#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Aug 18 13:04:18 2026

@author: inti
"""

import numpy as np
import pandas as pd 
from pathlib import Path

def load_usa_uv(station_id, path):
    """Return (DataFrame, 'f01' or 'f05') from a USA OUT directory.

    Preserve original columns (UV is labelled UVB), flags, numeric sentinels,
    row order and cadence. Empty CSV fields become NaN. Naive CSV timestamps
    represent UTC and are localized as UTC without shifting clock times.
    The CSVs do not declare units; no unit conversions are applied.
    No QC filtering, interpolation or resampling is applied.
    """
    tag = station_id.lower()
    directory = Path(path) / tag
    searched = []
    for resolution in ("f01", "f05"):
        # BRW and MSN use the existing uppercase F01 filename variant.
        for suffix in (resolution, resolution.upper()):
            filename = directory / f"{tag}_UVdata_{suffix}.csv"
            searched.append(filename)
            if not filename.is_file():
                continue
            df = pd.read_csv(filename, index_col=0)
            if "UVB" not in df.columns:
                raise ValueError(f"UV USA {station_id}: missing UVB column in {filename}")
            df.index = pd.to_datetime(df.index, format="%Y-%m-%d %H:%M:%S", errors="raise")
            if df.index.hasnans:
                raise ValueError(f"UV USA {station_id}: missing timestamps in {filename}")
            df.index = df.index.tz_localize("UTC")
            return df, resolution
    raise FileNotFoundError(
        f"UV USA {station_id}: no f01/f05 file found; searched: "
        + ", ".join(str(filename) for filename in searched)
    )


def clean_usa_uv(df, resolution):
    """Return a copy replacing only the UVB missing sentinel -9.9999 with NaN.

    Both f01 and f05 retain their index, columns, flags and other values.
    No flag-based filtering or temporal processing is applied.
    """
    if resolution not in ("f01", "f05"):
        raise ValueError(f"Unsupported USA UV resolution: {resolution!r}")
    result = df.copy()
    result["UVB"] = result["UVB"].mask(result["UVB"].eq(-9.9999))
    return result


def regularize_usa_uv(df, resolution):
    """Insert missing UTC timestamps as NaN rows, without interpolation.

    The grid spans the first through last observation at the native cadence.
    Reject off-grid timestamps rather than silently discarding observations.
    """
    frequencies = {"f01": "1min", "f05": "5min"}
    if resolution not in frequencies:
        raise ValueError(f"Unsupported USA UV resolution: {resolution!r}")
    if not isinstance(df.index, pd.DatetimeIndex) or str(df.index.tz) != "UTC":
        raise ValueError("USA UV: index must be timezone-aware in UTC")
    if df.index.hasnans or not df.index.is_unique:
        raise ValueError("USA UV: timestamps must be valid and unique")
    if df.empty:
        return df.copy()
    grid = pd.date_range(df.index.min(), df.index.max(),
                         freq=frequencies[resolution], name=df.index.name)
    if not df.index.isin(grid).all():
        raise ValueError("USA UV: timestamps do not fit the requested cadence")
    return df.reindex(grid)


def match_usa_uv_merra(df_uv, df_merra):
    """Attach native MERRA values at floor(UV hour) + 30 minutes.

    Both indices must already be UTC. Return all UV rows/columns unchanged
    plus o3, wv, aod, alpha; absent MERRA records become NaN. Report the number
    of unmatched observations and store it in attrs['merra_unmatched_count'].
    """
    for label, frame in (("UV", df_uv), ("MERRA", df_merra)):
        if not isinstance(frame.index, pd.DatetimeIndex) or str(frame.index.tz) != "UTC":
            raise ValueError(f"{label}: index must be timezone-aware in UTC")
        if frame.index.hasnans:
            raise ValueError(f"{label}: index contains NaT")
    columns = ["o3", "wv", "aod", "alpha"]
    if not df_merra.index.is_unique:
        raise ValueError("MERRA: duplicate timestamps")
    if not (df_merra.index == df_merra.index.floor("h") + pd.Timedelta(minutes=30)).all():
        raise ValueError("MERRA: expected native timestamps centered at HH:30:00")
    missing = [column for column in columns if column not in df_merra.columns]
    if missing:
        raise ValueError(f"MERRA: missing columns {missing}")
    overlap = [column for column in columns if column in df_uv.columns]
    if overlap:
        raise ValueError(f"UV: cannot overwrite existing columns {overlap}")
    centers = df_uv.index.floor("h") + pd.Timedelta(minutes=30)
    matched = df_merra[columns].reindex(centers)
    result = df_uv.copy()
    for column in columns:
        result[column] = matched[column].to_numpy()
    unmatched = int((~centers.isin(df_merra.index)).sum())
    result.attrs["merra_unmatched_count"] = unmatched
    print(f"UV USA: {unmatched} de {len(df_uv)} observaciones sin match MERRA.", flush=True)
    return result


def filenames(station, path):
    label = station["name"]
    period = station["period"]
    if label == 'PAR':
        file_str_uv = f"{label}_Ultra-violet.csv"
        file_str_rad = f"{label}_radiation_{period}.csv"
    else:
        file_str_uv = f"{label}_Ultra-violet_{period}.tab"
        file_str_rad = f"{label}_radiation_{period}.tab"
    file_uv = Path(path / file_str_uv)
    file_rad = Path(path / file_str_rad)
    return file_uv, file_rad


def load_bsrn_uv(station, path, start=None, end=None):
    
    filename = filenames(station, path)
    filename = filename[0]
    tz_local = station["tz"]
    
    with open(filename, "r") as f:
        for i, line in enumerate(f):
            if line.strip() == "*/":
                skiprows = i + 1
                break

    df = pd.read_csv(filename,sep="\t", skiprows=skiprows, parse_dates=["Date/Time"])

    df["Date"] = (
    pd.to_datetime(df["Date/Time"])
      .dt.tz_localize("UTC")
      .dt.tz_convert(tz_local)
      )
    
    columnas = {
        "Date": "Date",
        "UV-a global [W/m**2]": "uva",
        "UV-b global [W/m**2]": "uvb"
    }

    presentes = [c for c in columnas if c in df.columns]

    df = df[presentes].rename(columns=columnas).set_index("Date")

    for col in ["uva", "uvb"]:
        if col not in df.columns:
            df[col] = np.nan

    # Opcional: mantener un orden fijo
    df = df[["uva", "uvb"]]
    
    if start is None:
        start = df.index.min()
    else:
        start = (
            pd.Timestamp(start)
            .tz_localize("UTC")
            .tz_convert(tz_local)
        )
    
    if end is None:
        end = df.index.max()
    else:
        end = (
            pd.Timestamp(end)
            .tz_localize("UTC")
            .tz_convert(tz_local)
        )
    
    idx = pd.date_range(start, end, freq="1min")
    
    df = df.reindex(idx)
    df.index.name = "Date"
    
    return df


def load_bsrn_rad(station, path, start=None, end=None):
    
    filename = filenames(station, path)
    filename = filename[1]
    tz_local = station["tz"]

    with open(filename, "r") as f:
        for i, line in enumerate(f):
            if line.strip() == "*/":
                skiprows = i + 1
                break

    df = pd.read_csv(
        filename,
        sep="\t",
        skiprows=skiprows,
        parse_dates=["Date/Time"]
    )

    df["Date"] = (
        pd.to_datetime(df["Date/Time"])
        .dt.tz_localize("UTC")
        .dt.tz_convert(tz_local)
    )

    columnas = {
        "Date": "Date",
        "SWD [W/m**2]": "ghi",
        "DIR [W/m**2]": "dni",
        "DIF [W/m**2]": "dhi",
    }

    presentes = [c for c in columnas if c in df.columns]

    df = (
        df[presentes]
        .rename(columns=columnas)
        .set_index("Date")
    )

    # Reemplazar códigos de dato faltante de BSRN
    df = df.replace(-1, np.nan)

    # Asegurar que siempre existan las columnas
    for col in ["ghi", "dni", "dhi"]:
        if col not in df.columns:
            df[col] = np.nan

    df = df[["ghi", "dni", "dhi"]]

    if start is None:
        start = df.index.min()
    else:
        start = (
            pd.Timestamp(start)
            .tz_localize("UTC")
            .tz_convert(tz_local)
        )

    if end is None:
        end = df.index.max()
    else:
        end = (
            pd.Timestamp(end)
            .tz_localize("UTC")
            .tz_convert(tz_local)
        )

    idx = pd.date_range(start, end, freq="1min")

    df = df.reindex(idx)
    df.index.name = "Date"

    return df

def load_chile_uv(station, path, start=None, end=None):

    filename = filenames(station, path)[0]
    tz_local = station["tz"]

    df = pd.read_csv(
        filename,
        parse_dates=[0],
        index_col=0
    )

    df.index = pd.to_datetime(df.index).tz_localize(tz_local)
    df.index.name = "Date"

    df = df.rename(columns={df.columns[0]: "uvb"})

    if start is None:
        period = pd.Period(station["period"], freq="M")
        start = period.start_time.tz_localize(tz_local)
        end = period.end_time.floor("min").tz_localize(tz_local)

    # Índice final a 1 minuto
    idx = pd.date_range(start=start, end=end, freq="1min")

    # Interpolar desde los datos originales de 5 min
    df = (
        df.reindex(idx)
          .interpolate(method="time")
    )

    # Completar los minutos finales posteriores a la última medición
    df = df.ffill()

    return df

def load_chile_rad(station, path, start=None, end=None):

    filename = filenames(station, path)
    filename = filename[1]
    tz_local = station["tz"]
    
    df = pd.read_csv(filename, sep=";")

    df["Date"] = (
        pd.to_datetime(df["momento"])
        .dt.tz_localize("UTC")
        .dt.tz_convert(tz_local)
    )

    df = (
        df[["Date", "radiacionGlobalInst"]]
        .rename(columns={"radiacionGlobalInst": "ghi"})
        .set_index("Date")
    )

    df["ghi"] = pd.to_numeric(df["ghi"], errors="coerce")

    start = pd.Period(station["period"], freq="M").start_time
    end = pd.Period(station["period"], freq="M").end_time.floor("min")
    
    start = start.tz_localize(station["tz"])
    end = end.tz_localize(station["tz"])

    # Completar minutos faltantes con NaN
    idx = pd.date_range(
        start=start,
        end=end,
        freq="1min",
        tz=station["tz"]
    )
    
    df = df.reindex(idx)

    

    return df
