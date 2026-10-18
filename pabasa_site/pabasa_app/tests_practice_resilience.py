import json
from datetime import datetime, timezone
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from .models import Material, User
from .views import _record_material_practice_completion


class PracticeResilienceTests(TestCase):
    def setUp(self):
        self.students = [User.objects.create(custom_id=f'PRES-{n}', role='student', first_name='Test',
            last_name='Practice', sex='female', birth_month=1, birth_day=1, birth_year=2015,
            email=f'pres-{n}@example.invalid', password_hash='unused') for n in range(2)]
        self.material = Material.objects.create(title='Shared practice', type='practice', source_type='shared',
            is_system_owned=True, status='published', is_active=True, difficulty_level='easy',
            content_json={'mode':'color', 'items':['cat'], 'level':'level_1'})
        session = self.client.session
        session.update({'user_id':self.students[0].pk, 'user_role':'student'})
        session.save()

    @patch('pabasa_app.achievements.refresh_student_achievements')
    @patch('pabasa_app.achievements.record_learning_dates')
    def test_stale_material_cannot_erase_another_students_completion(self, *_):
        stale = Material.objects.get(pk=self.material.pk)
        payload = {'stars_earned':3, 'items_completed':1, 'completed_at':datetime.now(timezone.utc)}
        _record_material_practice_completion(self.material, self.students[0], payload)
        _record_material_practice_completion(stale, self.students[1], payload)
        self.material.refresh_from_db()
        self.assertEqual(set(self.material.content_json['student_completions']), {str(s.pk) for s in self.students})

    @patch('pabasa_app.achievements.refresh_student_achievements')
    @patch('pabasa_app.achievements.record_learning_dates')
    def test_stale_lower_color_result_cannot_reduce_saved_stars(self, *_):
        stale = Material.objects.get(pk=self.material.pk)
        _record_material_practice_completion(self.material, self.students[0], {'stars_earned':3})
        _record_material_practice_completion(stale, self.students[0], {'stars_earned':1})
        self.material.refresh_from_db()
        self.assertEqual(self.material.content_json['student_completions'][str(self.students[0].pk)]['stars_earned'], 3)

    def test_invalid_completion_bodies_return_400_without_saving(self):
        for payload in ([], None, 'bad', {'material_id':self.material.pk,'activity_type':'practice','correct_responses':'bad'},
                        {'material_id':self.material.pk,'activity_type':'practice','items_completed':{}},
                        {'material_id':self.material.pk,'activity_type':'practice','correct_responses':float('inf')}):
            with self.subTest(payload=payload):
                response = self.client.post(reverse('record_assessment_completion'), json.dumps(payload), content_type='application/json')
                self.assertEqual(response.status_code, 400)
        self.material.refresh_from_db()
        self.assertNotIn('student_completions', self.material.content_json)

    def test_hunt_non_object_body_returns_400(self):
        for payload in ([], None, 'bad'):
            response = self.client.post(reverse('award_hunt_mode_stars'), json.dumps(payload), content_type='application/json')
            self.assertEqual(response.status_code, 400)

    def test_old_account_queue_cannot_save_for_a_different_signed_in_student(self):
        response = self.client.post(reverse('record_assessment_completion'), json.dumps({
            'material_id':self.material.pk,'activity_type':'practice', 'student_id':self.students[1].pk,
            'items_completed':1,'correct_responses':1,
        }), content_type='application/json')
        self.assertEqual(response.status_code,403)
        self.material.refresh_from_db()
        self.assertNotIn('student_completions', self.material.content_json)

    def test_hunt_nonfinite_word_index_returns_400(self):
        self.material.content_json['mode'] = 'hunt'
        self.material.save(update_fields=['content_json'])
        response = self.client.post(reverse('award_hunt_mode_stars'), json.dumps({
            'student_id':self.students[0].pk, 'level_id':self.material.pk,
            'attempt_id':'invalid-index', 'award_type':'word', 'word_index':float('inf'),
        }), content_type='application/json')
        self.assertEqual(response.status_code,400)

    def test_hunt_cannot_credit_unpublished_or_private_material(self):
        for changes in ({'status':'draft'}, {'is_system_owned':False}, {'is_active':False}):
            material = Material.objects.create(title='Unavailable Hunt', type='practice', source_type='shared',
                is_system_owned=True, status='published', is_active=True, difficulty_level='easy',
                content_json={'mode':'hunt','items':['cat']})
            Material.objects.filter(pk=material.pk).update(**changes)
            response = self.client.post(reverse('award_hunt_mode_stars'), json.dumps({
                'student_id':self.students[0].pk,'level_id':material.pk,'attempt_id':'blocked',
                'award_type':'word','word_index':0,'transcript':'cat','confidence':.95,
            }), content_type='application/json')
            self.assertEqual(response.status_code,403)
        self.students[0].refresh_from_db()
        self.assertEqual(self.students[0].available_stars,0)
