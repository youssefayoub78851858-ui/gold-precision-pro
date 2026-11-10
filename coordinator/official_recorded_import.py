"""Offline FRED-v2 bridge and partial government ICS/RSS/Atom evidence parser."""
import argparse
import datetime as dt
from email.utils import parsedate_to_datetime
import io
import json
import re
import xml.etree.ElementTree as ET
from urllib.parse import urlparse
from zoneinfo import ZoneInfo
from recorded_utils import ns, iso_ms, pinned_file, validate_v2
from import_fred_recorded import convert as legacy_fred

ALLOWED={'www.bls.gov','bls.gov','www.bea.gov','bea.gov','www.federalreserve.gov','federalreserve.gov','home.treasury.gov','www.treasury.gov','treasury.gov'}


def fred_v2(csv_path,sidecar_path):
    import pathlib
    sidecar=json.loads(pathlib.Path(sidecar_path).read_text())
    source=urlparse(sidecar['sourceReference'])
    if source.scheme!='https' or source.hostname!='fred.stlouisfed.org' or not sidecar.get('publicDomainEvidenceReference'):
        raise ValueError('Official FRED source and series public-domain evidence required')
    records,report=legacy_fred(csv_path,sidecar_path)
    captured=ns(sidecar['capturedUTC'])
    for rows in records.values():
        for row in rows:
            meta=sidecar['observations'][row['observationDate']]
            reference=meta.get('referenceVintage',{})
            schedule=meta.get('releaseSchedule',{})
            if not reference.get('evidenceReference') or not schedule.get('evidenceReference'):
                raise ValueError('Point-in-time reference vintage and release schedule required')
            row.update(schemaVersion=2,role='DAILY_CONTEXT',
                       rights=dict(status='VERIFIED_INTERNAL_RESEARCH',algorithmicResearchAuthorized=True,evidenceReference=sidecar['publicDomainEvidenceReference']),
                       previous=reference['value'],previousObservationDate=reference['observationDate'],previousObservedUTC=reference['observedUTC'],previousAvailableUTC=reference['availableUTC'],
                       nextExpectedReleaseUTC=schedule['nextExpectedReleaseUTC'],releaseScheduleAvailableUTC=schedule['availableUTC'],releaseScheduleReference=schedule['evidenceReference'])
            if max(ns(row['availableUTC']),ns(row['releaseScheduleAvailableUTC']))>captured:
                raise ValueError('Future receipt relative to saved export')
    validate_v2(records)
    return dict(kind='LOCAL_OFFICIAL_FRED_V2',networkEnabled=False,executable=False,records=records,
                importReport=report,note='Daily context only; original value and separate schedule availability retained; no current network lookup')


def ics_time(key,value):
    if value.endswith('Z'):
        parsed=dt.datetime.strptime(value,'%Y%m%dT%H%M%SZ').replace(tzinfo=dt.timezone.utc)
    else:
        match=re.search(r'(?:^|;)TZID=([^;:]+)',key)
        if not match:raise ValueError('ICS event requires explicit UTC or TZID; date-only/floating values rejected')
        naive=dt.datetime.strptime(value,'%Y%m%dT%H%M%S')
        zone=ZoneInfo(match[1])
        zero,one=naive.replace(tzinfo=zone,fold=0),naive.replace(tzinfo=zone,fold=1)
        if zero.utcoffset()!=one.utcoffset() or zero.astimezone(dt.timezone.utc).astimezone(zone).replace(tzinfo=None)!=naive:
            raise ValueError('Ambiguous or nonexistent DST local event; provide UTC evidence')
        parsed=zero.astimezone(dt.timezone.utc)
    return parsed.isoformat(timespec='milliseconds').replace('+00:00','Z')


