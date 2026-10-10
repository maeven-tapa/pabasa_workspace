"""Read Cloud Monitoring metrics without changing cloud resources or exposing tokens."""

import argparse
import concurrent.futures
import datetime as dt
import json
import math
from pathlib import Path
import statistics
import subprocess
import urllib.error
import urllib.parse
import urllib.request

PROJECT = 'project-2b0d295d-ee06-40a7-927'
GCLOUD = r'C:\Program Files (x86)\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd'
METRICS = {
    'requests': ('run.googleapis.com/request_count', 'run'),
    'request_latency_ms': ('run.googleapis.com/request_latencies', 'run'),
    'run_cpu_fraction': ('run.googleapis.com/container/cpu/utilizations', 'run'),
    'run_memory_fraction': ('run.googleapis.com/container/memory/utilizations', 'run'),
    'run_instances': ('run.googleapis.com/container/instance_count', 'run'),
    'sql_cpu_fraction': ('cloudsql.googleapis.com/database/cpu/utilization', 'sql'),
    'sql_memory_fraction': ('cloudsql.googleapis.com/database/memory/utilization', 'sql'),
    'sql_connections': ('cloudsql.googleapis.com/database/postgresql/num_backends', 'sql'),
}


def bucket_upper(options, index):
    if 'exponentialBuckets' in options:
        bucket = options['exponentialBuckets']
        return (bucket['scale'] * bucket['growthFactor'] ** index
                if index <= bucket['numFiniteBuckets'] else math.inf)
    if 'linearBuckets' in options:
        bucket = options['linearBuckets']
        return (bucket.get('offset', 0) + bucket['width'] * index
                if index <= bucket['numFiniteBuckets'] else math.inf)
    bounds = options.get('explicitBuckets', {}).get('bounds', [])
    return bounds[index] if index < len(bounds) else math.inf


def summarize(series, name):
    points = [point for item in series for point in item.get('points', [])]
    scalars, distributions = [], []
    for point in points:
        value = point['value']
        if 'distributionValue' in value:
            distributions.append(value['distributionValue'])
        elif 'doubleValue' in value:
            scalars.append(value['doubleValue'])
        elif 'int64Value' in value:
            scalars.append(int(value['int64Value']))
    result = {'series': len(series), 'points': len(points)}
    if scalars:
        result.update(mean=statistics.mean(scalars), maximum=max(scalars), minimum=min(scalars))
        if name == 'requests':
            result['total'] = sum(scalars)
            by_status = {}
            for item in series:
                code = item.get('metric', {}).get('labels', {}).get('response_code', 'unknown')
                count = sum(int(point['value'].get('int64Value', 0)) for point in item.get('points', []))
                by_status[code] = by_status.get(code, 0) + count
            result['by_http_status'] = by_status
    count = sum(int(value.get('count', 0)) for value in distributions)
    if count:
        result['distribution_count'] = count
        result['weighted_mean'] = sum(int(value.get('count', 0)) * value.get('mean', 0)
                                      for value in distributions) / count
        options = distributions[0].get('bucketOptions', {})
        if all(value.get('bucketOptions', {}) == options for value in distributions):
            buckets = []
            for value in distributions:
                for index, bucket_count in enumerate(value.get('bucketCounts', [])):
                    while len(buckets) <= index:
                        buckets.append(0)
                    buckets[index] += int(bucket_count)
            for percentile in (.50, .95):
                cumulative = 0
                for index, bucket_count in enumerate(buckets):
                    cumulative += bucket_count
                    if cumulative >= count * percentile:
                        bound = bucket_upper(options, index)
                        result[f'p{int(percentile * 100)}_bucket_upper'] = bound if math.isfinite(bound) else None
                        break
        result['maximum_sample_mean'] = max(value.get('mean', 0) for value in distributions)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--revision', help='Optionally restrict Cloud Run metrics to one revision.')
    options = parser.parse_args()
    token = subprocess.run([GCLOUD, 'auth', 'print-access-token'], check=True,
                           capture_output=True, text=True).stdout.strip()
    end = dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=5)
    start = end - dt.timedelta(hours=24)
    headers = {'Authorization': 'Bearer ' + token}

    def collect(item):
        name, (metric, kind) = item
        scope = ('resource.type="cloud_run_revision" AND resource.labels.service_name="pabasa"'
                 if kind == 'run' else
                 'resource.type="cloudsql_database" AND '
                 f'resource.labels.database_id="{PROJECT}:pabasa-db"')
        if kind == 'run' and options.revision:
            scope += ' AND resource.labels.revision_name=' + json.dumps(options.revision)
        params = {'filter': f'metric.type="{metric}" AND {scope}',
                  'interval.startTime': start.isoformat(), 'interval.endTime': end.isoformat(),
                  'pageSize': 100000, 'view': 'FULL'}
        series = []
        try:
            while True:
                url = f'https://monitoring.googleapis.com/v3/projects/{PROJECT}/timeSeries?' + urllib.parse.urlencode(params)
                request = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(request, timeout=40) as response:
                    payload = json.load(response)
                series.extend(payload.get('timeSeries', []))
                if not payload.get('nextPageToken'):
                    break
                params['pageToken'] = payload['nextPageToken']
            return name, summarize(series, name)
        except urllib.error.HTTPError as error:
            details = json.loads(error.read()).get('error', {})
            return name, {'error': details.get('message', str(error.code))}

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        summaries = dict(pool.map(collect, METRICS.items()))
    result = {'window_start_utc': start.isoformat(), 'window_end_utc': end.isoformat(),
              'window_hours': 24, 'revision_filter': options.revision, 'metrics': summaries,
              'notes': ['Latency percentile upper bounds come from merged monitoring histogram buckets.',
                        'Run utilization statistics describe sampled active instances, not a full-class load test.']}
    suffix = '-current' if options.revision else ''
    target = Path(__file__).resolve().parents[1] / 'tmp' / f'redis-cloud-baseline{suffix}.json'
    target.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
