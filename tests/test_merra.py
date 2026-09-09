"""Run with python -m unittest discover -s tests -v; no network required."""
from datetime import date
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import requests
import xarray as xr

from config import STATIONS_USA
from src import merra, merra2

BON = {**STATIONS_USA["BON"], "name": "BON"}
UNITS = {"o3": "Dobsons", "wv": "kg m-2", "aod": "1", "alpha": "1"}


def hourly_data(station, start, end):
    hours = merra._required_hours(merra._minute_index(start, end))
    frame = pd.DataFrame({v: np.arange(len(hours), dtype=float) + i
                          for i, v in enumerate(UNITS)}, index=hours)
    frame.index = frame.index.tz_convert(station["tz"])
    frame.attrs["units"] = UNITS
    return frame


def fixture(path, product="slv", day="2024-10-01"):
    spec = merra.MERRA_PRODUCTS[product]
    ds = xr.Dataset(
        {v: (("time", "lat", "lon"), np.arange(24, dtype=float).reshape(24, 1, 1),
             {"units": spec["units"][v]}) for v in spec["variables"].values()},
        coords={"time": pd.date_range(f"{day}T00:30:00", periods=24, freq="h"),
                "lat": [40.0], "lon": [-88.125]},
        attrs={"ShortName": spec["short_name"], "VersionID": "5.12.4",
               "LatitudeResolution": "0.5", "LongitudeResolution": "0.625"})
    ds.to_netcdf(path, engine="h5netcdf")
    return ds


class PeriodTests(unittest.TestCase):
    def test_date_end_and_explicit_midnight_differ(self):
        full = merra._minute_index("2024-10-01", "2024-10-01")
        self.assertEqual(len(full), 1440)
        self.assertEqual(full[-1], pd.Timestamp("2024-10-01T23:59Z"))
        self.assertEqual(len(merra._minute_index("2024-10-01", "2024-10-01T00:00:00")), 1)
        self.assertTrue(full.equals(merra._minute_index(date(2024, 10, 1), date(2024, 10, 1))))

    def test_aware_bounds_preserve_instants(self):
        self.assertTrue(merra._minute_index("2024-09-30T20:00-05:00", "2024-09-30T22:00-05:00")
                        .equals(merra._minute_index("2024-10-01T01:00", "2024-10-01T03:00")))

    def test_edges_and_exact_knots(self):
        hours = merra._required_hours(merra._minute_index("2024-10-01", "2024-10-01"))
        self.assertEqual(hours[0], pd.Timestamp("2024-09-30T23:30Z"))
        self.assertEqual(hours[-1], pd.Timestamp("2024-10-02T00:30Z"))
        exact = merra._required_hours(merra._minute_index("2024-10-01T00:30", "2024-10-01T00:30"))
        self.assertEqual(len(exact), 1)

    def test_bad_bounds(self):
        for start, end in [("2024-10-02", "2024-10-01"), ("NaT", "2024-10-01")]:
            with self.subTest(start=start), self.assertRaises(ValueError):
                merra._minute_index(start, end)


class NativeProcessingTests(unittest.TestCase):
    def test_native_values_timestamps_columns_and_attrs(self):
        data = hourly_data(BON, "2024-10-01", "2024-10-01")
        with patch.object(merra, "load_merra_data", return_value=data):
            result = merra.process_merra(BON, "2024-10-01", "2024-10-01")
        pd.testing.assert_frame_equal(result, data.iloc[1:-1])
        self.assertEqual(result.attrs, data.attrs)
        self.assertEqual(len(result), 24)
        self.assertTrue((result.index.tz_convert("UTC").minute == 30).all())

    def test_exact_bounds_and_empty_period(self):
        data = hourly_data(BON, "2024-10-01", "2024-10-01")
        for start, end, count in [
            ("2024-10-01T01:29:15", "2024-10-01T01:30:00", 1),
            ("2024-10-01T01:30:01", "2024-10-01T02:29:59", 0),
            ("2024-10-01", "2024-10-01T00:00:00", 0),
            (date(2024, 10, 1), date(2024, 10, 1), 24),
        ]:
            with self.subTest(start=start, end=end), patch.object(merra, "load_merra_data", return_value=data):
                self.assertEqual(len(merra.process_merra(BON, start, end)), count)

    def test_dst_preserves_native_instants(self):
        for day, count in [("2024-03-10", 23), ("2024-11-03", 25)]:
            start = pd.Timestamp(day, tz=BON["tz"])
            end = pd.Timestamp(f"{day}T23:59", tz=BON["tz"])
            with self.subTest(day=day), patch.object(merra, "load_merra_data", side_effect=hourly_data):
                result = merra.process_merra(BON, start, end)
            self.assertEqual(len(result), count)
            self.assertTrue(result.index.is_unique)
            self.assertTrue((result.index[1:] - result.index[:-1] == pd.Timedelta(hours=1)).all())

    def test_nonfinite_input_raises(self):
        data = hourly_data(BON, "2024-10-01", "2024-10-01")
        data.loc[data.index[1], "wv"] = np.nan
        with patch.object(merra, "load_merra_data", return_value=data):
            with self.assertRaisesRegex(ValueError, "MERRA wv: missing/nonfinite"):
                merra.process_merra(BON, "2024-10-01", "2024-10-01")


