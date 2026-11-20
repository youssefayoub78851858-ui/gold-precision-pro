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
