from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import pandas as pd

from src.measurements import load_usa_uv, clean_usa_uv


class USAUVTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'abq').mkdir()

    def write(self, suffix, value=0.001):
        frame = pd.DataFrame({'UVB': [value, -9.9999, float('nan')],
                              'QCuvb': [True, False, False]},
                             index=pd.date_range('2021-01-01', periods=3,
                                                 freq='1min' if suffix.lower() == 'f01' else '5min'))
        frame.to_csv(self.root / 'abq' / f'abq_UVdata_{suffix}.csv')
        return frame

    def test_f01_preserves_values_flags_and_localizes_utc(self):
        expected = self.write('f01')
        frame, resolution = load_usa_uv('ABQ', self.root)
        self.assertEqual(resolution, 'f01')
        self.assertEqual(str(frame.index.tz), 'UTC')
        pd.testing.assert_frame_equal(frame.tz_localize(None), expected, check_freq=False)

    def test_f05_without_interpolation(self):
        expected = self.write('f05')
        frame, resolution = load_usa_uv('ABQ', self.root)
        self.assertEqual(resolution, 'f05')
        self.assertEqual(str(frame.index.tz), 'UTC')
        pd.testing.assert_frame_equal(frame.tz_localize(None), expected, check_freq=False)
        self.assertEqual(len(frame), 3)

    def test_prefer_f01(self):
        self.write('f05', 0.005)
        self.write('f01', 0.001)
        frame, resolution = load_usa_uv('ABQ', self.root)
        self.assertEqual(resolution, 'f01')
        self.assertEqual(frame.UVB.iloc[0], 0.001)

    def test_uppercase_variant_precedes_f05(self):
        self.write('F01')
        self.write('f05')
        self.assertEqual(load_usa_uv('ABQ', self.root)[1], 'f01')

    def test_missing_files(self):
        with self.assertRaises(FileNotFoundError) as error:
            load_usa_uv('ABQ', self.root)
        for text in ('ABQ', 'abq_UVdata_f01.csv', 'abq_UVdata_f05.csv'):
            self.assertIn(text, str(error.exception))

    def test_invalid_preferred_file_does_not_silently_fall_back(self):
        self.write('f05')
        path = self.root / 'abq/abq_UVdata_f01.csv'
        path.write_text(',UVB\nnot-a-date,1\n')
        with self.assertRaises(ValueError):
            load_usa_uv('ABQ', self.root)


class CleanUSAUVTests(unittest.TestCase):
    def test_only_sentinel_changes_for_both_resolutions(self):
        for resolution, flag, freq in [('f01', 'QCuvb', '1min'), ('f05', 'MSK', '5min')]:
            with self.subTest(resolution=resolution):
                df = pd.DataFrame({'UVB': [-9.9999, 0.0, 0.004, -0.0001, float('nan')],
                                   flag: [False, True, False, False, True],
                                   'GHI': [-9.9999, 1, 2, 3, 4]},
                                  index=pd.date_range('2021-01-01', periods=5, freq=freq, tz='UTC'))
                original = df.copy(deep=True)
                expected = df.copy(deep=True)
                expected.iloc[0, 0] = float('nan')
                result = clean_usa_uv(df, resolution)
                pd.testing.assert_frame_equal(result, expected)
                pd.testing.assert_frame_equal(df, original)
                pd.testing.assert_frame_equal(clean_usa_uv(result, resolution), expected)

    def test_unknown_resolution_raises(self):
        with self.assertRaisesRegex(ValueError, 'resolution'):
            clean_usa_uv(pd.DataFrame({'UVB': [-9.9999]}), 'f60')
