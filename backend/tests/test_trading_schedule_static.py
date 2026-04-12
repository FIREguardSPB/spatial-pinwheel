import unittest
from datetime import datetime, timezone

from core.services import trading_schedule


class TradingScheduleStaticTests(unittest.TestCase):
    def setUp(self):
        trading_schedule._CACHE.update({
            'source': 'static',
            'exchange': 'MOEX',
            'days': {},
            'error': None,
            'warning': 'broker schedule unavailable',
            'fetched_at': 1.0,
        })

    def test_static_snapshot_has_msk_session_window(self):
        snap = trading_schedule.get_schedule_snapshot(now=datetime(2026, 4, 1, 9, 0, tzinfo=timezone.utc))
        self.assertEqual(snap['source'], 'static')
        self.assertEqual(snap['exchange'], 'MOEX')
        self.assertEqual(snap['timezone'], 'Europe/Moscow')
        self.assertIsNotNone(snap['current_session_start'])
        self.assertIsNotNone(snap['current_session_end'])
        self.assertIsNotNone(snap['trading_day'])

    def test_static_next_open_from_thursday_points_to_friday(self):
        snap = trading_schedule.get_schedule_snapshot(now=datetime(2026, 4, 2, 13, 0, tzinfo=timezone.utc))
        self.assertEqual(snap['trading_day'], '2026-04-02')
        self.assertEqual(snap['next_open'], '2026-04-03T09:50:00+03:00')

    def test_static_holiday_map_for_2026_is_respected(self):
        holiday = trading_schedule.get_schedule_snapshot(now=datetime(2026, 5, 1, 9, 0, tzinfo=timezone.utc))
        self.assertFalse(holiday['is_trading_day'])
        self.assertEqual(holiday['next_open'], '2026-05-04T09:50:00+03:00')



    def test_static_snapshot_hides_broker_error_and_keeps_warning(self):
        snap = trading_schedule.get_schedule_snapshot(now=datetime(2026, 4, 2, 13, 0, tzinfo=timezone.utc))
        self.assertIsNone(snap.get('error'))
        self.assertEqual(snap.get('warning'), 'broker schedule unavailable')

    def test_broker_snapshot_with_absurd_monday_jump_is_corrected_by_static_guard(self):
        trading_schedule._CACHE.update({
            'source': 'broker',
            'exchange': 'MOEX',
            'days': {
                '2026-04-02': {
                    'date': '2026-04-02',
                    'is_trading_day': True,
                    'day_start': datetime(2026, 4, 2, 6, 50, tzinfo=timezone.utc),
                    'day_end': datetime(2026, 4, 2, 15, 59, 59, tzinfo=timezone.utc),
                },
                '2026-04-06': {
                    'date': '2026-04-06',
                    'is_trading_day': True,
                    'day_start': datetime(2026, 4, 6, 6, 50, tzinfo=timezone.utc),
                    'day_end': datetime(2026, 4, 6, 15, 59, 59, tzinfo=timezone.utc),
                },
            },
            'warning': None,
        })
        snap = trading_schedule.get_schedule_snapshot(now=datetime(2026, 4, 2, 12, 0, tzinfo=timezone.utc))
        self.assertEqual(snap['next_open'], '2026-04-03T09:50:00+03:00')
        self.assertEqual(snap.get('warning'), 'broker next_open corrected by static guard')


if __name__ == '__main__':
    unittest.main()
