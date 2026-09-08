"""Station MERRA-2 subsets, hourly loading and UTC minute interpolation."""

from datetime import date, datetime
from pathlib import Path
import re
from tempfile import NamedTemporaryFile
import warnings

import numpy as np
import pandas as pd
import pvlib
import xarray as xr

from . import merra2

MERRA_CACHE_DIR = Path(__file__).resolve().parents[1] / "data/raw/merra"
MERRA_PRODUCTS = {
    "slv": {"short_name": "M2T1NXSLV", "dataset_id": "M2T1NXSLV_5.12.4",
            "variables": {"o3": "TO3", "wv": "TQV"},
            "units": {"TO3": "Dobsons", "TQV": "kg m-2"}},
    "aer": {"short_name": "M2T1NXAER", "dataset_id": "M2T1NXAER_5.12.4",
            "variables": {"aod": "TOTEXTTAU", "alpha": "TOTANGSTR"},
            "units": {"TOTEXTTAU": "1", "TOTANGSTR": "1"}},
}


def login_merra():
    """Legacy explicit Earthdata login; subset processing does not require it."""
    import earthaccess
    return earthaccess.login(strategy="interactive", persist=True)


def _utc_timestamp(value):
    timestamp = pd.Timestamp(value)
    if pd.isna(timestamp):
        raise ValueError("MERRA period cannot contain NaT")
    return (timestamp.tz_localize("UTC") if timestamp.tzinfo is None
            else timestamp.tz_convert("UTC"))


def _minute_index(start, end):
    # A datetime at midnight is an explicit instant, unlike a date object/string.
    date_only_end = ((isinstance(end, date) and not isinstance(end, datetime))
                     or (isinstance(end, str)
                         and re.fullmatch(r"\d{4}-\d{2}-\d{2}", end.strip()) is not None))
    first, last = _utc_timestamp(start), _utc_timestamp(end)
    if date_only_end:
        last += pd.Timedelta(days=1)
    if last < first or (date_only_end and last == first):
        raise ValueError(f"MERRA invalid period: {start!r} to {end!r}")
    return pd.date_range(first, last, freq="1min",
                         inclusive="left" if date_only_end else "both")


def _required_hours(index):
    offset = pd.Timedelta(minutes=30)
    first = (index[0] - offset).floor("h") + offset
    last = (index[-1] - offset).ceil("h") + offset
    return pd.date_range(first, last, freq="h")


def _read_subset(path, station, product, day):
    """Read/validate one daily point subset without filling its missing values."""
    spec = MERRA_PRODUCTS[product]
    variables = list(spec["variables"].values())
    context = f"MERRA {variables}, UTC day {day:%Y-%m-%d}, file {path}"
    try:
        with xr.open_dataset(path, engine="h5netcdf") as ds:
            if dict(ds.sizes) != {"time": 24, "lat": 1, "lon": 1}:
                raise ValueError(f"expected time=24, lat=1, lon=1; got {dict(ds.sizes)}")
            if ds.attrs.get("ShortName") != spec["short_name"] or ds.attrs.get("VersionID") != "5.12.4":
                raise ValueError("unexpected product/version metadata")
            for variable in variables:
                if variable not in ds:
                    raise ValueError(f"missing variable {variable}")
                if ds[variable].dims != ("time", "lat", "lon"):
                    raise ValueError(f"unexpected dimensions for {variable}")
                if ds[variable].attrs.get("units") != spec["units"][variable]:
                    raise ValueError(f"unexpected units for {variable}: {ds[variable].attrs.get('units')!r}")
            # Native grid geometry is carried in the verified GES DISC files.
            for coord, resolution in (("lat", "LatitudeResolution"), ("lon", "LongitudeResolution")):
                spacing = float(ds.attrs[resolution])
                value = float(ds[coord].values[0])
                if not np.isfinite(spacing) or spacing <= 0:
                    raise ValueError(f"invalid {resolution}")
                distance = abs(value - float(station[coord]))
                if coord == "lon":
                    distance = min(distance, abs(360 - distance))
                if not np.isfinite(value) or distance > spacing / 2 + 1e-8:
                    raise ValueError(f"{coord}={value} is not the station's nearest grid point")
            timestamps = pd.DatetimeIndex(ds.time.values).tz_localize("UTC")
            expected = pd.date_range(day + pd.Timedelta(minutes=30), periods=24, freq="h")
            if not timestamps.is_unique or not timestamps.sort_values().equals(expected):
                raise ValueError("missing/duplicate/incorrect hourly UTC timestamps")
            frame = ds[variables].isel(lat=0, lon=0).to_dataframe()[variables].copy()
            frame.index = timestamps
            frame = frame.rename(columns={v: k for k, v in spec["variables"].items()}).sort_index()
            frame.attrs["units"] = {k: ds[v].attrs["units"] for k, v in spec["variables"].items()}
            frame.attrs["grid_point"] = (float(ds.lat.values[0]), float(ds.lon.values[0]))
            return frame
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise ValueError(f"{context}: {exc}") from exc


