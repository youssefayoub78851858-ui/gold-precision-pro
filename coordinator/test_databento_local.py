"""Fabricated raw records in temporary files only. No Databento account or network."""
import copy
import csv
import io
import hashlib
import json
import pathlib
import subprocess
import tempfile
import unittest
from databento_gc_import import convert
from databento_cost_preflight import assess
from recorded_utils import ns, iso_ms, iso_ns


class LocalDatabento(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=pathlib.Path(self.temp.name)
        event=ns('2026-11-10T12:00:01.123456789Z')
        self.rows=[dict(ts_event=str(event),ts_recv=str(event+1000),publisher_id=1,instrument_id=12345,sequence=100,flags=128,rtype=0,action='T',side='B',price=100000000000,size=2),
                   dict(ts_event=str(event+1000000000),ts_recv=str(event+1000001000),publisher_id=1,instrument_id=12345,sequence=105,flags=128,rtype=0,action='T',side='A',price=101000000000,size=3)]
        self.m=dict(manifestVersion=1,kind='databento-gc-trades',file='FAKE-UNIT.json',sha256='',dataset='GLBX.MDP3',schema='trades',format='json',
                    availabilityBasis='ACTUAL_LOCAL_RECEIPT',accessClass='HISTORICAL_T_PLUS_1',timestampEncoding='UNIX_NS',priceEncoding='FIXED_1E9',targetContract='GCZ2026',
                    capturedUTC='2026-11-12T12:00:00Z',localReceivedUTC='2026-11-12T11:00:00.000000001Z',localReceiptEvidence='UNIT RECEIPT ONLY',
                    rights=dict(status='VERIFIED_INTERNAL_RESEARCH',algorithmicResearchAuthorized=True,evidenceReference='FABRICATED UNIT ATTESTATION'),
                    instrumentMappings=[dict(publisher_id=1,instrument_id=12345,venue='COMEX',instrumentClass='F',rawSymbol='GCZ6',contract='GCZ2026',
                                             validFromUTC='2026-01-01T00:00:00Z',validUntilUTC='2026-12-20T00:00:00Z',contractExpiryUTC='2026-12-20T00:00:00Z',
                                             mappingAvailableUTC='2026-11-12T10:00:00Z',evidenceReference='UNIT MAPPING')],
                    windows=[dict(startUTC='2026-11-10T12:00:00Z',endUTC='2026-11-10T12:01:00Z',continuity=dict(status='VERIFIED_COMPLETE',sequenceGapCount=0,evidenceReference='UNIT QUALITY',availableUTC='2026-11-12T11:00:00Z'))])

    def tearDown(self):self.temp.cleanup()

    def run_import(self):
        file=self.root/self.m['file']
        if self.m['format']=='csv':
            stream=io.StringIO();writer=csv.DictWriter(stream,fieldnames=list(self.rows[0]));writer.writeheader();writer.writerows(self.rows);file.write_text(stream.getvalue())
        elif self.m['format']=='jsonl':file.write_text('\n'.join(json.dumps(row) for row in self.rows))
        else:file.write_text(json.dumps(self.rows))
        self.m['sha256']=hashlib.sha256(file.read_bytes()).hexdigest()
        manifest=self.root/'manifest.json';manifest.write_text(json.dumps(self.m))
        return convert(manifest)

    def test_exact_ns_price_side_and_actual_receipt(self):
        out=self.run_import()
        self.assertEqual(out['normalizedTrades'][0]['marketUTC'],'2026-11-10T12:00:01.123456789Z')
        self.assertEqual(out['normalizedTrades'][0]['priceUSD'],'100')
        self.assertEqual(out['windowReports'][0]['buyVolume'],2)
        self.assertEqual(out['windowReports'][0]['sellVolume'],3)
        self.assertEqual(len(out['feeds']['orderFlow']),1)
        # 100 -> 105 is not automatically a channel gap in a filtered trades export.
        self.assertEqual(out['windowReports'][0]['blockers'],[])
        flow=out['feeds']['orderFlow'][0]
        self.assertEqual(flow['availableUTC'],'2026-11-12T11:00:00.001Z')
        self.assertFalse(out['executable']);self.assertFalse(out['networkEnabled'])
        script="const c=require(process.argv[1]);let s='';process.stdin.on('data',x=>s+=x).on('end',()=>console.log(JSON.stringify(c.assessLayer('orderFlow',JSON.parse(s),'2026-11-10T12:01:00Z'))))"
        result=subprocess.run(['node','-e',script,str(pathlib.Path(__file__).with_name('ultimate_v2_contracts.js'))],input=json.dumps(flow),text=True,capture_output=True,check=True)
        self.assertEqual(json.loads(result.stdout)['reason'],'NOT_AVAILABLE_AT_DECISION')

    def test_unknown_side_preserved_and_never_inferred(self):
        self.rows[0]['side']='N';out=self.run_import()
        self.assertEqual(out['windowReports'][0]['unknownVolume'],2)
        self.assertEqual(out['feeds']['orderFlow'],[])
        self.assertEqual(len(out['feeds']['GC']),1)
        self.assertEqual(out['normalizedTrades'][0]['aggressor'],'UNKNOWN')

    def test_gap_and_missing_coverage_block_even_consecutive_sequence(self):
        self.rows[1]['sequence']=101
        self.m['windows'][0]['continuity']['status']='UNKNOWN'
        out=self.run_import();self.assertFalse(out['feeds']['orderFlow'])
        self.m['windows'][0]['continuity']['status']='VERIFIED_COMPLETE'
        self.m['windows'][0]['continuity']['sequenceGapCount']=1
        self.assertFalse(self.run_import()['feeds']['GC'])

    def test_flag_clock_and_duplicate_quarantine(self):
        for flag,reason in [(4,'CHANNEL_GAP_FLAG'),(8,'BAD_TS_RECV'),(32,'SNAPSHOT_TRADE_UNREVIEWED'),(2,'PUBLISHER_FLAG_UNREVIEWED')]:
            self.rows[0]['flags']=128|flag
            out=self.run_import()
            self.assertFalse(out['feeds']['orderFlow']);self.assertIn(reason,out['windowReports'][0]['blockers'])
        self.rows[0]['flags']=128
        self.rows.append(copy.deepcopy(self.rows[-1]))
        self.assertIn('DUPLICATE_OR_AMBIGUOUS_TRADE',self.run_import()['windowReports'][0]['blockers'])

    def test_clock_order_mapping_and_contract_mismatch(self):
        self.rows[0]['ts_recv']=str(int(self.rows[0]['ts_event'])-1)
        self.assertIn('CLOCK_ORDER',self.run_import()['windowReports'][0]['blockers'])
        self.rows[0]['ts_recv']=str(int(self.rows[0]['ts_event'])+1000)
        self.m['instrumentMappings'][0]['contract']='GCG2027';self.m['instrumentMappings'][0]['rawSymbol']='GCG7'
        self.assertIn('CONTRACT_MISMATCH',self.run_import()['windowReports'][0]['blockers'])
        self.m['instrumentMappings'].append(copy.deepcopy(self.m['instrumentMappings'][0]))
        with self.assertRaisesRegex(ValueError,'ambiguous'):self.run_import()

    def test_no_implicit_units_sides_or_market_access(self):
        self.m['priceEncoding']='GUESS'
        with self.assertRaises(ValueError):self.run_import()
        self.m['priceEncoding']='FIXED_1E9';self.rows[0]['ts_event']=1.0e18
        with self.assertRaises(ValueError):self.run_import()
        self.rows[0]['ts_event']='18446744073709551615'
        with self.assertRaises(ValueError):self.run_import()
        self.rows[0]['ts_event']=str(ns('2026-11-10T12:00:01Z'));self.rows[0]['action']='F'
        with self.assertRaises(ValueError):self.run_import()

    def test_rights_block_and_millisecond_rounding(self):
        self.m['rights']['algorithmicResearchAuthorized']=False
        with self.assertRaisesRegex(ValueError,'QUARANTINED'):self.run_import()
        value=ns('2026-11-10T12:00:00.000000001Z')
        self.assertEqual(iso_ms(value),'2026-11-10T12:00:00.000Z')
        self.assertEqual(iso_ms(value,ceil=True),'2026-11-10T12:00:00.001Z')
        self.assertEqual(iso_ns(value),'2026-11-10T12:00:00.000000001Z')

    def test_cost_quote_is_never_spending_authorization(self):
        quote=dict(dataset='GLBX.MDP3',schema='trades',symbols=['GCZ6'],startUTC='2026-10-01T00:00:00Z',endUTC='2026-10-02T00:00:00Z',quotedUTC='2026-11-10T00:00:00Z',evidenceReference='FABRICATED QUOTE',currency='USD',estimatedDataUSD='2.50',licenseUSD='0',otherFeesUSD='0',taxUSD=None,eligibleCreditsUSD=None)
        self.assertIsNone(assess(quote)['estimatedCashUSD'])
        quote.update(taxUSD='0',eligibleCreditsUSD='2.00')
        out=assess(quote);self.assertEqual(out['estimatedCashUSD'],'0.50');self.assertFalse(out['approvedToSpend'])
        quote['estimatedDataUSD']='NaN'
        with self.assertRaises(ValueError):assess(quote)
        quote['estimatedDataUSD']='2.50';quote['endUTC']='2026-11-10T00:00:00Z'
        with self.assertRaises(ValueError):assess(quote)

    def test_canonical_csv_iso_ns_and_jsonl(self):
        self.m.update(format='csv',timestampEncoding='ISO8601_NS',priceEncoding='DECIMAL_USD')
        for i,row in enumerate(self.rows):
            row['ts_event']=iso_ns(int(row['ts_event']));row['ts_recv']=iso_ns(int(row['ts_recv']));row['price']=str(100+i)
        out=self.run_import()
        self.assertEqual(out['normalizedTrades'][0]['marketUTC'],'2026-11-10T12:00:01.123456789Z')
        self.assertEqual(out['windowReports'][0]['knownSideVolumePct'],100)
        self.m['format']='jsonl'
        self.assertEqual(self.run_import()['feeds'],out['feeds'])

    def test_recent_capture_cannot_be_called_historical(self):
        self.m['capturedUTC']='2026-11-10T13:00:00Z'
        self.m['localReceivedUTC']='2026-11-10T12:01:00Z'
        with self.assertRaisesRegex(ValueError,r'T\+1'):
            self.run_import()

    def test_contract_cannot_be_relabelled_by_mapping(self):
        self.m['instrumentMappings'][0]['rawSymbol']='GCG7'
        with self.assertRaisesRegex(ValueError,'contract disagree'):self.run_import()

    def test_windows_sorted_by_actual_quality_availability_without_retiming(self):
        more=copy.deepcopy(self.rows)
        for row in more:
            row['ts_event']=str(int(row['ts_event'])+60*10**9)
            row['ts_recv']=str(int(row['ts_recv'])+60*10**9)
            row['sequence']+=100
        self.rows+=more
        later=copy.deepcopy(self.m['windows'][0])
        later.update(startUTC='2026-11-10T12:01:00Z',endUTC='2026-11-10T12:02:00Z')
        self.m['windows'][0]['continuity']['availableUTC']='2026-11-12T11:30:00Z'
        later['continuity']['availableUTC']='2026-11-12T11:15:00Z'
        self.m['windows'].append(later)
        out=self.run_import()
        arrivals=[row['availableUTC'] for row in out['feeds']['orderFlow']]
        self.assertEqual(arrivals,['2026-11-12T11:15:00.000Z','2026-11-12T11:30:00.000Z'])
        self.assertEqual(out['feeds']['orderFlow'][0]['observedUTC'],'2026-11-10T12:02:00.000Z')
