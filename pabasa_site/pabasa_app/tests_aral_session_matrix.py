"""Validate synthetic live-probe saving checkpoints against real Django views."""
import json
from pathlib import Path

from django.test import TestCase
from django.urls import reverse

from .models import StudentActivityProgress
from . import tests_aral_save_recovery


def comparable(value):
    if isinstance(value, dict):
        return {k: comparable(v) for k, v in value.items() if k not in ('choice_tokens', 'pending_reading_nonce', 'picture_order', 'target_word', 'started_at', 'elapsed_seconds')}
    if isinstance(value, list):
        return [comparable(v) for v in value]
    return value


class AralSessionSavingMatrixTests(TestCase):
    setUp = tests_aral_save_recovery.AralSaveRecoveryTests.setUp

    def test_every_active_activity_saves_its_checkpoint(self):
        cases = json.loads((Path(__file__).resolve().parents[2] / 'tools/fixtures/aral_save_checkpoints.json').read_text(encoding='utf-8'))['activities']
        self.assertEqual(len(cases), 85)
        for case in cases:
            with self.subTest(activity=case['key']):
                scope = dict(student=self.student, school_calendar=self.calendar, term=1, activity_key=case['key'])
                StudentActivityProgress.objects.filter(**scope).delete()
                if case['before']:
                    StudentActivityProgress.objects.create(**scope, **case['before'])
                self.client.get(reverse('prescribed_activity_page', kwargs={'activity_key':case['key']}))
                response = self.client.post(case['path'], json.dumps(case['payload']), content_type='application/json')
                self.assertEqual(response.status_code, 200, response.content[:250])
                row = StudentActivityProgress.objects.filter(**scope).values(*case['after']).first()
                self.assertEqual(comparable(row), comparable(case['after']))
                self.client.get(reverse('prescribed_activity_page', kwargs={'activity_key':case['key']}))
                restored = StudentActivityProgress.objects.filter(**scope).values(*case['after']).first()
                self.assertEqual(comparable(restored), comparable(row))
                if row and 'target_word' in row['state']:
                    self.assertEqual(restored['state']['target_word'],row['state']['target_word'])
