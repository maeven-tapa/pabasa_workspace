"""Offline checks for release runtime cloning; never contacts Google Cloud."""
import copy
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('gate', Path(__file__).with_name('cloud_release_gate.py'))
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


class GateTests(unittest.TestCase):
    def fixture(self):
        return {'spec': {'template': {'metadata': {'annotations': {
            'run.googleapis.com/cloudsql-instances': 'project:region:database',
            'autoscaling.knative.dev/maxScale': '3'}}, 'spec': {
                'serviceAccountName': 'runtime@example.test', 'containers': [{
                    'image': 'old-image', 'env': [{'name': 'DB_PASSWORD', 'valueFrom': {
                        'secretKeyRef': {'name': 'password-secret', 'key': 'latest'}}}],
                    'resources': {'limits': {'cpu': '1', 'memory': '1Gi'}},
                    'ports': [{'containerPort': 8080}]}]}}}}

    def test_migration_job_keeps_identity_secrets_and_database_attachment(self):
        source = self.fixture()
        original = copy.deepcopy(source)
        result = gate.job_spec(source, 'image@sha256:digest', 'release-job', 'project')
        task = result['spec']['template']['spec']['template']
        self.assertEqual(task['spec']['serviceAccountName'], 'runtime@example.test')
        container = task['spec']['containers'][0]
        self.assertEqual(container['env'], source['spec']['template']['spec']['containers'][0]['env'])
        self.assertEqual(container['image'], 'image@sha256:digest')
        self.assertNotIn('ports', container)
        self.assertNotIn('metadata', task, 'Cloud Run TaskTemplate only contains spec')
        self.assertEqual(result['spec']['template']['metadata']['annotations'],
                         {'run.googleapis.com/cloudsql-instances': 'project:region:database'})
        self.assertEqual(source, original)
        command = container['args'][1]
        self.assertLess(command.index('check_migration_readiness --require-recorded'), command.index('migrate --check'))
        self.assertLess(command.index('migrate --check'), command.index('migrate --noinput'))
        self.assertTrue(command.endswith('migrate --check'))

    def test_capacity_job_requires_explicit_supported_client_count(self):
        with self.assertRaises(ValueError):
            gate.job_spec(self.fixture(), 'image', 'job', 'project', clients=15)
        result = gate.job_spec(self.fixture(), 'image', 'job', 'project', clients=50)
        task = result['spec']['template']['spec']['template']['spec']
        self.assertEqual(task['maxRetries'], 0)
        self.assertIn({'name': 'PABASA_AUTHORIZED_CAPACITY_TEST', 'value': '50'}, task['containers'][0]['env'])
        self.assertEqual(task['containers'][0]['args'], ['tools/benchmark_live_crla_twenty.py'])

    def test_migration_application_requires_verified_backup(self):
        with self.assertRaises(ValueError):
            gate.job_spec(self.fixture(), 'image', 'job', 'project', apply_migrations=True)
        result = gate.job_spec(self.fixture(), 'image', 'job', 'project',
                               apply_migrations=True, backup_verified=True)
        command = result['spec']['template']['spec']['template']['spec']['containers'][0]['args'][1]
        self.assertLess(command.index('check_migration_readiness --require-recorded'), command.index('migrate --noinput'))
        self.assertNotIn('migrate --check', command[:command.index('migrate --noinput')])
        self.assertTrue(command.endswith('migrate --check'))

    @patch.object(gate, 'cli')
    def test_backup_must_succeed_for_exact_attached_instance(self, cli):
        cli.side_effect = ['', [{'id': '123', 'instance': 'database', 'status': 'SUCCESSFUL'}]]
        gate.backup_database(self.fixture(), 'project')
        self.assertIn('--instance=database', cli.call_args_list[0].args[0])
        cli.side_effect = ['', [{'id': '124', 'instance': 'database', 'status': 'FAILED'}]]
        with self.assertRaises(RuntimeError):
            gate.backup_database(self.fixture(), 'project')

    @patch.object(gate, 'cli')
    def test_backup_rejects_ambiguous_or_other_project_database(self, cli):
        source = self.fixture()
        source['spec']['template']['metadata']['annotations']['run.googleapis.com/cloudsql-instances'] = 'other:region:database'
        with self.assertRaises(ValueError):
            gate.backup_database(source, 'project')
        cli.assert_not_called()


if __name__ == '__main__':
    unittest.main()
