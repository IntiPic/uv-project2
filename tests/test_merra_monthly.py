"""Monthly acquisition tests: real temporary NetCDFs, no network."""
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd
import xarray as xr

from src import merra, merra2
from test_merra import BON, fixture


def download_month(dataset_id, variables, start, end, bbox, directory):
    product = 'slv' if 'SLV' in dataset_id else 'aer'
    paths = []
    for day in pd.date_range(start[:10], end[:10]):
        path = Path(directory) / f'{day:%Y%m%d}.nc'
        fixture(path, product, f'{day:%Y-%m-%d}')
        paths.append(path)
    return paths[::-1]  # service order must not affect timestamps


class MonthlyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.enterContext(patch.object(merra, 'MERRA_MONTHLY_CACHE_DIR', self.root / 'monthly'))
        self.enterContext(patch.object(merra, 'MERRA_CACHE_DIR', self.root / 'daily'))
        self.enterContext(redirect_stdout(StringIO()))
        self.download = self.enterContext(patch.object(merra2, '_download_monthly_subsets', side_effect=download_month))

    def test_month_lengths_cache_and_daily_equivalence(self):
        for month, days in [('2024-01-01', 31), ('2023-02-01', 28), ('2024-02-01', 29), ('2024-04-01', 30)]:
            month = pd.Timestamp(month, tz='UTC')
            for product in merra.MERRA_PRODUCTS:
                with self.subTest(month=month, product=product):
                    frame = merra._monthly_subset(BON, product, month)
                    frame.attrs.pop('download_seconds')
                    self.assertEqual(len(frame), days * 24)
                    daily = []
                    for day in pd.date_range(month, periods=days):
                        path = self.root / 'daily.nc'
                        fixture(path, product, f'{day:%Y-%m-%d}')
                        daily.append(merra._read_subset(path, BON, product, day))
                    pd.testing.assert_frame_equal(frame, pd.concat(daily))
                    calls = self.download.call_count
                    cached = merra._monthly_subset(BON, product, month)
                    pd.testing.assert_frame_equal(frame, cached)
                    self.assertEqual(calls, self.download.call_count)
                    self.assertEqual(frame.attrs, cached.attrs)
        self.assertFalse((self.root / 'daily').exists())

    def test_invalid_cache_reacquired_and_failed_replacement_not_published(self):
        month = pd.Timestamp('2024-01-01', tz='UTC')
        merra._monthly_subset(BON, 'slv', month)
        target = next((self.root / 'monthly/BON').glob('*.nc'))
        target.write_bytes(b'invalid')
        with self.assertWarns(RuntimeWarning):
            merra._monthly_subset(BON, 'slv', month)
        self.assertEqual(self.download.call_count, 2)
        target.write_bytes(b'preserve until validated')
        self.download.side_effect = RuntimeError('503 exhausted')
        with self.assertWarns(RuntimeWarning), self.assertRaises(RuntimeError):
            merra._monthly_subset(BON, 'slv', month)
        self.assertEqual(target.read_bytes(), b'preserve until validated')
        self.assertEqual(list(target.parent.iterdir()), [target])

    def test_invalid_monthly_files_trigger_daily_fallback(self):
        original = download_month
        for problem in ('http', 'missing_day', 'missing_hour', 'duplicate', 'point', 'units', 'nan'):
            with self.subTest(problem=problem):
                def broken(*args):
                    if problem == 'http':
                        raise RuntimeError('503 exhausted')
                    paths = original(*args)
                    if problem == 'missing_day':
                        return paths[:-1]
                    if problem == 'duplicate':
                        return paths + paths[:1]
                    with xr.open_dataset(paths[0], engine='h5netcdf') as ds:
                        ds = ds.load()
                    if problem == 'point':
                        ds = ds.assign_coords(lat=[40.1])
                    elif problem == 'units':
                        ds.TQV.attrs['units'] = 'wrong'
                    elif problem == 'missing_hour':
                        ds = ds.isel(time=slice(1, None))
                    else:
                        ds.TQV.values[0, 0, 0] = np.nan
                    ds.to_netcdf(paths[0], engine='h5netcdf')
                    return paths
                self.download.side_effect = broken
                calls = []
                def daily(station, product, day):
                    calls.append((product, day))
                    path = self.root / 'fixture.nc'
                    fixture(path, product, f'{day:%Y-%m-%d}')
                    return merra._read_subset(path, station, product, day)
                with patch.object(merra, '_daily_subset', side_effect=daily):
                    result = merra.load_merra_data(BON, '2024-01-16T01:00', '2024-01-16T02:00')
                self.assertEqual(len(calls), 2)
                self.assertEqual(len(result), 24)
                self.assertFalse(list((self.root / 'monthly').rglob('*.nc')))

    def test_year_edges_and_dst_equal_daily_output(self):
        def daily(station, product, day):
            path = self.root / 'fixture.nc'
            fixture(path, product, f'{day:%Y-%m-%d}')
            return merra._read_subset(path, station, product, day)
        for start, end in [('2024-01-01', '2024-01-01'),
                           ('2024-03-10T00:00-06:00', '2024-03-10T23:59-05:00'),
                           ('2024-11-03T00:00-05:00', '2024-11-03T23:59-06:00')]:
            with self.subTest(start=start):
                actual = merra.load_merra_data(BON, start, end)
                with patch.object(merra, '_monthly_subset', side_effect=RuntimeError('fallback')), patch.object(merra, '_daily_subset', side_effect=daily):
                    expected = merra.load_merra_data(BON, start, end)
                pd.testing.assert_frame_equal(actual, expected)
                self.assertEqual(actual.attrs, expected.attrs)
        starts = [c.args[2] for c in self.download.call_args_list]
        self.assertIn('2023-12-01T00:00:00', starts)
        self.assertIn('2024-01-01T00:00:00', starts)

    def test_cross_product_point_mismatch_falls_back(self):
        month = pd.Timestamp('2024-01-01', tz='UTC')
        frames = {p: merra._monthly_subset(BON, p, month) for p in merra.MERRA_PRODUCTS}
        frames['aer'].attrs['grid_point'] = (40.1, -88.125)
        def daily(station, product, day):
            path = self.root / 'fixture.nc'
            fixture(path, product, f'{day:%Y-%m-%d}')
            return merra._read_subset(path, station, product, day)
        with patch.object(merra, '_monthly_subset', side_effect=lambda s,p,m,**kwargs: frames[p]), patch.object(merra, '_daily_subset', side_effect=daily) as fallback:
            result = merra.load_merra_data(BON, '2024-01-16T01:00', '2024-01-16T02:00')
        self.assertEqual(fallback.call_count, 2)
        self.assertEqual(result.attrs['grid_point'], (40., -88.125))

    def test_partial_month_resumes_and_complete_month_is_silent(self):
        month = pd.Timestamp('2024-01-01', tz='UTC')
        merra._monthly_subset(BON, 'slv', month)
        self.download.reset_mock()
        with patch.object(merra, '_daily_subset', side_effect=AssertionError('daily path used')):
            with redirect_stdout(StringIO()) as output:
                first = merra.load_merra_data(BON, '2024-01-16T01:00', '2024-01-16T02:00')
            self.assertIn('MERRA 2024-01 descargado (AER + SLV)', output.getvalue())
            self.assertEqual(self.download.call_count, 1)
            self.assertIn('AER', self.download.call_args.args[0])
            with redirect_stdout(StringIO()) as output:
                cached = merra.load_merra_data(BON, '2024-01-16T01:00', '2024-01-16T02:00')
            self.assertEqual(output.getvalue(), '')
            self.assertEqual(self.download.call_count, 1)
            pd.testing.assert_frame_equal(first, cached)


class MonthlyServiceTests(unittest.TestCase):
    def test_multiple_links_and_sequential_downloads(self):
        links = ['https://example.org/a.nc', 'https://example.org/b.nc']
        result = {'items': [{'type':'DATA', 'link':link} for link in links]}
        with patch.object(merra2, '_subset_rpc', side_effect=[{'Status':'Succeeded'}, result]):
            self.assertEqual(merra2._subset_result_links('job', 'session'), links)
        with patch.object(merra2, 'merra_subset_request', return_value=('job','session')), patch.object(merra2, '_subset_result_links', return_value=links), patch.object(merra2, '_download_link', side_effect=lambda link,path,dataset: path) as download:
            paths = merra2._download_monthly_subsets('dataset', ['v'], 'start', 'end', [0,0,0,0], '/tmp/staging')
            self.assertEqual([c.args[0] for c in download.call_args_list], links)
            self.assertEqual(paths, [Path('/tmp/staging/000.nc'), Path('/tmp/staging/001.nc')])
