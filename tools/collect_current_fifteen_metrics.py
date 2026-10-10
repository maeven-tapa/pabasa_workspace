"""Collect sanitized test results, server timings, and delayed resource samples."""
import concurrent.futures
import datetime as dt
import json
from pathlib import Path
import subprocess
import urllib.parse
import urllib.request
from measure_cloud_baseline import GCLOUD, PROJECT, summarize

ROOT = Path(__file__).resolve().parents[1]
REVISION = 'pabasa-01197-ht7'
token = subprocess.run([GCLOUD, 'auth', 'print-access-token'], capture_output=True, text=True, check=True).stdout.strip()


def api(url, body=None):
    req = urllib.request.Request(url, headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'},
                                 data=json.dumps(body).encode() if body is not None else None)
    with urllib.request.urlopen(req, timeout=35) as response:
        return json.load(response)


def logs(filter_text):
    entries, params = [], {'resourceNames': ['projects/' + PROJECT], 'filter': filter_text,
                           'pageSize': 1000, 'orderBy': 'timestamp asc'}
    while True:
        payload = api('https://logging.googleapis.com/v2/entries:list', params)
        entries.extend(payload.get('entries', []))
        if not payload.get('nextPageToken'): return entries
        params['pageToken'] = payload['nextPageToken']


job = (ROOT / 'tmp/current-loadtest-job-name.txt').read_text().strip()
entries = logs('resource.type="cloud_run_job" AND resource.labels.job_name=' + json.dumps(job) + ' AND textPayload:"PABASA_CURRENT_TWENTY_TEST "')
if not entries:
    print(json.dumps({'pending': True, 'job': job}))
    raise SystemExit(0)
report = json.loads(entries[-1]['textPayload'].split('PABASA_CURRENT_TWENTY_TEST ', 1)[1])
if report['clients'] != 20:
    raise ValueError('Expected a 20-client benchmark report.')
(ROOT / 'tmp/current-twenty-user-test.json').write_text(json.dumps(report, indent=2))
start = dt.datetime.fromisoformat(report['started_utc']) - dt.timedelta(minutes=2)
end = dt.datetime.fromisoformat(report['finished_utc']) + dt.timedelta(minutes=2)


def metric(item):
    name, kind, metric_type = item
    scope = ('resource.type="cloud_run_revision" AND resource.labels.service_name="pabasa" AND resource.labels.revision_name=' + json.dumps(REVISION)
             if kind == 'run' else f'resource.type="cloudsql_database" AND resource.labels.database_id="{PROJECT}:pabasa-db-micro"')
    params = {'filter': f'metric.type="{metric_type}" AND {scope}', 'interval.startTime': start.isoformat(),
              'interval.endTime': end.isoformat(), 'pageSize': 100000, 'view': 'FULL'}
    series = []
    while True:
        payload = api(f'https://monitoring.googleapis.com/v3/projects/{PROJECT}/timeSeries?' + urllib.parse.urlencode(params))
        series.extend(payload.get('timeSeries', []))
        if not payload.get('nextPageToken'): break
        params['pageToken'] = payload['nextPageToken']
    samples = []
    for s in series:
        for p in s.get('points', []):
            v = p['value']
            value = v['distributionValue'].get('mean', 0) if 'distributionValue' in v else float(v.get('doubleValue', v.get('int64Value', 0)))
            samples.append({'timestamp': p['interval']['endTime'], 'value': value, 'labels': s.get('metric', {}).get('labels', {})})
    result = dict(summarize(series, name), samples=sorted(samples, key=lambda x:x['timestamp']))
    if name == 'sql_connections':
        totals = {}
        for s in samples: totals[s['timestamp']] = totals.get(s['timestamp'], 0) + s['value']
        result['summed_maximum'] = max(totals.values(), default=None)
    return name, result


specs = [('sql_cpu', 'sql', 'cloudsql.googleapis.com/database/cpu/utilization'),
         ('sql_memory', 'sql', 'cloudsql.googleapis.com/database/memory/utilization'),
         ('sql_connections', 'sql', 'cloudsql.googleapis.com/database/postgresql/num_backends'),
         ('run_cpu', 'run', 'run.googleapis.com/container/cpu/utilizations'),
         ('run_memory', 'run', 'run.googleapis.com/container/memory/utilizations'),
         ('run_instances', 'run', 'run.googleapis.com/container/instance_count')]
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
    metrics = dict(pool.map(metric, specs))
scope = f'resource.type="cloud_run_revision" AND resource.labels.service_name="pabasa" AND timestamp>="{report["http_started_utc"]}" AND timestamp<="{end.isoformat()}"'
request_entries = logs(scope + ' AND httpRequest.userAgent=' + json.dumps(report['user_agent']))
requests = [{'timestamp': e['timestamp'], 'revision': e['resource']['labels'].get('revision_name'),
             'path': urllib.parse.urlparse(e['httpRequest']['requestUrl']).path,
             'status': e['httpRequest'].get('status'), 'ms': float(e['httpRequest'].get('latency', '0s').removesuffix('s'))*1000}
            for e in request_entries if e.get('httpRequest')]
error_entries = logs(scope + ' AND resource.labels.revision_name=' + json.dumps(REVISION) + ' AND severity>=ERROR')
result = {'collected_utc': dt.datetime.now(dt.timezone.utc).isoformat(), 'clients': report['clients'], 'revision': REVISION,
          'metrics': metrics, 'request_logs': requests, 'error_log_count': len(error_entries)}
(ROOT / 'tmp/current-twenty-user-metrics.json').write_text(json.dumps(result, indent=2))
print(json.dumps({'report': report, 'metrics': {name: {k:v for k,v in data.items() if k != 'samples'} | {
    'first_sample_utc': min((s['timestamp'] for s in data['samples']), default=None),
    'last_sample_utc': max((s['timestamp'] for s in data['samples']), default=None)} for name, data in metrics.items()},
    'matched_request_logs': len(requests), 'error_log_count': len(error_entries)}, indent=2))