def _daily_subset(station, product, day):
    spec = MERRA_PRODUCTS[product]
    directory = MERRA_CACHE_DIR / station["name"]
    filename = f"{spec['dataset_id']}.{day:%Y%m%d}.SUB.nc"
    target = directory / filename
    # Accept the filenames produced by the original experiments as well.
    candidates = [target, *sorted(directory.glob(f"MERRA2_*.tavg1_2d_{product}_Nx.{day:%Y%m%d}.SUB.nc"))]
    for path in candidates:
        if path.is_file():
            try:
                return _read_subset(path, station, product, day)
            except ValueError as exc:
                warnings.warn(f"Invalid subset cache: {exc}", RuntimeWarning, stacklevel=2)

    directory.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(dir=directory, suffix=".pending.nc", delete=False) as f:
        pending = Path(f.name)
    try:
        lat, lon = float(station["lat"]), float(station["lon"])
        # Same small box/mapping as the verified BON experiment; no local regridding.
        bbox = [max(-180, lon - 0.01), max(-90, lat - 0.01), lon, lat]
        merra2.merra_download_subset(
            dataset_id=spec["dataset_id"], variables=list(spec["variables"].values()),
            start=day.strftime("%Y-%m-%dT00:00:00"), end=day.strftime("%Y-%m-%dT23:59:59"),
            bbox=bbox, output_file=pending)
        frame = _read_subset(pending, station, product, day)
        pending.replace(target)
        return frame
    except Exception as exc:
        raise RuntimeError(f"MERRA {list(spec['variables'].values())}, UTC day {day:%Y-%m-%d}: {exc}") from exc
    finally:
        pending.unlink(missing_ok=True)


def load_merra_data(station, start, end):
    """Load hourly point data covering the requested grid and interpolation edges.

    Period semantics match process_merra(); the returned hourly index uses the
    station timezone. Extra hours/days are retained here for interpolation.
    """
    index = _minute_index(start, end)
    index.tz_convert(station["tz"])  # validate timezone before acquisition
    name = station["name"]
    if not isinstance(name, str) or not name or Path(name).name != name or name in (".", ".."):
        raise ValueError("MERRA station name must be one directory name")
    for coord, bound in (("lat", 90), ("lon", 180)):
        if not np.isfinite(float(station[coord])) or abs(float(station[coord])) > bound:
            raise ValueError(f"Invalid station {coord}")
    days = _required_hours(index).normalize().unique()
    products, units, point = [], {}, None
    for product in MERRA_PRODUCTS:
        frames = [_daily_subset(station, product, day) for day in days]
        for frame in frames:
            if point is not None and frame.attrs["grid_point"] != point:
                raise ValueError("MERRA subsets select inconsistent grid points")
            point = frame.attrs["grid_point"]
            units.update(frame.attrs["units"])
        hourly = pd.concat(frames).sort_index()
        if not hourly.index.is_unique:
            raise ValueError(f"MERRA {product}: duplicate hourly timestamps")
        products.append(hourly)
    # Outer alignment preserves missing model inputs for explicit error handling.
    frame = pd.concat(products, axis=1).sort_index()
    frame.index = frame.index.tz_convert(station["tz"])
    frame.attrs = {"units": units, "grid_point": point}
    return frame


def process_merra(station, start, end):
    """Return o3, wv, aod, alpha at one-minute cadence for the requested period.

    Naive bounds are UTC; aware bounds retain their instant. ISO YYYY-MM-DD
    start means 00:00 UTC. A date-only end (ISO string or datetime.date) includes
    that entire UTC day, using next midnight as an exclusive limit. An end with
    an explicit time is inclusive and never extended, including midnight.

    The minute grid starts exactly at start; only its ticks within the bounds
    are returned. Acquire real hourly records bracketing those ticks, interpolate
    in UTC with method='time', then convert to station['tz'] (timezone-aware,
    preserving DST). Never extrapolate or interpolate across a missing hourly
    input: raise with the variable and affected UTC period instead. Units are
    unchanged and recorded in DataFrame.attrs['units']. There is no CAMS dependency.

    This intentionally replaces the legacy 59-minute tail and missing clipping.
    """
    target = _minute_index(start, end)
    hourly = load_merra_data(station, start, end)
    hourly.index = hourly.index.tz_convert("UTC")
    if not hourly.index.is_unique:
        raise ValueError("MERRA: duplicate hourly timestamps")
    required = _required_hours(target)
    selected = hourly.reindex(required)
    for variable in ("o3", "wv", "aod", "alpha"):
        invalid = ~np.isfinite(selected[variable].to_numpy())
        if invalid.any():
            missing = required[invalid][0]
            affected_start = max(target[0], missing - pd.Timedelta(hours=1))
            affected_end = min(target[-1], missing + pd.Timedelta(hours=1))
            raise ValueError(f"MERRA {variable}: missing/nonfinite hourly input at {missing}; "
                             f"affected UTC period {affected_start} to {affected_end}; "
                             "cannot interpolate or extrapolate")
    # Retain original :30 hourly knots even for minute grids offset in seconds.
    result = (selected.reindex(required.union(target)).sort_index()
              .interpolate(method="time", limit_area="inside").reindex(target))
    result.index = result.index.tz_convert(station["tz"])
    result.attrs = hourly.attrs.copy()
    return result


def filename_merra(station, path):
    label = station["name"]
    file_str_merra = f"{label}_MERRA.csv"
    file_merra = Path(path / file_str_merra)
    return file_merra


def load_merra(station, path):
    
    filename = filename_merra(station, path)
    
    df = pd.read_csv(
        filename,
        index_col=0,
    )

    # ---------------------------------------------------------
    # Timezone
    # ---------------------------------------------------------

    df.index = pd.to_datetime(df.index, utc=True)
    df.index = df.index.tz_convert(station["tz"])
    
    start = pd.Period(station["period"], freq="M").start_time
    end = pd.Period(station["period"], freq="M").end_time.floor("min")
    
    start = start.tz_localize(station["tz"])
    end = end.tz_localize(station["tz"])
    
    idx = pd.date_range(
        start=start,
        end=end,
        freq="1min"
    )
    
    df = df.reindex(idx)

    # ---------------------------------------------------------
    # Solar zenith angle
    # ---------------------------------------------------------

    solar_position = pvlib.solarposition.get_solarposition(
        time=df.index,
        latitude=station["lat"],
        longitude=station["lon"],
    )

    df["sza"] = solar_position["zenith"]
    
    

    return df
