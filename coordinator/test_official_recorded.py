"""Fabricated government/FRED file contents for local parser tests only."""
import hashlib
import json
import pathlib
import tempfile
import unittest
from official_recorded_import import government, fred_v2, ics_time


class OfficialOffline(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=pathlib.Path(self.temp.name)
        self.m=dict(manifestVersion=1,kind='government-official-export',file='UNIT-ONLY.xml',sha256='',format='rss',
                    sourceURL='https://www.federalreserve.gov/feeds/press_all.xml',publicDomainEvidenceReference='UNIT PUBLIC DOMAIN ATTESTATION',thirdPartyContentExcluded=True,
                    capturedUTC='2026-11-10T14:00:00Z',localReceivedUTC='2026-11-10T13:00:00Z',localReceiptEvidence='UNIT RECEIPT')

    def tearDown(self):self.temp.cleanup()

    def run_import(self,raw):
        file=self.root/self.m['file'];file.write_text(raw)
        self.m['sha256']=hashlib.sha256(file.read_bytes()).hexdigest()
        manifest=self.root/'manifest.json';manifest.write_text(json.dumps(self.m))
        return government(manifest)

    def test_official_news_stays_partial_no_false_completeness(self):
        result=self.run_import('<rss><channel><item><guid>UNIT-1</guid><title>Fabricated unit title</title><pubDate>Tue, 10 Nov 2026 12:00:00 GMT</pubDate></item></channel></rss>')
        self.assertTrue(result['partialScope']);self.assertFalse(result['eligibleForUltimate']);self.assertFalse(result['continuityVerified'])
        self.assertEqual(result['events'][0]['availableUTC'],'2026-11-10T13:00:00.000Z')
        self.assertEqual(result['events'][0]['impact'],'UNCLASSIFIED')
        self.assertFalse(result['networkEnabled'])

    def test_atom_updated_cannot_replace_publication(self):
        self.m['format']='atom'
        with self.assertRaisesRegex(ValueError,'Original publication'):
            self.run_import('<feed xmlns="http://www.w3.org/2005/Atom"><entry><id>UNIT</id><updated>2026-11-10T12:00:00Z</updated></entry></feed>')
        result=self.run_import('<feed xmlns="http://www.w3.org/2005/Atom"><entry><id>UNIT</id><published>2026-11-10T12:00:00Z</published><title>UNIT</title></entry></feed>')
        self.assertEqual(len(result['events']),1)

    def test_news_duplicates_future_and_unofficial_source(self):
        item='<item><guid>UNIT</guid><pubDate>Tue, 10 Nov 2026 12:00:00 GMT</pubDate></item>'
        with self.assertRaisesRegex(ValueError,'Duplicate'):self.run_import('<rss><channel>'+item+item+'</channel></rss>')
        with self.assertRaisesRegex(ValueError,'arrival order'):self.run_import('<rss><channel>'+item.replace('12:00:00','15:00:00')+'</channel></rss>')
        self.m['sourceURL']='https://example.com/fake.gov'
        with self.assertRaises(ValueError):self.run_import('<rss/>')

    def test_known_future_schedule_needs_actual_publication_evidence(self):
        self.m['format']='ics';self.m['sourceURL']='https://www.bls.gov/schedule/news_release/bls.ics'
        raw='BEGIN:VCALENDAR\nBEGIN:VEVENT\nUID:UNIT\nDTSTAMP:20000101T000000Z\nDTSTART;TZID=America/New_York:20261112T083000\nSUMMARY:UNIT\nEND:VEVENT\nEND:VCALENDAR\n'
        with self.assertRaisesRegex(ValueError,'publication evidence'):self.run_import(raw)
        self.m['publications']={'UNIT':dict(publishedUTC='2026-11-09T12:00:00Z',evidenceReference='UNIT PUBLICATION')}
        result=self.run_import(raw)
        self.assertEqual(result['events'][0]['timeUTC'],'2026-11-12T13:30:00.000Z')
        self.assertFalse(result['eligibleForUltimate'])

    def test_dst_ambiguity_floating_and_recurrence_rejected(self):
        for value in ('20261101T013000','20260308T023000'):
            with self.assertRaisesRegex(ValueError,'DST'):ics_time('DTSTART;TZID=America/New_York',value)
        with self.assertRaises(ValueError):ics_time('DTSTART','20261112T083000')
        self.m['format']='ics'
        with self.assertRaisesRegex(ValueError,'Recurring'):
            self.run_import('BEGIN:VEVENT\nUID:UNIT\nDTSTART:20261112T130000Z\nRRULE:FREQ=DAILY\nEND:VEVENT\n')

    def test_fred_v2_explicit_reference_and_release_times(self):
        file=self.root/'UNIT-FRED.csv';file.write_text('observation_date,DGS2\n2026-11-06,4.1\n2026-11-09,4.2\n')
        timing={date:dict(observedUTC=date+'T20:30:00Z',availableUTC=date+'T21:15:00Z',evidenceReference='UNIT RECEIPT') for date in ('2026-11-06','2026-11-09')}
        side=dict(sha256=hashlib.sha256(file.read_bytes()).hexdigest(),series='DGS2',rightsStatus='PUBLIC_DOMAIN_CITATION_REQUESTED',sourceReference='https://fred.stlouisfed.org/series/DGS2',
                  publicDomainEvidenceReference='FABRICATED UNIT ATTESTATION',capturedUTC='2026-11-10T12:00:00Z',observations=timing)
        path=self.root/'sidecar.json';path.write_text(json.dumps(side))
        with self.assertRaisesRegex(ValueError,'vintage'):fred_v2(file,path)
        timing['2026-11-09']['referenceVintage']=dict(value=4.05,observationDate='2026-11-06',observedUTC='2026-11-06T20:30:00Z',availableUTC='2026-11-06T21:15:00Z',evidenceReference='UNIT AS-KNOWN REFERENCE')
        timing['2026-11-09']['releaseSchedule']=dict(nextExpectedReleaseUTC='2026-11-10T21:15:00Z',availableUTC='2026-11-08T12:00:00Z',evidenceReference='UNIT SCHEDULE')
        path.write_text(json.dumps(side));out=fred_v2(file,path)
        row=out['records']['US02Y'][0]
        self.assertEqual(row['previous'],4.05)  # explicit as-known vintage, not revised CSV 4.1
        self.assertEqual(row['availableUTC'],'2026-11-09T21:15:00Z')
        self.assertEqual(row['role'],'DAILY_CONTEXT');self.assertFalse(out['networkEnabled'])
        timing['2026-11-09']['releaseSchedule']['availableUTC']='2026-11-11T12:00:00Z'
        path.write_text(json.dumps(side))
        with self.assertRaisesRegex(ValueError,'Future receipt'):fred_v2(file,path)
