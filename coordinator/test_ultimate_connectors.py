import unittest
from ultimate_connectors import plan, snapshot, validate


class OfflineConnectors(unittest.TestCase):
    def test_disabled_and_no_requests(self):
        for spec in plan().values():
            self.assertFalse(spec['enabled'])
            self.assertFalse(spec['networkImplemented'])
            self.assertEqual(spec['requestsSent'], 0)

    def test_arrival_cutoff_and_entitlements(self):
        record = dict(mode='recorded',source='Licensed archived export',instrument='DXY',entitlementVerified=True,observedUTC='2026-09-01T12:00:00Z',availableUTC='2026-09-01T12:01:00Z',previous=100,value=99)
        self.assertEqual(snapshot({'DXY':[record]}, '2026-09-01T12:00:00Z'), {})
        self.assertEqual(snapshot({'DXY':[record]}, '2026-09-01T12:01:00Z')['DXY'], record)
        with self.assertRaises(ValueError):
            validate('DXY', {**record, 'entitlementVerified':False})
        with self.assertRaises(ValueError):
            validate('DXY', {**record, 'instrument':'GC'})
        with self.assertRaises(ValueError):
            validate('DXY', {**record, 'availableUTC':'2026-09-01T11:59:00Z'})

    def test_future_news_publication_rejected(self):
        record = dict(mode='recorded',source='Archived calendar',instrument='USD_EVENTS',entitlementVerified=True,observedUTC='2026-09-01T12:00:00Z',availableUTC='2026-09-01T12:01:00Z',events=[dict(timeUTC='2026-09-01T13:00:00Z',publishedUTC='2026-09-01T12:02:00Z',impact='high')],coverageStartUTC='2026-09-01T11:00:00Z',coverageEndUTC='2026-09-01T14:00:00Z')
        with self.assertRaises(ValueError):
            validate('calendar',record)
        record['events'][0]['publishedUTC']='2026-09-01T11:00:00Z'
        self.assertEqual(validate('calendar',record),record)

    def test_calendar_release_leakage_and_point_in_time_snapshot(self):
        # At 12:01 the schedule is known, not the 13:00 release actual.
        event = dict(timeUTC='2026-09-01T13:00:00Z',
                     publishedUTC='2026-09-01T11:00:00Z', impact='high')
        base = dict(mode='recorded', source='Offline test export',
                    instrument='USD_EVENTS', entitlementVerified=True,
                    observedUTC='2026-09-01T12:00:00Z',
                    availableUTC='2026-09-01T12:01:00Z',
                    events=[event], coverageStartUTC='2026-09-01T11:00:00Z',
                    coverageEndUTC='2026-09-01T14:00:00Z')
        self.assertEqual(snapshot({'calendar': [base]},
                                  '2026-09-01T12:00:00Z'), {})
        self.assertEqual(snapshot({'calendar': [base]},
                                  '2026-09-01T12:01:00Z')['calendar'], base)
        for field, value in (
            ('actual', 0), ('actualValue', 3.5),
            ('actual_value', 3.5), ('surprise', -0.5),
            ('surpriseValue', 1), ('surprise_value', 1),
            ('revisedActual', 4), ('status', 'RELEASED'),
            ('status', 'completed'),
        ):
            with self.subTest(field=field, value=value):
                invalid = {**base, 'events': [{**event, field: value}]}
                with self.assertRaises(ValueError):
                    validate('calendar', invalid)
        self.assertEqual(validate('calendar', {
            **base, 'events': [{**event, 'actual': None}]
        })['events'][0]['actual'], None)
        after = {**base, 'observedUTC': '2026-09-01T13:00:00Z',
                 'availableUTC': '2026-09-01T13:01:00Z',
                 'events': [{**event, 'actual': 3.5, 'surprise': 0.5}]}
        self.assertEqual(validate('calendar', after), after)
        self.assertEqual(snapshot({'calendar': [after]},
                                  '2026-09-01T12:59:59Z'), {})
