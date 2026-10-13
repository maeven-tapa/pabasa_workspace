"""Collect read-only Cloud Monitoring evidence for hosting size recommendations."""
import concurrent.futures
import datetime as dt
import json
from pathlib import Path
import statistics
import subprocess
import urllib.error
import urllib.parse
import urllib.request

from measure_cloud_baseline import GCLOUD, PROJECT, summarize

METRICS = {
    'sql_cpu': 'cloudsql.googleapis.com/database/cpu/utilization',
    'sql_memory_components': 'cloudsql.googleapis.com/database/memory/components',
    'sql_memory_bytes_excluding_cache': 'cloudsql.googleapis.com/database/memory/usage',
    'sql_memory_bytes_including_cache': 'cloudsql.googleapis.com/database/memory/total_usage',
    'sql_disk_bytes_used': 'cloudsql.googleapis.com/database/disk/bytes_used',
    'sql_disk_bytes_quota': 'cloudsql.googleapis.com/database/disk/quota',
    'sql_disk_utilization': 'cloudsql.googleapis.com/database/disk/utilization',
    'sql_backends': 'cloudsql.googleapis.com/database/postgresql/num_backends',
    'run_cpu_current': 'run.googleapis.com/container/cpu/utilizations',
    'run_memory_current': 'run.googleapis.com/container/memory/utilizations',
}


def main():
    token = subprocess.run([GCLOUD, 'auth', 'print-access-token'], capture_output=True,
                           text=True, check=True).stdout.strip()
    headers = {'Authorization': 'Bearer ' + token}
    end = dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=5)
    start = end - dt.timedelta(days=7)

    def collect(item):
        name, metric = item
        scope = ('resource.type="cloud_run_revision" AND resource.labels.service_name="pabasa" '
                 'AND resource.labels.revision_name="pabasa-01173-w2r"' if name.startswith('run_') else
                 f'resource.type="cloudsql_database" AND resource.labels.database_id="{PROJECT}:pabasa-db"')
        params = {'filter': f'metric.type="{metric}" AND {scope}',
                  'interval.startTime': start.isoformat(), 'interval.endTime': end.isoformat(),
                  'pageSize': 100000, 'view': 'FULL'}
        series = []
        try:
            while True:
                url = f'https://monitoring.googleapis.com/v3/projects/{PROJECT}/timeSeries?' + urllib.parse.urlencode(params)
                with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=40) as response:
                    payload = json.load(response)
                series.extend(payload.get('timeSeries', []))
                if not payload.get('nextPageToken'):
                    break
                params['pageToken'] = payload['nextPageToken']
            result = summarize(series, name)
            timestamps = [p['interval']['endTime'] for s in series for p in s.get('points', [])]
            if timestamps:
                result['first_sample_utc'] = min(timestamps)
                result['last_sample_utc'] = max(timestamps)
            result['series_summaries'] = [dict(labels=s.get('metric', {}).get('labels', {}),
                                             **summarize([s], name)) for s in series]
            # Connection states/databases are separate series: sum at each timestamp.
            if name == 'sql_backends':
                totals = {}
                for s in series:
                    for point in s.get('points', []):
                        timestamp = point['interval']['endTime']
                        value = point['value']
                        totals[timestamp] = totals.get(timestamp, 0) + float(value.get('int64Value', value.get('doubleValue', 0)))
                values = sorted(totals.values())
                if values:
                    result['summed_connections'] = {'mean': statistics.mean(values), 'max': max(values)}
            return name, result
        except urllib.error.HTTPError as error:
            return name, {'http_error': error.code}

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        metrics = dict(pool.map(collect, METRICS.items()))
    result = {'start_utc': start.isoformat(), 'end_utc': end.isoformat(), 'days': 7,
              'metrics': metrics,
              'notes': ['Current revision only exists for part of the seven-day interval.',
                        'Samples cannot capture sub-minute spikes or guarantee performance after resizing.',
                        'Database memory settings and cache footprint can change with machine size.']}
    path = Path(__file__).resolve().parents[1] / 'tmp' / 'hosting-sizing-metrics.json'
    path.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
