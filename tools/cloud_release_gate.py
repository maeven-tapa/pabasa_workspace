"""Run an isolated same-image migration check or authorized capacity probe.

Runtime identity, DB env/secret references, volumes and Cloud SQL attachment are
copied from the selected service in memory. No environment values or tokens are
printed. The configuration-only release refuses pending schema migrations.
"""
import argparse
import copy
import json
from pathlib import Path
import subprocess
import tempfile


def cli(arguments, *, json_result=False):
    result = subprocess.run(['gcloud', *arguments], capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError('Cloud command failed: ' + ' '.join(arguments[:3]) +
                           '; inspect the corresponding Cloud Run job/build logs.')
    return json.loads(result.stdout) if json_result else result.stdout.strip()


def job_spec(service, image, name, project, *, clients=None):
    runtime = service['spec']['template']['spec']
    source = runtime['containers'][0]
    container = {key: copy.deepcopy(source[key]) for key in ('env', 'resources', 'volumeMounts') if key in source}
    container['image'] = image
    if clients:
        if clients not in (20, 50):
            raise ValueError('Only explicitly authorized 20- or 50-student probes are supported.')
        container['command'] = ['python']
        container['args'] = ['tools/benchmark_live_crla_twenty.py']
        container.setdefault('env', []).append({'name': 'PABASA_AUTHORIZED_CAPACITY_TEST', 'value': str(clients)})
    else:
        # Check before migrate: this static-only release must not change schema.
        container['command'] = ['sh']
        container['args'] = ['-c', 'python pabasa_site/manage.py check_migration_readiness --require-recorded'
                             ' && python pabasa_site/manage.py migrate --check'
                             ' && python pabasa_site/manage.py migrate --noinput'
                             ' && python pabasa_site/manage.py migrate --check']
    allowed_annotations = {'run.googleapis.com/cloudsql-instances', 'run.googleapis.com/execution-environment',
                           'run.googleapis.com/vpc-access-connector', 'run.googleapis.com/vpc-access-egress',
                           'run.googleapis.com/network-interfaces'}
    annotations = {key: value for key, value in service['spec']['template']['metadata'].get('annotations', {}).items()
                   if key in allowed_annotations}
    task = {'serviceAccountName': runtime['serviceAccountName'], 'containers': [container],
            'maxRetries': 0, 'timeoutSeconds': '900'}
    if runtime.get('volumes'):
        task['volumes'] = copy.deepcopy(runtime['volumes'])
    return {'apiVersion': 'run.googleapis.com/v1', 'kind': 'Job',
            'metadata': {'name': name, 'namespace': project},
            'spec': {'template': {'spec': {'taskCount': 1, 'parallelism': 1,
                'template': {'metadata': {'annotations': annotations}, 'spec': task}}}}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', required=True)
    parser.add_argument('--region', default='asia-southeast1')
    parser.add_argument('--service', required=True)
    parser.add_argument('--image', required=True)
    parser.add_argument('--job', default='pabasa-release-migration-check')
    parser.add_argument('--image-file', type=Path)
    parser.add_argument('--clients', type=int, choices=(20, 50))
    args = parser.parse_args()
    flags = ['--project=' + args.project, '--region=' + args.region, '--quiet']
    image = args.image
    if '@sha256:' not in image:
        digest = cli(['artifacts', 'docker', 'images', 'describe', image,
                      '--project=' + args.project, '--format=value(image_summary.digest)'])
        if not digest.startswith('sha256:') or len(digest) != 71:
            raise ValueError('The release image digest could not be verified.')
        image = image.rsplit(':', 1)[0] + '@' + digest
    service = cli(['run', 'services', 'describe', args.service, *flags, '--format=json'], json_result=True)
    spec = job_spec(service, image, args.job, args.project, clients=args.clients)
    with tempfile.TemporaryDirectory(prefix='pabasa-release-gate-') as directory:
        path = Path(directory) / 'job.json'
        path.write_text(json.dumps(spec), encoding='utf-8')
        cli(['run', 'jobs', 'replace', str(path), *flags])
    print('Running ' + args.job + ' with image ' + image, flush=True)
    cli(['run', 'jobs', 'execute', args.job, '--wait', *flags])
    if args.image_file:
        args.image_file.write_text(image + '\n', encoding='utf-8')
    print('Same-image job succeeded: ' + args.job, flush=True)


if __name__ == '__main__':
    main()
