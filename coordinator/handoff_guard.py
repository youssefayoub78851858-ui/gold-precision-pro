"""Read-only readiness gate; cannot route services, expose secrets or launch provider requests."""
import argparse,datetime,json,os,pathlib
UTC=datetime.timezone.utc
def check(m,key_present,now):
 reasons=[]
 if not key_present:reasons.append('PROVIDER_KEY_NOT_AVAILABLE_HERE')
 if not m.get('accountInventoryComplete'):reasons.append('ACCOUNT_WIDE_CONSUMER_INVENTORY_UNCONFIRMED')
 if not m.get('allAccountConsumersRouted'):reasons.append('SHARED_ACCOUNT_HANDOFF_NOT_COMPLETE')
 callers=m.get('consumers',[])
 if not callers:reasons.append('NO_CONSUMER_INVENTORY')
 for caller in callers:
  if caller.get('running') is False:continue
  if caller.get('route')!='SHARED_BROKER':reasons.append('BYPASS_OR_UNVERIFIED_ROUTE:'+caller['name'])
 if m.get('publishedServiceMustRemainUnchanged') and any(c.get('name')=='RenderPublishedService' and c.get('route')!='SHARED_BROKER' for c in callers):reasons.append('PUBLISHED_RENDER_CHANGE_PROHIBITED_SO_GLOBAL_HANDOFF_BLOCKED')
 if not m.get('minuteTrafficDrained'):reasons.append('LAST_ROLLING_MINUTE_NOT_DRAINED')
 if not m.get('durableQuotaLedgerConfirmed'):reasons.append('QUOTA_LEDGER_PROCESS_RESTART_PERSISTENCE_UNCONFIRMED')
 usage=m.get('providerUsage',{});used=usage.get('dailyUsed');extra=usage.get('postMeasurementCallsReserved')
 if type(used)!=int or not 0<=used<=800:reasons.append('CURRENT_PROVIDER_USAGE_NOT_VERIFIED')
 if type(extra)!=int or extra<0:reasons.append('POST_USAGE_MEASUREMENT_REQUESTS_NOT_RESERVED')
 try:
  at=datetime.datetime.fromisoformat(usage['observedUTC'].replace('Z','+00:00'))
  if at.tzinfo is None or at.utcoffset()!=datetime.timedelta(0) or not 0<=(now-at).total_seconds()<=60 or at.date()!=now.date():reasons.append('USAGE_SNAPSHOT_STALE_FUTURE_OR_WRONG_UTC_DAY')
 except (KeyError,TypeError,ValueError,AttributeError):reasons.append('USAGE_OBSERVATION_TIME_MISSING')
 if type(used)==int and type(extra)==int and used+extra>=720:reasons.append('SAFETY_DAILY_BUDGET_EXHAUSTED')
 return {'status':'BLOCKED' if reasons else 'CONFIGURATION_READY_PENDING_LIVE_VALIDATION','blockingReasons':sorted(set(reasons)),'providerMinuteLimit':8,'providerDailyLimit':800,'brokerRolling60sLimit':7,'brokerDailySafetyLimit':720,'providerRequestsMade':0,'globalQuotaProven':False,'noFlagsAutomaticallyEnabled':True}
def main():
 p=argparse.ArgumentParser();p.add_argument('--manifest',default=str(pathlib.Path(__file__).parent/'handoff-manifest.json'));a=p.parse_args();result=check(json.load(open(a.manifest)),bool(os.environ.get('TWELVE_DATA_API_KEY')),datetime.datetime.now(UTC));pathlib.Path(__file__).with_name('handoff-check.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
if __name__=='__main__':main()
