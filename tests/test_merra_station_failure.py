"""Station failure limit, cache preservation and batch continuation; no network."""
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import download_merra_usa as batch
from src import merra, merra2
from test_merra import BON, fixture


class StationFailureTests(unittest.TestCase):
    def test_abort_preserves_cache_continues_batch_and_resumes(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            daily_root = root / 'daily'
            cache = daily_root / BON['name']
            cache.mkdir(parents=True)
            paths = []
            for product in merra.MERRA_PRODUCTS:
                path = cache / f"{merra.MERRA_PRODUCTS[product]['dataset_id']}.20240101.SUB.nc"
                fixture(path, product, '2024-01-01')
                paths.append(path)
            saved = {path: path.read_bytes() for path in paths}
            following = {**BON, 'name': 'NEXT'}
            stations = {'BON': BON, 'NEXT': following}
            calls = []
            failing = True

            def download(**kwargs):
                day = kwargs['start'][:10]
                station = Path(kwargs['output_file']).parent.name
                product = 'slv' if 'SLV' in kwargs['dataset_id'] else 'aer'
                calls.append((station, day, product))
                if failing and station == BON['name']:
                    raise RuntimeError('HTTP 503: retries exhausted')
                fixture(kwargs['output_file'], product, day)

            with patch.object(merra, 'MERRA_CACHE_DIR', daily_root), \
                 patch.object(merra, '_monthly_subset', side_effect=RuntimeError('monthly unavailable')), \
                 patch.object(merra2, 'merra_download_subset', side_effect=download), \
                 patch.object(batch, '__file__', str(root / 'download_merra_usa.py')), \
                 patch.object(batch, 'STATIONS_USA', stations), \
                 patch.object(batch, 'start', '2024-01-01T01:00'), \
                 patch.object(batch, 'end', '2024-01-02T03:00'):
                with redirect_stdout(StringIO()) as output:
                    batch.main()
                self.assertEqual([c for c in calls if c[0] == BON['name']],
                                 [(BON['name'], '2024-01-02', 'slv')] * 2)
                self.assertIn('2 descargas diarias fallidas; abortando estación', output.getvalue())
                self.assertIn('Estaciones completadas (1): NEXT', output.getvalue())
                self.assertIn('Estaciones fallidas (1): BON', output.getvalue())
                self.assertFalse((root / 'data/processed/merra/BON').exists())
                self.assertEqual(len(list((root / 'data/processed/merra/NEXT').glob('*.csv'))), 1)
                for path, content in saved.items():
                    self.assertEqual(path.read_bytes(), content)
                self.assertEqual(set(cache.iterdir()), set(paths))

                failing = False
                calls.clear()
                with redirect_stdout(StringIO()):
                    batch.main()
                self.assertEqual(calls, [(BON['name'], '2024-01-02', 'slv'),
                                         (BON['name'], '2024-01-02', 'aer')])
                self.assertEqual(len(list((root / 'data/processed/merra/BON').glob('*.csv'))), 1)
                for path, content in saved.items():
                    self.assertEqual(path.read_bytes(), content)

    def test_success_resets_failure_limit_for_next_subset(self):
        with TemporaryDirectory() as directory:
            calls = {}
            def daily(station, product, day):
                calls[product] = calls.get(product, 0) + 1
                if calls[product] == 1:
                    raise RuntimeError('HTTP retries exhausted')
                path = Path(directory) / f'{product}.nc'
                fixture(path, product, f'{day:%Y-%m-%d}')
                return merra._read_subset(path, station, product, day)
            with patch.object(merra, '_monthly_subset', side_effect=RuntimeError('monthly failed')), \
                 patch.object(merra, '_daily_subset', side_effect=daily), redirect_stdout(StringIO()):
                result = merra.process_merra(BON, '2024-01-01T01:00', '2024-01-01T03:00')
            self.assertEqual(calls, {'slv': 2, 'aer': 2})
            self.assertEqual(len(result), 2)
            self.assertEqual(str(result.index.tz), BON['tz'])
