"""Stage the verified digest, check HTTPS, then promote that exact revision."""
import argparse
import json
from pathlib import Path
import re
import time
import tempfile
import urllib.request
from urllib.parse import urlsplit

from cloud_release_gate import cli, job_spec


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('project', 'region', 'service', 'commit', 'build'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--image-file', required=True, type=Path)
    args = parser.parse_args()
    image = args.image_file.read_text().strip()
    if not re.fullmatch(r'[^\s]+@sha256:[0-9a-f]{64}', image):
        raise ValueError('A verified immutable image digest is required.')
    flags = ['--project=' + args.project, '--region=' + args.region, '--quiet']
    source = cli(['run', 'services', 'describe', args.service, *flags, '--format=json'], json_result=True)
    # Cloud Run limits the combined service name and traffic tag to 46 chars.
    tag_length = 46 - len(args.service)
    if tag_length < 5:
        raise ValueError('The service name leaves insufficient space for a unique verification tag.')
    tag = 'b' + args.build[:min(8, tag_length - 1)]
    host = tag + '---' + urlsplit(source['status']['url']).hostname
    revision = args.service + '-b' + args.build[:8]
    labels = 'managed-by=gcp-cloud-build-deploy-cloud-run,commit-sha=' + args.commit + ',gcb-build-id=' + args.build
    cli(['run', 'services', 'update', args.service, *flags, '--image=' + image,
         '--no-traffic', '--tag=' + tag, '--revision-suffix=b' + args.build[:8],
         '--update-env-vars=PABASA_REVISION_HOST=' + host, '--labels=' + labels])
    staged = cli(['run', 'revisions', 'describe', revision, *flags, '--format=json'], json_result=True)
    if staged['status'].get('imageDigest') != image or not any(
            condition.get('type') == 'Ready' and condition.get('status') == 'True'
            for condition in staged['status'].get('conditions', [])):
        raise RuntimeError('The staged revision is not ready with the verified image.')
    for path in ('/', '/auth/'):
        for attempt in range(6):
            try:
                request = urllib.request.Request('https://' + host + path,
                    headers={'User-Agent': 'PABASA-build-check-' + args.build})
                with urllib.request.urlopen(request, timeout=30) as response:
                    if response.status != 200 or not response.read(4096):
                        raise RuntimeError('Empty or unsuccessful HTTPS response.')
                break
            except Exception:
                if attempt == 5:
                    raise
                time.sleep(5)
        print('Staged HTTPS check passed: ' + path, flush=True)
    # The same image also checks authenticated templates/queries against the
    # production database. All synthetic users and session writes roll back.
    source = cli(['run', 'services', 'describe', args.service, *flags, '--format=json'], json_result=True)
    job = 'pabasa-verify-' + args.build[:8]
    spec = job_spec(source, image, job, args.project)
    container = spec['spec']['template']['spec']['template']['spec']['containers'][0]
    container['command'] = ['python']
    container['args'] = ['tools/check_release_runtime.py']
    with tempfile.TemporaryDirectory(prefix='pabasa-verify-') as directory:
        path = Path(directory) / 'job.json'
        path.write_text(json.dumps(spec), encoding='utf-8')
        cli(['run', 'jobs', 'replace', str(path), *flags])
    cli(['run', 'jobs', 'execute', job, '--wait', *flags])
    print('Same-image authenticated verification job passed.', flush=True)
    # A later push must not be overwritten by a build that finished out of order.
    build = cli(['builds', 'describe', args.build, '--project=' + args.project,
                 '--region=global', '--format=json'], json_result=True)
    trigger = build.get('buildTriggerId')
    if not trigger:
        raise RuntimeError('Promotion requires the existing GitHub trigger.')
    newest = cli(['builds', 'list', '--project=' + args.project, '--region=global',
                  '--filter=buildTriggerId=' + trigger, '--sort-by=~createTime', '--limit=1',
                  '--format=json'], json_result=True)
    if not newest or newest[0]['id'] != args.build:
        raise RuntimeError('A newer triggered build exists; this revision will not be promoted.')
    cli(['run', 'services', 'update-traffic', args.service, *flags, '--to-revisions=' + revision + '=100'])
    result = cli(['run', 'services', 'describe', args.service, *flags, '--format=json'], json_result=True)
    if not any(row.get('revisionName') == revision and row.get('percent') == 100
               for row in result['status']['traffic']):
        raise RuntimeError('The verified revision did not receive all traffic.')
    cli(['run', 'services', 'update-traffic', args.service, *flags, '--remove-tags=' + tag])
    cli(['run', 'jobs', 'delete', job, *flags])
    print('Verified digest promoted: ' + revision + ' ' + image, flush=True)


if __name__ == '__main__':
    main()
