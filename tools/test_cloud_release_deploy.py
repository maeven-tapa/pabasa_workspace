"""Offline regression checks: a failed or stale release never gets traffic."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import deploy_checked_release as deploy


class DeploymentTests(unittest.TestCase):
    def run_release(self, *, bad_digest=False, http_error=False, job_error=False, stale=False):
        image = 'registry.test/project/app@sha256:' + 'a' * 64
        self.commands = []

        def cli(args, **kwargs):
            self.commands.append(args)
            if args[:3] == ['run', 'services', 'describe']:
                return {'spec': {'template': {'metadata': {'annotations': {}}, 'spec': {
                    'serviceAccountName': 'runtime@example.test', 'containers': [{'image': image}]}}},
                    'status': {'url': 'https://service.run.app', 'traffic': [
                        {'revisionName': 'service-b12345678', 'percent': 100}]}}
            if args[:3] == ['run', 'revisions', 'describe']:
                return {'status': {'imageDigest': 'wrong' if bad_digest else image,
                                   'conditions': [{'type': 'Ready', 'status': 'True'}]}}
            if args[:3] == ['run', 'jobs', 'execute'] and job_error:
                raise RuntimeError('Authenticated verification failed')
            if args[:2] == ['builds', 'describe']:
                return {'buildTriggerId': 'existing-trigger'}
            if args[:2] == ['builds', 'list']:
                return [{'id': 'newer-build' if stale else '12345678-build'}]
            return ''

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'image.txt'
            path.write_text(image)
            response = MagicMock()
            response.__enter__.return_value.status = 200
            response.__enter__.return_value.read.return_value = b'<html>healthy</html>'
            argv = ['deploy', '--project=project', '--region=region', '--service=service',
                    '--commit=' + 'b' * 40, '--build=12345678-build', '--image-file=' + str(path)]
            with patch.object(sys, 'argv', argv), patch.object(deploy, 'cli', side_effect=cli), \
                    patch.object(deploy.urllib.request, 'urlopen',
                                 side_effect=OSError('HTTPS failed') if http_error else None,
                                 return_value=response), patch.object(deploy.time, 'sleep'):
                deploy.main()

    def assert_not_promoted(self):
        self.assertFalse(any(args[:3] == ['run', 'services', 'update-traffic'] for args in self.commands))

    def test_checked_digest_is_staged_then_promoted(self):
        self.run_release()
        stage = next(args for args in self.commands if args[:3] == ['run', 'services', 'update'])
        self.assertIn('--no-traffic', stage)
        self.assertTrue(any(arg.startswith('--image=registry.test/project/app@sha256:') for arg in stage))
        self.assertTrue(any(args[:3] == ['run', 'services', 'update-traffic'] for args in self.commands))

    def test_wrong_digest_is_never_promoted(self):
        with self.assertRaises(RuntimeError):
            self.run_release(bad_digest=True)
        self.assert_not_promoted()

    def test_failed_https_is_never_promoted(self):
        with self.assertRaises(OSError):
            self.run_release(http_error=True)
        self.assert_not_promoted()

    def test_failed_authenticated_check_is_never_promoted(self):
        with self.assertRaises(RuntimeError):
            self.run_release(job_error=True)
        self.assert_not_promoted()

    def test_older_build_cannot_overwrite_newer_release(self):
        with self.assertRaises(RuntimeError):
            self.run_release(stale=True)
        self.assert_not_promoted()


if __name__ == '__main__':
    unittest.main()
