from contextlib import redirect_stdout
from io import StringIO
import unittest

import pandas as pd

from src.measurements import match_usa_uv_merra


class MatchUSAUVTests(unittest.TestCase):
    def merra(self, timestamps):
        return pd.DataFrame({c: [10. + i for i in range(len(timestamps))]
                             for c in ('o3', 'wv', 'aod', 'alpha')},
                            index=pd.DatetimeIndex(timestamps, tz='UTC'))

    def uv(self, timestamps):
        return pd.DataFrame({'UVB': float('nan'), 'QCuvb': False, 'extra': 7},
                            index=pd.DatetimeIndex(timestamps, tz='UTC', name='Date'))

    def match(self, uv, merra):
        original_uv, original_merra = uv.copy(deep=True), merra.copy(deep=True)
        with redirect_stdout(StringIO()):
            result = match_usa_uv_merra(uv, merra)
        pd.testing.assert_frame_equal(result[uv.columns], uv)
        pd.testing.assert_frame_equal(uv, original_uv)
        pd.testing.assert_frame_equal(merra, original_merra)
        pd.testing.assert_index_equal(result.index, uv.index)
        self.assertEqual(str(result.index.tz), 'UTC')
        return result

    def test_f01_boundaries(self):
        uv = self.uv(['2021-01-01 '+t for t in ('10:00', '10:01', '10:59', '11:00')])
        result = self.match(uv, self.merra(['2021-01-01 10:30', '2021-01-01 11:30']))
        for column in ('o3', 'wv', 'aod', 'alpha'):
            self.assertEqual(result[column].tolist(), [10., 10., 10., 11.])

    def test_f05(self):
        result = self.match(self.uv(pd.date_range('2021-01-01 10:00', periods=12, freq='5min')),
                            self.merra(['2021-01-01 10:30']))
        self.assertTrue((result[['o3', 'wv', 'aod', 'alpha']] == 10.).all().all())

    def test_day_boundary(self):
        result = self.match(self.uv(['2021-01-01 23:55', '2021-01-02 00:00']),
                            self.merra(['2021-01-01 23:30', '2021-01-02 00:30']))
        self.assertEqual(result.o3.tolist(), [10., 11.])

    def test_missing_hour_and_report(self):
        uv = self.uv(['2021-01-01 '+t for t in ('10:00', '11:00', '11:05')])
        with redirect_stdout(StringIO()) as output:
            result = match_usa_uv_merra(uv, self.merra(['2021-01-01 10:30', '2021-01-01 12:30']))
        self.assertTrue(result.iloc[1:][['o3', 'wv', 'aod', 'alpha']].isna().all().all())
        self.assertEqual(result.attrs['merra_unmatched_count'], 2)
        self.assertIn('2 de 3 observaciones sin match', output.getvalue())

    def test_unsorted_and_duplicate_uv_rows_preserved(self):
        result = self.match(self.uv(['2021-01-01 '+t for t in ('11:05', '10:00', '10:00')]),
                            self.merra(['2021-01-01 10:30', '2021-01-01 11:30']))
        self.assertEqual(result.o3.tolist(), [11., 10., 10.])

    def test_reject_naive_and_non_utc_for_both_inputs(self):
        for which in ('UV', 'MERRA'):
            for timezone in (None, 'America/Chicago'):
                with self.subTest(which=which, timezone=timezone):
                    uv, merra = self.uv(['2021-01-01 10:00']), self.merra(['2021-01-01 10:30'])
                    frame = uv if which == 'UV' else merra
                    frame.index = frame.index.tz_localize(None) if timezone is None else frame.index.tz_convert(timezone)
                    with self.assertRaisesRegex(ValueError, which+':.*UTC'):
                        match_usa_uv_merra(uv, merra)

    def test_reject_duplicate_off_center_and_column_collision(self):
        uv = self.uv(['2021-01-01 10:00'])
        for times in (['2021-01-01 10:30'] * 2, ['2021-01-01 10:31']):
            with self.assertRaises(ValueError):
                match_usa_uv_merra(uv, self.merra(times))
        uv['o3'] = 5.
        with self.assertRaisesRegex(ValueError, 'overwrite'):
            match_usa_uv_merra(uv, self.merra(['2021-01-01 10:30']))
