import unittest
from unittest.mock import patch
import numpy as np
import pandas as pd
import pvlib
from config import STATIONS_USA
from src.clearsky import add_usa_clearsky
from src.measurements import regularize_usa_uv


class USAClearskyTests(unittest.TestCase):
    def data(self, freq='1min'):
        index = pd.date_range('2021-06-01', periods=1440 if freq == '1min' else 288, freq=freq, tz='UTC')
        return pd.DataFrame({'GHI': 500., 'UVB': np.nan, 'QCghi': False, 'extra': 1}, index=index)

    def test_f01_preserves_input_and_solar_convention(self):
        df = self.data()
        original = df.copy()
        station = STATIONS_USA['ABQ']
        result = add_usa_clearsky(df, station)
        pd.testing.assert_frame_equal(result[df.columns], original)
        pd.testing.assert_frame_equal(df, original)
        pd.testing.assert_index_equal(result.index, df.index)
        solar = pvlib.solarposition.get_solarposition(df.index, station['lat'], station['lon'], altitude=station['elevation'])
        np.testing.assert_array_equal(result.sza, solar.zenith)
        self.assertTrue((result.ghi_clear >= 0).all())
        self.assertEqual(result.clear_sky.dtype, bool)
        reference = result.ghi_clear
        df['GHI'] = reference
        detected = add_usa_clearsky(df, station)
        self.assertTrue(detected.clear_sky.any())

    def test_missing_sentinel_only_masked_for_detection(self):
        df = self.data()
        df.loc[df.index[:3], 'GHI'] = [-9999.9, -1., np.nan]
        with patch('src.clearsky.pv.clearsky.detect_clearsky', return_value=pd.Series(False, index=df.index)) as detect:
            result = add_usa_clearsky(df, STATIONS_USA['ABQ'])
        measured = detect.call_args.args[0]
        self.assertTrue(pd.isna(measured.iloc[0]))
        self.assertEqual(measured.iloc[1], -1.)
        self.assertTrue(pd.isna(measured.iloc[2]))
        pd.testing.assert_frame_equal(result[df.columns], df)

    def test_f05_uses_inferred_limits_at_native_cadence(self):
        df = self.data('5min')
        original_detect = pvlib.clearsky.detect_clearsky
        with patch('src.clearsky.pv.clearsky.detect_clearsky', wraps=original_detect) as detect:
            result = add_usa_clearsky(df, STATIONS_USA['BON'])
        self.assertTrue(detect.call_args.kwargs['infer_limits'])
        pd.testing.assert_frame_equal(result[df.columns], df)
        pd.testing.assert_index_equal(result.index, df.index)
        self.assertEqual(result.clear_sky.dtype, bool)
        self.assertTrue((result.ghi_clear >= 0).all())

    def test_gaps_and_non_utc_are_rejected(self):
        df = self.data()
        for invalid in (df.drop(df.index[10]), df.tz_convert('America/Denver'), df.tz_localize(None)):
            with self.assertRaises(ValueError):
                add_usa_clearsky(invalid, STATIONS_USA['ABQ'])

    def test_regularized_gaps_are_nan_and_clearsky_accepts_them(self):
        for resolution, freq in [('f01', '1min'), ('f05', '5min')]:
            with self.subTest(resolution=resolution):
                full = self.data(freq)
                absent = full.index[20]
                df = full.drop(absent)
                original = df.copy(deep=True)
                regular = regularize_usa_uv(df, resolution)
                self.assertTrue(regular.loc[absent].isna().all())
                pd.testing.assert_index_equal(regular.index, full.index)
                pd.testing.assert_frame_equal(regular.loc[df.index], df, check_dtype=False)
                pd.testing.assert_frame_equal(df, original)
                result = add_usa_clearsky(regular, STATIONS_USA['ABQ'])
                pd.testing.assert_frame_equal(result[regular.columns], regular)
                self.assertEqual(result.clear_sky.dtype, bool)
                self.assertFalse(result.loc[absent, 'clear_sky'])

    def test_regularize_rejects_duplicate_off_grid_and_non_utc(self):
        df = self.data()
        for invalid in (pd.concat([df, df.iloc[:1]]), df.tz_localize(None)):
            with self.assertRaises(ValueError):
                regularize_usa_uv(invalid, 'f01')
        with self.assertRaises(ValueError):
            regularize_usa_uv(df, 'f05')