class ProcessingTests(unittest.TestCase):
    def test_interpolation_preserves_values_units_and_utc_ticks(self):
        with patch.object(merra, "load_merra_data", side_effect=hourly_data):
            result = merra.process_merra_1min(BON, "2024-10-01T01:00", "2024-10-01T03:00")
        self.assertEqual(list(result), list(UNITS))
        self.assertEqual(result.attrs["units"], UNITS)
        self.assertEqual(len(result), 121)
        np.testing.assert_allclose(result.o3, 0.5 + np.arange(121) / 60)
        self.assertEqual(str(result.index.tz), "America/Chicago")
        self.assertTrue(result.index.is_unique and result.index.is_monotonic_increasing)
        self.assertFalse(result.isna().any().any())

    def test_offset_grid_keeps_hourly_interpolation_knots(self):
        with patch.object(merra, "load_merra_data", side_effect=hourly_data):
            result = merra.process_merra_1min(BON, "2024-10-01T01:00:15", "2024-10-01T01:02:20")
        self.assertEqual(len(result), 3)
        self.assertAlmostEqual(result.o3.iloc[0], 30.25 / 60)
        self.assertEqual(result.index.tz_convert("UTC")[-1], pd.Timestamp("2024-10-01T01:02:15Z"))

    def test_dst_preserves_elapsed_minutes_and_unique_aware_index(self):
        for day, count in [("2024-03-10", 1380), ("2024-11-03", 1500)]:
            with self.subTest(day=day), patch.object(merra, "load_merra_data", side_effect=hourly_data):
                start = pd.Timestamp(day, tz=BON["tz"])
                end = pd.Timestamp(f"{day}T23:59", tz=BON["tz"])
                result = merra.process_merra_1min(BON, start, end)
                self.assertEqual(len(result), count)
                self.assertTrue(result.index.is_unique and result.index.is_monotonic_increasing)
                self.assertTrue((result.index[1:] - result.index[:-1] == pd.Timedelta(minutes=1)).all())

    def test_missing_edge_missing_hour_and_nan_raise(self):
        for kind in ("left", "right", "hour", "nan"):
            data = hourly_data(BON, "2024-10-01T01:00", "2024-10-01T03:00")
            if kind == "nan":
                data.loc[data.index[1], "wv"] = np.nan
            else:
                data = data.drop(data.index[{"left": 0, "right": -1, "hour": 1}[kind]])
            with self.subTest(kind=kind), patch.object(merra, "load_merra_data", return_value=data):
                with self.assertRaisesRegex(ValueError, r"MERRA (wv|o3):.*affected UTC period"):
                    merra.process_merra_1min(BON, "2024-10-01T01:00", "2024-10-01T03:00")

    def test_nonfinite_outside_required_records_is_not_filled(self):
        data = hourly_data(BON, "2024-10-01T01:00", "2024-10-01T03:00")
        data.loc[data.index[0] - pd.Timedelta(hours=1)] = np.nan
        with patch.object(merra, "load_merra_data", return_value=data):
            result = merra.process_merra_1min(BON, "2024-10-01T01:00", "2024-10-01T03:00")
        self.assertFalse(result.isna().any().any())


