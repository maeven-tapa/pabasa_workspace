"""Run an isolated same-image migration check or authorized capacity probe.

Runtime identity, DB env/secret references, volumes and Cloud SQL attachment are
copied from the selected service in memory. No environment values or tokens are
printed. The default refuses pending schema migrations. Explicit migration
releases create and verify an on-demand Cloud SQL backup before applying them.
"""
import argparse
import copy
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import uuid


def cli(arguments, *, json_result=False):
    executable = shutil.which('gcloud') or shutil.which('gcloud.cmd')
    if not executable:
        raise RuntimeError('Google Cloud CLI is required.')
    result = subprocess.run([executable, *arguments], capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError('Cloud command failed: ' + ' '.join(arguments[:3]) +
                           '; inspect the corresponding Cloud Run job/build logs.')
    return json.loads(result.stdout) if json_result else result.stdout.strip()


def job_spec(service, image, name, project, *, clients=None, apply_migrations=False,
             backup_verified=False):
    if apply_migrations and (clients or not backup_verified):
        raise ValueError('Migration application requires a verified backup and no capacity probe.')
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
        # The default remains read-only. Applying migrations requires a backup.
        container['command'] = ['sh']
        container['args'] = ['-c', 'python pabasa_site/manage.py check_migration_readiness --require-recorded'
                             ' && python pabasa_site/manage.py check'
                             ' && python pabasa_site/manage.py migrate --plan'
                             + ('' if apply_migrations else ' && python pabasa_site/manage.py migrate --check')
                             + ' && python pabasa_site/manage.py migrate --noinput'
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
            'spec': {'template': {'metadata': {'annotations': annotations},
                'spec': {'taskCount': 1, 'parallelism': 1, 'template': {'spec': task}}}}}


def backup_database(service, project):
    """Fail closed unless the selected service's exact Cloud SQL backup succeeds."""
    attached = service['spec']['template']['metadata'].get('annotations', {}).get(
        'run.googleapis.com/cloudsql-instances', '')
    parts = attached.split(':')
    if len(parts) != 3 or ',' in attached or parts[0] != project or not parts[2]:
        raise ValueError('A single Cloud SQL instance in the release project is required.')
    instance = parts[2]
    description = 'pabasa-release-' + uuid.uuid4().hex
    cli(['sql', 'backups', 'create', '--instance=' + instance, '--project=' + project,
         '--description=' + description, '--quiet'])
    backups = cli(['sql', 'backups', 'list', '--instance=' + instance, '--project=' + project,
                   '--filter=description=' + description, '--format=json'], json_result=True)
    if len(backups) != 1 or backups[0].get('status') != 'SUCCESSFUL' or backups[0].get('instance') != instance:
        raise RuntimeError('The release database backup could not be verified; migrations are blocked.')
    print('Verified pre-migration backup ' + str(backups[0]['id']) + ' for ' + instance, flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', required=True)
    parser.add_argument('--region', default='asia-southeast1')
    parser.add_argument('--service', required=True)
    parser.add_argument('--image', required=True)
    parser.add_argument('--job', default='pabasa-release-migration-check')
    parser.add_argument('--image-file', type=Path)
    parser.add_argument('--clients', type=int, choices=(20, 50))
    parser.add_argument('--apply-migrations', action='store_true',
                        help='Create and verify a Cloud SQL backup, then apply ready migrations.')
    args = parser.parse_args()
    if args.apply_migrations and args.clients:
        parser.error('--apply-migrations cannot be combined with --clients')
    flags = ['--project=' + args.project, '--region=' + args.region, '--quiet']
    image = args.image
    if '@sha256:' not in image:
        digest = cli(['artifacts', 'docker', 'images', 'describe', image,
                      '--project=' + args.project, '--format=value(image_summary.digest)'])
        if not digest.startswith('sha256:') or len(digest) != 71:
            raise ValueError('The release image digest could not be verified.')
        image = image.rsplit(':', 1)[0] + '@' + digest
    service = cli(['run', 'services', 'describe', args.service, *flags, '--format=json'], json_result=True)
    if args.apply_migrations:
        backup_database(service, args.project)
    spec = job_spec(service, image, args.job, args.project, clients=args.clients,
                    apply_migrations=args.apply_migrations, backup_verified=args.apply_migrations)
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
