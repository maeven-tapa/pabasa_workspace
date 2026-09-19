import json
import uuid

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import School, StudentActivityProgress, User
from .prescribed_activity_catalog import prescribed_activity


class PrescribedLesson2021ClusterTests(TestCase):
    key = 'session-7-lesson-20-21-gawain-1'

    def setUp(self):
        token = uuid.uuid4().hex
        school = School.objects.create(name=f'Cluster {token}', code=f'CL-{token}')
        self.student = User.objects.create(
            custom_id=f'STU-{token}', role='student', first_name='Cluster', last_name='Learner',
            middle_initial='', suffix='', sex='female', birth_month=1, birth_day=1, birth_year=2018,
            email=f'cluster-{token}@example.com', password_hash='hashed', school_record=school,
        )
        self.teacher = User.objects.create(
            custom_id=f'TCH-{token}', role='teacher', first_name='Cluster', last_name='Teacher',
            middle_initial='', suffix='', sex='female', birth_month=1, birth_day=1, birth_year=1990,
            email=f'teacher-{token}@example.com', password_hash='hashed', teacher_role='Teacher',
            school_record=school,
        )

    def login_student(self):
        session = self.client.session
        session.update({'user_id': self.student.id, 'user_role': 'student', 'email': self.student.email})
        session.save()
        self.student.active_session_key = session.session_key
        self.student.last_activity = timezone.now()
        self.student.save(update_fields=['active_session_key', 'last_activity', 'updated_at'])

    def login_teacher(self):
        session = self.client.session
        session.update({'user_id': self.teacher.id, 'user_role': 'teacher', 'email': self.teacher.email})
        session.save()

    def test_catalog_has_workbook_order_and_scoped_png_placeholders(self):
        activity = prescribed_activity(self.key)
        self.assertEqual(activity['display_title'], 'Lesson 20 at 21: Gawain 1')
        self.assertEqual(activity['instruction'], 'Basahin ang salita. Bilugan ang pantig na may klaster.')
        self.assertEqual([item['word'] for item in activity['items']], ['tsek', 'kotse', 'tsokolate', 'pitsel', 'kutsara'])
        self.assertEqual([item['answer'] for item in activity['items']], ['tsek', 'tse', 'tso', 'tsel', 'tsa'])
        self.assertTrue(all(item['image_path'].startswith('pabasa_app/prescribed/session_7/lesson_20_21/gawain_1/') for item in activity['items']))

    def test_page_hides_answers_and_server_requires_reading_before_each_choice(self):
        self.login_student()
        page = self.client.get(reverse('prescribed_activity_page', kwargs={'activity_key': self.key}))
        self.assertTemplateUsed(page, 'pabasa_app/prescribed_cluster_syllable_page.html')
        payload = page.context['prescribed_activity_data']
        self.assertNotIn('answer', payload['items'][0])
        progress_url = reverse('prescribed_activity_progress', kwargs={'activity_key': self.key})
        rejected = self.client.post(progress_url, data=json.dumps({
            'candidate_answer': 'tsek', 'state': {'phase': 'syllable_selection', 'state_version': 1},
        }), content_type='application/json')
        self.assertEqual(rejected.status_code, 400)
        read = self.client.post(progress_url, data=json.dumps({
            'state': {'phase': 'oral_reading', 'completed_oral_reads': [0], 'state_version': 1},
        }), content_type='application/json')
        self.assertEqual(read.status_code, 200)
        accepted = self.client.post(progress_url, data=json.dumps({
            'candidate_answer': 'tsek', 'state': {'phase': 'syllable_selection', 'completed_oral_reads': [0], 'state_version': 2},
        }), content_type='application/json')
        self.assertTrue(accepted.json()['accepted'])
        saved = StudentActivityProgress.objects.get(student=self.student, activity_key=self.key)
        self.assertEqual(saved.completed_items, 1)
        self.assertEqual(saved.state['selected_answers']['0'], 'tsek')

    def test_teacher_picker_uses_the_registered_activity(self):
        self.login_teacher()
        teacher_page = self.client.get(reverse('course_teacher_view'))
        self.assertEqual(teacher_page.status_code, 200)
        self.assertEqual(
            teacher_page.context['prescribed_lesson_20_21_activities'][0]['activity_key'], self.key,
        )
        self.assertContains(teacher_page, 'prescribed-lesson-20-21-activities')
