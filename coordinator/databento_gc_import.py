"""Offline canonical Databento trades CSV/JSONL/JSON importer. No SDK or market client."""
import argparse
import csv
from decimal import Decimal, InvalidOperation
import io
import json
import re
from recorded_utils import ns, iso_ns, iso_ms, pinned_file, rights, validate_v2


def integer(value):
    if isinstance(value,bool) or not re.fullmatch(r'[0-9]+',str(value)):
        raise ValueError('Exact nonnegative integer required')
    return int(value)


def convert(path):
    m, raw = pinned_file(path,'databento-gc-trades')
    r = rights(m)
    if m.get('dataset') != 'GLBX.MDP3' or m.get('schema') != 'trades' or m.get('availabilityBasis') != 'ACTUAL_LOCAL_RECEIPT' or m.get('accessClass')!='HISTORICAL_T_PLUS_1':
        raise ValueError('GLBX.MDP3 trades with actual local receipt required')
    if m.get('timestampEncoding') not in ('UNIX_NS','ISO8601_NS') or m.get('priceEncoding') not in ('FIXED_1E9','DECIMAL_USD'):
        raise ValueError('Explicit timestamp and price encodings required')
    if not re.fullmatch(r'GC[FGHJKMNQUVXZ]\d{4}',m.get('targetContract','')):
        raise ValueError('Dated GC contract required; no continuous/spread/spot aliases')
    captured = ns(m['capturedUTC'])
    batch_received = ns(m['localReceivedUTC'])
    if batch_received > captured or not m.get('localReceiptEvidence'):
        raise ValueError('Actual local-receipt evidence missing or future')
    if m['format'] == 'csv':
        source = list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))))
    elif m['format'] == 'jsonl':
        source = [json.loads(line) for line in raw.decode().splitlines() if line.strip()]
    elif m['format'] == 'json':
        source = json.loads(raw)
    else:
        raise ValueError('Use canonical local CSV/JSONL/JSON; DBN decoding is not performed here')
    if not isinstance(source,list):
        raise ValueError('Trade array required')
    rows, seen = [], set()
    last_recv = None
    for row in source:
        event, recv = ns(row['ts_event'],m['timestampEncoding']), ns(row['ts_recv'],m['timestampEncoding'])
        if event>captured-86400*10**9:raise ValueError('Historical T+1 intake excludes recent/live captures')
        publisher, instrument = integer(row['publisher_id']), integer(row['instrument_id'])
        sequence, flags = integer(row['sequence']), integer(row['flags'])
        size = integer(row['size'])
        if size<=0 or size>=2**32 or publisher>=2**16 or instrument>=2**32 or sequence>=2**32 or flags>=256 or integer(row['rtype']) != 0 or row['action'] != 'T':
            raise ValueError('Not a canonical trades record')
        try:
            if m['priceEncoding']=='FIXED_1E9':
                if not re.fullmatch(r'-?[0-9]+',str(row['price'])):raise ValueError('Integer fixed price required')
                fixed=int(row['price'])
                if not -2**63<fixed<2**63-1:raise ValueError('Undefined or out-of-range price')
                price=Decimal(fixed)/Decimal(10**9)
            else:
                price=Decimal(str(row['price']))
            if not price.is_finite() or price<=0:raise ValueError('Invalid price')
        except InvalidOperation as error:
            raise ValueError('Invalid decimal price') from error
        matches=[mapping for mapping in m['instrumentMappings'] if integer(mapping['publisher_id'])==publisher and integer(mapping['instrument_id'])==instrument and ns(mapping['validFromUTC'])<=event<ns(mapping['validUntilUTC'])]
        if len(matches)!=1:raise ValueError('Unknown or ambiguous point-in-time instrument mapping')
        mapping=matches[0]
        if mapping.get('venue')!='COMEX' or mapping.get('instrumentClass')!='F' or not mapping.get('evidenceReference') or not re.fullmatch(r'GC[FGHJKMNQUVXZ]\d{1,4}',mapping.get('rawSymbol','')):
            raise ValueError('Verified COMEX outright mapping required')
        raw_contract=re.fullmatch(r'GC([FGHJKMNQUVXZ])(\d{1,4})',mapping['rawSymbol'])
        canonical=re.fullmatch(r'GC([FGHJKMNQUVXZ])(\d{4})',mapping.get('contract',''))
        if not canonical or raw_contract[1]!=canonical[1] or int(canonical[2])%(10**len(raw_contract[2]))!=int(raw_contract[2]):
            raise ValueError('Raw symbol and canonical contract disagree')
        expiry=ns(mapping['contractExpiryUTC']); mapping_time=ns(mapping['mappingAvailableUTC'])
        if mapping_time>captured:raise ValueError('Mapping evidence unavailable at capture')
        quality=[]
        if mapping.get('contract')!=m['targetContract']:quality.append('CONTRACT_MISMATCH')
        if event>=expiry:quality.append('EXPIRED_CONTRACT')
        if event>recv or recv>batch_received:quality.append('CLOCK_ORDER')
        if last_recv is not None and recv<last_recv:quality.append('REVERSED_VENDOR_RECEIPT')
        last_recv=recv
        if flags&8:quality.append('BAD_TS_RECV')
        if flags&4:quality.append('CHANNEL_GAP_FLAG')
        if flags&32:quality.append('SNAPSHOT_TRADE_UNREVIEWED')
        if flags&2:quality.append('PUBLISHER_FLAG_UNREVIEWED')
        side=row.get('side','N') or 'N'
        aggressor={'B':'BUY','A':'SELL'}.get(side,'UNKNOWN')
        key=(publisher,instrument,sequence,event,recv,str(price),size,side)
        if key in seen:quality.append('DUPLICATE_OR_AMBIGUOUS_TRADE')
        seen.add(key)
        rows.append(dict(ts_event_ns=str(event),ts_recv_ns=str(recv),local_recv_ns=str(batch_received),mapping_available_ns=str(mapping_time),
                         marketUTC=iso_ns(event),vendorReceivedUTC=iso_ns(recv),localReceivedUTC=iso_ns(batch_received),
                         publisher_id=publisher,instrument_id=instrument,sequence=sequence,flags=flags,contract=mapping['contract'],
                         contractExpiryUTC=iso_ms(expiry),priceUSD=str(price),size=size,rawSide=side,aggressor=aggressor,quality=quality))
    feeds={'GC':[],'orderFlow':[]};windows=[]
    previous_end=None
    for window in m.get('windows',[]):
        start,end=ns(window['startUTC']),ns(window['endUTC'])
        if not 0<end-start<=300*10**9 or start%1000000 or end%1000000 or (previous_end is not None and start<previous_end):
            raise ValueError('Explicit nonoverlapping UTC-ms windows of at most 5 minutes required')
        previous_end=end
        chosen=[row for row in rows if start<=int(row['ts_event_ns'])<end]
        blocks=sorted({reason for row in chosen for reason in row['quality']})
        proof=window.get('continuity',{})
        if proof.get('status')!='VERIFIED_COMPLETE' or proof.get('sequenceGapCount')!=0 or not proof.get('evidenceReference'):
            blocks.append('CONTINUITY_UNVERIFIED_OR_GAPPED')
        # Consecutive trade sequences are not required: trades are a filtered channel subset.
        unknown=sum(row['size'] for row in chosen if row['aggressor']=='UNKNOWN')
        buy=sum(row['size'] for row in chosen if row['aggressor']=='BUY')
        sell=sum(row['size'] for row in chosen if row['aggressor']=='SELL')
        if not chosen:blocks.append('NO_TRADES')
        local=max([batch_received]+[int(row['mapping_available_ns']) for row in chosen])
        if proof.get('availableUTC'):
            if ns(proof['availableUTC'])<end:blocks.append('CONTINUITY_BEFORE_WINDOW_CLOSE')
            local=max(local,ns(proof['availableUTC']))
        else:
            blocks.append('CONTINUITY_RECEIPT_MISSING')
        if local>captured:raise ValueError('Future window quality receipt')
        base=dict(schemaVersion=2,mode='recorded',role='INTRADAY_CONFIRMATION',source='Databento GLBX.MDP3 trades local export',rights=r,
                  availabilityEvidence=m['localReceiptEvidence'],availableUTC=iso_ms(local,ceil=True),contract=m['targetContract'],
                  availabilityBasis='ACTUAL_LOCAL_RECEIPT',isActualStrategyReceipt=True)
        if not blocks:
            ordered=sorted(chosen,key=lambda row:(int(row['ts_event_ns']),int(row['ts_recv_ns']),row['sequence']))
            latest=ordered[-1]
            prior=next((row for row in reversed(ordered[:-1]) if iso_ms(int(row['ts_event_ns']))<iso_ms(int(latest['ts_event_ns']))),None)
            base['contractExpiryUTC']=latest['contractExpiryUTC']
            if prior is not None and int(latest['ts_event_ns'])-int(prior['ts_event_ns'])<=300*10**9:
                feeds['GC'].append({**base,'instrument':'GC','observedUTC':iso_ms(int(latest['ts_event_ns'])),
                                    'value':float(Decimal(latest['priceUSD'])),'previous':float(Decimal(prior['priceUSD'])),
                                    'previousObservedUTC':iso_ms(int(prior['ts_event_ns'])),'previousAvailableUTC':iso_ms(max(batch_received,int(prior['mapping_available_ns'])),ceil=True),
                                    'referenceContract':m['targetContract'],'priceConvention':'TRADE'})
            else:
                blocks.append('GC_DISTINCT_PRIOR_TRADE_MISSING')
            if unknown==0:
                feeds['orderFlow'].append({**base,'instrument':'GC_TRADES','observedUTC':iso_ms(end),
                                           'windowStartUTC':iso_ms(start),'windowEndUTC':iso_ms(end),'kind':'trades','sideMethod':'EXCHANGE_AGGRESSOR',
                                           'licensed':True,'sequenceGapCount':0,'buyVolume':buy,'sellVolume':sell})
        if unknown:blocks.append('UNKNOWN_AGGRESSOR')
        windows.append(dict(startUTC=iso_ms(start),endUTC=iso_ms(end),tradeCount=len(chosen),buyVolume=buy,sellVolume=sell,unknownVolume=unknown,
                            knownSideVolumePct=100*(buy+sell)/(buy+sell+unknown) if buy+sell+unknown else None,blockers=sorted(set(blocks))))
    # Index by actual availability, including late quality receipts, without changing clocks.
    for entries in feeds.values():entries.sort(key=lambda row:(ns(row['availableUTC']),ns(row['observedUTC'])))
    validate_v2(feeds)
    return dict(kind='LOCAL_DATABENTO_GC_INTAKE',networkEnabled=False,executable=False,sourceSHA256=m['sha256'],
                independentlyAuthenticated=False,availabilityBasis='ACTUAL_LOCAL_RECEIPT',normalizedTrades=rows,windowReports=windows,feeds=feeds,
                note='Vendor ts_recv is not local arrival. Historical data downloaded later is not retrospectively available to the strategy. Unknown sides are never inferred; filtered sequence jumps alone do not establish channel loss.')


if __name__=='__main__':
    import pathlib
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest');parser.add_argument('--output',required=True)
    args=parser.parse_args()
    pathlib.Path(args.output).write_text(json.dumps(convert(args.manifest),indent=2,allow_nan=False)+'\n')
