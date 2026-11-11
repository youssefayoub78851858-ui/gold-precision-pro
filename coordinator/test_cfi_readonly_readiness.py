import json
import pathlib
import unittest

from cfi_readonly_readiness import readiness


ROOT = pathlib.Path(__file__).resolve().parents[1]


class CFIReadiness(unittest.TestCase):
    def test_source_remains_off_until_official_confirmation(self):
        data = readiness()
        self.assertEqual(data['status'], 'AWAITING_OFFICIAL_CFI_CONFIRMATION')
        self.assertFalse(data['instrumentConfirmed'])
        self.assertFalse(data['readOnlyApiConfirmed'])
        self.assertFalse(data['closedM15H1H4Confirmed'])
        self.assertFalse(data['renderCloudUseConfirmed'])
        self.assertFalse(data['costAndTermsConfirmed'])
        self.assertFalse(data['enabled'])
        self.assertEqual(data['networkRequests'], 0)
        self.assertEqual(data['signal'], 'WAIT')
        self.assertFalse(data['executable'])

    def test_saved_readiness_has_no_credentials_or_requests(self):
        inventory = json.loads((ROOT / 'research/results/connector-readiness.json').read_text())
        source = inventory['XAUUSD_CFI_MT5']
        self.assertFalse(source['enabled'])
        self.assertFalse(source['networkImplemented'])
        self.assertFalse(source['credentialConfigured'])
        self.assertEqual(source['requestsSent'], 0)

        inquiry = json.loads((ROOT / 'research/results/ultimate-source-inventory.json').read_text())
        record = next(item for item in inquiry['sources'] if item['layer'] == 'XAUUSD_CFI_MT5')
        self.assertTrue(record['supportInquiry']['approved'])
        self.assertTrue(record['supportInquiry']['sent'])
        self.assertTrue(record['supportInquiry']['messageId'])
        self.assertFalse(record['networkEnabled'])
        self.assertEqual(record['requestsSent'], 0)


if __name__ == '__main__':
    unittest.main()