def government(path):
    m,raw=pinned_file(path,'government-official-export')
    url=urlparse(m['sourceURL'])
    if url.scheme!='https' or url.hostname not in ALLOWED or not m.get('publicDomainEvidenceReference') or m.get('thirdPartyContentExcluded') is not True:
        raise ValueError('Official source and rights/third-party review required')
    captured,received=ns(m['capturedUTC']),ns(m['localReceivedUTC'])
    if received>captured or not m.get('localReceiptEvidence'):
        raise ValueError('Actual local capture receipt required')
    if len(raw)>8*1024*1024:raise ValueError('Local official export exceeds 8 MiB')
    events=[]
    if m['format']=='ics':
        unfolded=[]
        for line in raw.decode('utf-8-sig').replace('\r\n','\n').splitlines():
            if line.startswith((' ','\t')) and unfolded:unfolded[-1]+=line[1:]
            else:unfolded.append(line)
        current=None
        for line in unfolded:
            if line=='BEGIN:VEVENT':
                if current is not None:raise ValueError('Nested VEVENT')
                current={}
            elif line=='END:VEVENT':
                if current is None:raise ValueError('Unmatched VEVENT')
                if 'RRULE' in current:raise ValueError('Recurring calendar expansion requires explicit reviewed occurrences')
                uid=current['UID'][1]
                timing=m.get('publications',{}).get(uid)
                if not timing or not timing.get('evidenceReference'):
                    raise ValueError('Calendar publication evidence required; DTSTAMP is not inferred publication')
                published,arrival=ns(timing['publishedUTC']),ns(timing.get('availableUTC',m['localReceivedUTC']))
                if published>arrival or arrival>captured:raise ValueError('Calendar publication/arrival order')
                events.append(dict(id=uid,timeUTC=ics_time(*current['DTSTART']),publishedUTC=iso_ms(published,ceil=True),availableUTC=iso_ms(arrival,ceil=True),
                                   title=current.get('SUMMARY',('',''))[1],impact='UNCLASSIFIED',publicationEvidence=timing['evidenceReference']))
                current=None
            elif current is not None and ':' in line:
                key,value=line.split(':',1);name=key.split(';',1)[0]
                if name in current:raise ValueError('Duplicate calendar property')
                current[name]=(key,value)
        if current is not None:raise ValueError('Unclosed VEVENT')
        role='GOVERNMENT_SCHEDULE_SUBSET'
    elif m['format'] in ('rss','atom'):
        root=ET.fromstring(raw)
        def local(tag):return tag.split('}')[-1]
        for item in root.iter():
            if local(item.tag) not in ('item','entry'):continue
            fields={local(c.tag):c for c in item}
            def value(name):return fields[name].text.strip() if name in fields and fields[name].text else ''
            uid=value('guid') or value('id') or value('link')
            if not uid:raise ValueError('Stable official news ID required')
            if 'pubDate' in fields:
                pub=parsedate_to_datetime(value('pubDate'))
                if pub.tzinfo is None:raise ValueError('RSS publication requires timezone')
                published=ns(pub.astimezone(dt.timezone.utc).isoformat().replace('+00:00','Z'))
            elif 'published' in fields:
                published=ns(value('published'))
            else:raise ValueError('Original publication required; updated timestamp is not substituted')
            arrival=ns(m.get('receipts',{}).get(uid,m['localReceivedUTC']))
            if published>arrival or arrival>captured:raise ValueError('News publication/arrival order')
            events.append(dict(id=uid,title=value('title'),publishedUTC=iso_ms(published,ceil=True),availableUTC=iso_ms(arrival,ceil=True),impact='UNCLASSIFIED'))
        role='GOVERNMENT_NEWS_SUBSET'
    else:raise ValueError('Only saved ICS/RSS/Atom supported')
    if len({e['id'] for e in events})!=len(events):raise ValueError('Duplicate official event ID')
    return dict(kind='LOCAL_OFFICIAL_PARTIAL_EVIDENCE',networkEnabled=False,executable=False,sourceURL=m['sourceURL'],sourceSHA256=m['sha256'],
                role=role,partialScope=True,eligibleForUltimate=False,continuityVerified=False,events=events,
                note='Government subset only, no impact inference or broad-news coverage claim; not a complete Ultimate feed')


if __name__=='__main__':
    import pathlib
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='mode',required=True)
    f=sub.add_parser('fred');f.add_argument('csv');f.add_argument('sidecar');f.add_argument('--output',required=True)
    g=sub.add_parser('government');g.add_argument('manifest');g.add_argument('--output',required=True)
    args=parser.parse_args()
    result=fred_v2(args.csv,args.sidecar) if args.mode=='fred' else government(args.manifest)
    pathlib.Path(args.output).write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
