#!/usr/bin/env python3
"""Benchmark aislado: requests mensuales frente a tres días de muestra."""
from pathlib import Path
from time import perf_counter
import json
import time
from urllib.parse import unquote, urlparse

import numpy as np
import pandas as pd
import requests
import xarray as xr

from config import STATIONS_USA
from src import merra as mr, merra2

START = "2024-01-01"
END = "2024-01-31"
SAMPLE_DAYS = ("2024-01-01", "2024-01-16", "2024-01-31")
ROOT = Path(__file__).resolve().parent / "data/raw/merra_test_monthly/BON"


def monthly_links(job, session):
    # Experimental: un job mensual puede devolver varios NetCDF diarios.
    args = {"jobId": job, "sessionId": session}
    deadline = time.monotonic() + merra2.JOB_TIMEOUT
    while time.monotonic() < deadline:
        result = merra2._subset_rpc("GetStatus", args)
        status = result.get("Status")
        if status == "Succeeded":
            break
        if status not in ("Accepted", "Running", "Pending", "Queued"):
            raise RuntimeError(f"Estado mensual: {status}")
        time.sleep(max(0, min(merra2.POLL_INTERVAL, deadline - time.monotonic())))
    else:
        raise TimeoutError("Job mensual excedió el timeout")
    result = merra2._subset_rpc("GetResult", args)
    links = [item["link"] for item in result.get("items", [])
             if isinstance(item, dict)
             and item.get("type") != "VIEW RELATED INFORMATION"
             and isinstance(item.get("link"), str)
             and urlparse(item["link"]).scheme == "https"
             and ".nc" in unquote(item["link"]).lower()]
    if not links:
        raise RuntimeError("Job mensual sin enlaces NetCDF")
    return links


def fetch(link, path):
    pending = path.with_suffix(".part")
    deadline = time.monotonic() + merra2.JOB_TIMEOUT
    try:
        with requests.get(link, stream=True, timeout=merra2.HTTP_TIMEOUT) as response:
            response.raise_for_status()
            with pending.open("wb") as stream:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if time.monotonic() >= deadline:
                        raise TimeoutError("Transferencia mensual excedió el timeout")
                    stream.write(chunk)
        if pending.stat().st_size == 0:
            raise ValueError("Archivo mensual vacío")
        pending.replace(path)
    finally:
        pending.unlink(missing_ok=True)


def inspect(paths, product, station):
    spec = mr.MERRA_PRODUCTS[product]
    datasets = []
    for path in paths:
        with xr.open_dataset(path, engine="h5netcdf") as source:
            ds = source.load()
        print(f"  {path.name}: {path.stat().st_size} bytes; dimensiones {dict(ds.sizes)}", flush=True)
        if ds.sizes.get("lat") != 1 or ds.sizes.get("lon") != 1:
            raise ValueError("Se esperaba un único punto espacial")
        if ds.attrs.get("ShortName") != spec["short_name"] or ds.attrs.get("VersionID") != "5.12.4":
            raise ValueError("Producto/versión incorrectos")
        for variable in spec["variables"].values():
            if ds[variable].dims != ("time", "lat", "lon") or ds[variable].attrs.get("units") != spec["units"][variable]:
                raise ValueError(f"Dimensiones/unidades incorrectas: {variable}")
        for coord, resolution in (("lat", "LatitudeResolution"), ("lon", "LongitudeResolution")):
            value = float(ds[coord].values[0])
            spacing = float(ds.attrs[resolution])
            distance = abs(value - station[coord])
            if coord == "lon":
                distance = min(distance, abs(360 - distance))
            if not np.isfinite(value) or not np.isfinite(spacing) or spacing <= 0 or distance > spacing / 2 + 1e-8:
                raise ValueError(f"Punto nearest incorrecto: {coord}")
        datasets.append(ds)
    combined = xr.concat(datasets, dim="time", join="exact").sortby("time")
    times = pd.DatetimeIndex(combined.time.values)
    expected = pd.date_range(f"{START}T00:30", f"{END}T23:30", freq="h")
    if not times.equals(expected):
        raise ValueError(f"Se esperaban 744 timestamps horarios nativos únicos; obtenidos {len(times)}")
    print(f"  Total: {dict(combined.sizes)}; UTC {times[0]} a {times[-1]}; "
          f"lat={combined.lat.values.tolist()}, lon={combined.lon.values.tolist()}", flush=True)
    return combined


