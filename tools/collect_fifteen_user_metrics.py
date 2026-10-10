"""Read delayed monitoring samples and request logs for the bounded load test."""
import concurrent.futures
import datetime as dt
import json
from pathlib import Path
import subprocess
import urllib.parse
import urllib.request
from measure_cloud_baseline import PROJECT, GCLOUD, summarize


def main():
    root = Path(__file__).resolve().parents[1]
    test = json.loads((root / 'tmp/twenty-user-test.json').read_text(encoding='utf-8-sig'))
    if test['clients'] != 20:
        raise ValueError('Expected a 20-client benchmark report.')
    start = dt.datetime.fromisoformat(test['started_utc']) - dt.timedelta(minutes=3)
    end = dt.datetime.fromisoformat(test['finished_utc']) + dt.timedelta(minutes=2)
    token = subprocess.run([GCLOUD, 'auth', 'print-access-token'], capture_output=True,
                           text=True, check=True).stdout.strip()
    headers = {'Authorization': 'Bearer ' + token}
    def api(url, body=None):
        request = urllib.request.Request(url, headers=dict(headers, **{'Content-Type': 'application/json'}),
                                         data=json.dumps(body).encode() if body else None)
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)
    def metric(item):
        name, kind, metric_type = item
        scope = ('resource.type="cloud_run_revision" AND resource.labels.service_name="pabasa" '
                 'AND resource.labels.revision_name="pabasa-01173-w2r"' if kind == 'run' else
                 f'resource.type="cloudsql_database" AND resource.labels.database_id="{PROJECT}:pabasa-db"')
        params = {'filter': f'metric.type="{metric_type}" AND {scope}',
                  'interval.startTime': start.isoformat(), 'interval.endTime': end.isoformat(),
                  'view': 'FULL', 'pageSize': 100000}
        data = api(f'https://monitoring.googleapis.com/v3/projects/{PROJECT}/timeSeries?' + urllib.parse.urlencode(params))
        series = data.get('timeSeries', [])
        samples = []
        for s in series:
            for p in s.get('points', []):
                v = p['value']
                value = (v['distributionValue'].get('mean', 0) if 'distributionValue' in v else
                         float(v.get('doubleValue', v.get('int64Value', 0))))
                samples.append({'timestamp': p['interval']['endTime'], 'value': value,
                                'labels': s.get('metric', {}).get('labels', {})})
        return name, dict(summarize(series, name), samples=sorted(samples, key=lambda x:x['timestamp']))
    metrics = [('sql_cpu', 'sql', 'cloudsql.googleapis.com/database/cpu/utilization'),
               ('sql_memory_fraction', 'sql', 'cloudsql.googleapis.com/database/memory/utilization'),
               ('sql_memory_quota', 'sql', 'cloudsql.googleapis.com/database/memory/quota'),
               ('sql_connections', 'sql', 'cloudsql.googleapis.com/database/postgresql/num_backends'),
               ('run_cpu', 'run', 'run.googleapis.com/container/cpu/utilizations'),
               ('run_memory', 'run', 'run.googleapis.com/container/memory/utilizations'),
               ('run_instances', 'run', 'run.googleapis.com/container/instance_count')]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        collected = dict(pool.map(metric, metrics))
    logs = api('https://logging.googleapis.com/v2/entries:list', {
        'resourceNames': [f'projects/{PROJECT}'],
        'filter': ('resource.type="cloud_run_revision" AND resource.labels.service_name="pabasa" '
                   'AND httpRequest.userAgent=' + json.dumps(test['user_agent']) + ' '
                   f'AND timestamp>="{test["http_started_utc"]}" AND timestamp<="{end.isoformat()}"'),
        'pageSize': 1000, 'orderBy': 'timestamp asc'})
    requests = [{'timestamp': e['timestamp'], 'path': urllib.parse.urlparse(e['httpRequest']['requestUrl']).path,
                 'status': e['httpRequest']['status'], 'ms': float(e['httpRequest']['latency'].removesuffix('s')) * 1000}
                for e in logs.get('entries', []) if e.get('httpRequest')]
    result = {'collected_utc': dt.datetime.now(dt.timezone.utc).isoformat(), 'clients': test['clients'], 'metrics': collected,
              'request_logs': requests,
              'notes': ['Monitoring samples can take around three minutes to arrive.',
                        'Minute samples smooth short bursts. Inspect timestamps, not only window-wide means.']}
    (root / 'tmp/twenty-user-test-metrics.json').write_text(json.dumps(result, indent=2))
    compact = {name: {k:v for k,v in data.items() if k != 'samples'} | {
               'last_sample': max((s['timestamp'] for s in data['samples']), default=None)}
               for name, data in collected.items()}
    print(json.dumps({'metrics': compact, 'matched_request_logs': len(requests)}, indent=2))


if __name__ == '__main__':
    main()