class CacheTests(unittest.TestCase):
    def test_legacy_cache_and_daily_product_alignment(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "BON").mkdir()
            for product in merra.MERRA_PRODUCTS:
                fixture(root / "BON" / f"MERRA2_400.tavg1_2d_{product}_Nx.20241001.SUB.nc", product)
            with patch.object(merra, "MERRA_CACHE_DIR", root), patch.object(merra, "_monthly_subset", side_effect=RuntimeError("monthly unavailable")), patch.object(merra2, "merra_download_subset") as download:
                result = merra.process_merra_1min(BON, "2024-10-01T01:00", "2024-10-01T03:00")
                native = merra.process_merra(BON, "2024-10-01T01:00", "2024-10-01T03:00")
                download.assert_not_called()
            np.testing.assert_array_equal(native.to_numpy(), result.loc[native.index].to_numpy())
            self.assertEqual(list(native), list(result))
            self.assertEqual(len(native), 2)
            self.assertEqual(len(result), 121)
            self.assertEqual(result.attrs["units"], UNITS)

    def test_invalid_cache_replaced_then_reused(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "BON").mkdir()
            target = root / "BON/M2T1NXSLV_5.12.4.20241001.SUB.nc"
            target.write_text("<html>not a NetCDF</html>")
            def download(**kwargs):
                fixture(kwargs["output_file"])
            with patch.object(merra, "MERRA_CACHE_DIR", root), patch.object(merra2, "merra_download_subset", side_effect=download) as mock:
                with self.assertWarnsRegex(RuntimeWarning, "Invalid subset cache"):
                    merra._daily_subset(BON, "slv", pd.Timestamp("2024-10-01", tz="UTC"))
                merra._daily_subset(BON, "slv", pd.Timestamp("2024-10-01", tz="UTC"))
                self.assertEqual(mock.call_count, 1)

    def test_wrong_units_point_timestamp_or_variable_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "subset.nc"
            for problem in ("units", "point", "time", "variable"):
                ds = fixture(path)
                if problem == "units": ds.TQV.attrs["units"] = "wrong"
                if problem == "point": ds = ds.assign_coords(lat=[41.0])
                if problem == "time": ds = ds.assign_coords(time=ds.time.values + np.timedelta64(1, "h"))
                if problem == "variable": ds = ds.drop_vars("TQV")
                ds.to_netcdf(path, engine="h5netcdf")
                with self.subTest(problem=problem), self.assertRaisesRegex(ValueError, "UTC day 2024-10-01"):
                    merra._read_subset(path, BON, "slv", pd.Timestamp("2024-10-01", tz="UTC"))


class ServiceTests(unittest.TestCase):
    def test_fault_and_bad_json_raise(self):
        response = MagicMock()
        response.__enter__.return_value = response
        with patch.object(merra2.requests, "post", return_value=response):
            response.json.return_value = {"type": "jsonwsp/fault", "fault": "bad request"}
            with self.assertRaisesRegex(RuntimeError, "fault"):
                merra2.merra_subset_request("dataset", ["x"], "start", "end", [0, 0, 0, 0])
            response.json.side_effect = ValueError("bad JSON")
            with self.assertRaisesRegex(RuntimeError, "bad JSON"):
                merra2._subset_rpc("GetStatus", {})

    def test_failed_dismissed_and_unknown_status_raise(self):
        for status in ("Failed", "Dismissed", "Unknown"):
            with self.subTest(status=status), patch.object(merra2, "_subset_rpc", return_value={"Status": status}):
                with self.assertRaisesRegex(RuntimeError, status):
                    merra2.merra_subset_result("new-job", "new-session")

    def test_poll_timeout(self):
        with patch.object(merra2.time, "monotonic", side_effect=[0, 601]):
            with self.assertRaises(TimeoutError):
                merra2.merra_subset_result("new-job", "new-session")

    def test_select_netcdf_and_skip_readme(self):
        with patch.object(merra2, "_subset_rpc", side_effect=[{"Status": "Succeeded"}, {"items": [
                {"type": "VIEW RELATED INFORMATION", "link": "https://example.org/readme"},
                {"type": "DATA", "link": "https://example.org/file.SUB.nc"}]}]):
            self.assertEqual(merra2.merra_subset_result("new-job", "new-session"), "https://example.org/file.SUB.nc")

    def test_http_failure_preserves_existing_output(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "file.nc"
            output.write_bytes(b"existing")
            with patch.object(merra2, "merra_subset_request", return_value=("job", "session")), \
                 patch.object(merra2, "merra_subset_result", return_value="https://example.org/file.SUB.nc"), \
                 patch.object(merra2.requests, "get", side_effect=requests.Timeout("timeout")):
                with self.assertRaisesRegex(RuntimeError, "timeout"):
                    merra2.merra_download_subset("dataset", ["x"], "start", "end", [0, 0, 0, 0], output)
            self.assertEqual(output.read_bytes(), b"existing")
            self.assertEqual(list(Path(directory).iterdir()), [output])


if __name__ == "__main__":
    unittest.main()