def compare(monthly, product, station, directory, experimental=False):
    spec = mr.MERRA_PRODUCTS[product]
    matches = 0
    for day in pd.date_range(START, END, tz="UTC"):
        candidates = ([directory / f"{product}_{day:%Y%m%d}.nc"] if experimental else
                      [directory / f"{spec['dataset_id']}.{day:%Y%m%d}.SUB.nc",
                       *sorted(directory.glob(f"MERRA2_*.tavg1_2d_{product}_Nx.{day:%Y%m%d}.SUB.nc"))])
        path = next((path for path in candidates if path.is_file()), None)
        if path is None:
            continue
        daily = mr._read_subset(path, station, product, day)
        point = (float(monthly.lat.values[0]), float(monthly.lon.values[0]))
        if daily.attrs["grid_point"] != point:
            raise ValueError("Puntos mensual y diario distintos")
        # Comparar todos los registros disponibles, no sólo algunos ejemplos.
        for column, variable in spec["variables"].items():
            values = monthly[variable].isel(lat=0, lon=0).sel(time=daily.index.tz_localize(None)).values
            np.testing.assert_allclose(values, daily[column].values, rtol=0, atol=0, equal_nan=True,
                                       err_msg=f"{variable}, {day:%Y-%m-%d}")
        matches += len(daily)
    print(f"  Comparación {product.upper()} con {directory}: {matches} timestamps por variable, "
          + ("igualdad numérica exacta" if matches else "sin caché disponible"), flush=True)
    return matches


def main():
    station = STATIONS_USA["BON"]
    lat, lon = float(station["lat"]), float(station["lon"])
    bbox = [max(-180, lon - 0.01), max(-90, lat - 0.01), lon, lat]
    # Cada ejecución tiene su propio directorio; nunca publica en la caché diaria.
    run = ROOT / pd.Timestamp.now(tz="UTC").strftime("%Y%m%dT%H%M%S%fZ")
    run.mkdir(parents=True)
    report = {"station": "BON", "start": START, "end": END, "monthly": {}, "daily_samples": {}}
    total_started = perf_counter()
    try:
        monthly = {}
        for product in ("aer", "slv"):
            spec = mr.MERRA_PRODUCTS[product]
            print(f"Mensual {product.upper()}: {START} a {END}", flush=True)
            started = perf_counter()
            job, session = merra2.merra_subset_request(spec["dataset_id"], list(spec["variables"].values()),
                                                      f"{START}T00:00:00", f"{END}T23:59:59", bbox)
            links = monthly_links(job, session)
            job_seconds = perf_counter() - started
            paths = []
            for i, link in enumerate(links):
                path = run / f"{product}_{i:03d}.nc"
                fetch(link, path)
                paths.append(path)
            acquisition_seconds = perf_counter() - started
            report["monthly"][product] = {"job_seconds": job_seconds, "acquisition_seconds": acquisition_seconds,
                                            "files": {p.name: p.stat().st_size for p in paths}}
            print(f"  Job: {job_seconds:.1f} s; job + transferencias: {acquisition_seconds:.1f} s", flush=True)
            monthly[product] = inspect(paths, product, station)
            for directory in dict.fromkeys([mr.MERRA_CACHE_DIR / station["name"], mr.MERRA_CACHE_DIR / "BON"]):
                compare(monthly[product], product, station, directory)
        daily_dir = run / "daily_sample"
        daily_dir.mkdir()
        for day in SAMPLE_DAYS:
            started = perf_counter()
            for product in ("slv", "aer"):
                spec = mr.MERRA_PRODUCTS[product]
                path = daily_dir / f"{product}_{day.replace('-', '')}.nc"
                merra2.merra_download_subset(spec["dataset_id"], list(spec["variables"].values()),
                                            f"{day}T00:00:00", f"{day}T23:59:59", bbox, path)
            report["daily_samples"][day] = perf_counter() - started
            print(f"Diario de muestra {day}: {report['daily_samples'][day]:.1f} s (SLV + AER)", flush=True)
        for product in ("aer", "slv"):
            compare(monthly[product], product, station, daily_dir, experimental=True)
        monthly_seconds = sum(item["acquisition_seconds"] for item in report["monthly"].values())
        estimated = np.mean(list(report["daily_samples"].values())) * 31
        report.update(monthly_seconds=monthly_seconds, daily_estimated_seconds=float(estimated), speedup=float(estimated / monthly_seconds))
        print(f"Mensual: {monthly_seconds:.1f} s para 31 días\n"
              f"Diario estimado: ~{estimated:.1f} s para 31 días (media de 3 días sin caché)\n"
              f"Factor de mejora estimado: {estimated / monthly_seconds:.2f}x", flush=True)
    except Exception as exc:
        report["error"] = str(exc)
        print(f"ERROR experimental: {exc}\nBenchmark incompleto; no se puede concluir una mejora.", flush=True)
    finally:
        report["total_seconds"] = perf_counter() - total_started
        (run / "benchmark.json").write_text(json.dumps(report, indent=2) + "\n")
        print(f"Tiempo total: {report['total_seconds']:.1f} s. Resultados: {run}", flush=True)
    return 1 if "error" in report else 0


if __name__ == "__main__":
    raise SystemExit(main())
