import json

from django.test import TestCase
from django.urls import reverse

from .models import Material, User
from .syllable_blending import build_activity


class ProtectedActivityRecoveryTests(TestCase):
    def setUp(self):
        self.student = User.objects.create(
            custom_id='STD-ACTIVITY-RECOVERY', role='student', first_name='Activity', last_name='Learner',
            middle_initial='', suffix='', sex='female', birth_month=1, birth_day=1, birth_year=2015,
            email='activity-recovery@example.com', password_hash='hashed-password',
        )
        session = self.client.session
        session.update({'user_id': self.student.id, 'user_role': 'student', 'email': self.student.email})
        session.save()

    def test_picture_word_route_renders_protected_template(self):
        material = Material.objects.create(
            title='Picture-Word Matching', item_type='word', type='assessment', source_type='template',
            status='published', student_access=True, language='Filipino',
            content_text='aso', content_json={
                'template_title': 'Picture-Word Matching', 'template_type': 'Picture-Word Matching',
                'activity_type': 'picture_word_matching', 'language': 'Filipino',
                'pictureWordMatching': {'mode': 'prescribed', 'setKey': 'D'},
                'items': [{'image': 'Dog.png', 'sourceSetKey': 'D', 'englishWord': 'Dog', 'filipinoWord': 'Aso'}],
            },
        )

        response = self.client.get(reverse('picture_word_matching_page'), {'id': f'material-{material.id}'})

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'pabasa_app/picture_word_matching_page.html')
        payload = json.loads(response.context['picture_word_material_json'])
        self.assertEqual(payload['items'][0]['word'], 'Aso')
        self.assertIn('/picture_word/prescribe_sets/Set%20D/Dog-Aso.png', payload['items'][0]['image_path'])

    def test_picture_word_route_migrates_legacy_custom_asset_path(self):
        material = Material.objects.create(
            title='Picture-Word Matching', item_type='word', type='assessment', source_type='template',
            status='published', student_access=True, language='English',
            content_text='horse', content_json={
                'template_title': 'Picture-Word Matching', 'activity_type': 'picture_word_matching',
                'language': 'English', 'pictureWordMatching': {'mode': 'custom'},
                'items': [{'image': 'Horse.png', 'set': 'Custom Set', 'englishWord': 'Horse', 'filipinoWord': 'Kabayo'}],
            },
        )

        response = self.client.get(reverse('picture_word_matching_page'), {'id': f'material-{material.id}'})

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.context['picture_word_material_json'])
        self.assertIn('/picture_word/custom/Horse-Kabayo.png', payload['items'][0]['image_path'])

    def test_syllable_blending_route_renders_lost_found_payload(self):
        content = build_activity('Filipino', 'big_box', 0)
        content.update({
            'template_title': 'Syllable Blending', 'template_lesson': 'Syllable Blending',
            'template_type': 'Syllable Blending', 'template_source': 'template',
        })
        material = Material.objects.create(
            title='Syllable Blending', item_type='word', type='assessment', source_type='template',
            status='published', student_access=True, language='Filipino', content_text='maso', content_json=content,
        )

        response = self.client.get(reverse('syllable_blending_page'), {'id': f'material-{material.id}'})

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'pabasa_app/syllable_blending_page.html')
        payload = json.loads(response.context['syllable_blending_material_json'])
        self.assertEqual(payload['activity_id'], 'filipino_big_box_01')
        self.assertEqual(len(payload['items']), 5)
        self.assertTrue(payload['syllable_pool'])

    def test_syllable_combination_result_requires_both_syllables(self):
        content = build_activity('English', 'syllable_combination', 1)
        content.update({
            'template_title': 'Syllable Blending', 'template_lesson': 'Syllable Blending',
            'template_type': 'Syllable Blending', 'template_source': 'template',
            'items': [{'syllables': ['mon', 'key'], 'answer': 'monkey'}],
        })
        material = Material.objects.create(
            title='MON + KEY', item_type='word', type='assessment', source_type='template',
            status='published', student_access=True, language='English', content_text='monkey',
            content_json=content,
        )

        response = self.client.get(reverse('syllable_blending_page'), {'id': f'material-{material.id}'})

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.context['syllable_blending_material_json'])
        self.assertEqual(payload['items'][0], {'syllables': ['mon', 'key'], 'answer': 'monkey'})
        rendered = response.content.decode('utf-8')
        self.assertIn('<span class="answer-slot">?</span>', rendered)
        self.assertIn("syllableResults.length===2&&syllableResults.every(Boolean)", rendered)
        self.assertIn("bothCorrect?String(item.answer||'').toUpperCase():'?'", rendered)
        self.assertIn('syllable_results:syllableResults.map(Boolean)', rendered)

    def test_syllable_combination_partial_match_keeps_result_hidden(self):
        template_path = 'pabasa_app/syllable_blending_page.html'
        with open(self._template_filename(template_path), encoding='utf-8') as template_file:
            source = template_file.read()

        self.assertIn("return expected.map((syllable,index)=>Boolean(", source)
        self.assertIn("syllableResults.length===2&&syllableResults.every(Boolean)", source)
        self.assertIn("if(slot)slot.textContent=bothCorrect?String(item.answer||'').toUpperCase():'?'", source)

    @staticmethod
    def _template_filename(template_path):
        from django.template.loader import get_template
        return get_template(template_path).origin.name

    def test_picture_word_completion_uses_objective_matching_score(self):
        material = Material.objects.create(
            title='Picture-Word Matching', item_type='word', type='assessment', source_type='template',
            status='published', student_access=True, language='English', content_text='dog',
            content_json={
                'template_title': 'Picture-Word Matching', 'activity_type': 'picture_word_matching',
                'language': 'English', 'items': [{'englishWord': 'Dog', 'filipinoWord': 'Aso'}],
            },
        )

        response = self.client.post(reverse('record_assessment_completion'), json.dumps({
            'material_id': material.id, 'activity_type': 'picture_word_matching',
            'items_completed': 1, 'scores': {'duration_seconds': 3, 'matches': [
                {'picture_index': 0, 'selected_word': 'Dog'},
            ]},
        }), content_type='application/json')

        self.assertEqual(response.status_code, 200)
        result = material.assessment_results.get(student=self.student, attempt_status='completed')
        self.assertEqual(result.correct_items, 1)
        self.assertEqual(float(result.accuracy), 100.0)
        self.assertTrue(result.remarks.startswith('PICTURE_WORD_MATCHING_RESULT:'))

    def test_syllable_completion_and_progress_use_specialized_pipeline(self):
        content = build_activity('English', 'big_box', 0)
        content.update({'template_title': 'Syllable Blending', 'template_lesson': 'Syllable Blending'})
        material = Material.objects.create(
            title='Syllable Blending', item_type='word', type='assessment', source_type='template',
            status='published', student_access=True, language='English', content_text='sunset', content_json=content,
        )
        answers = [item['answer'] for item in content['items']]
        responses = [
            {'item_index': index, 'recognized_response': answer, 'is_correct': True, 'completed': True}
            for index, answer in enumerate(answers)
        ]
        progress_response = self.client.post(reverse('record_assessment_completion'), json.dumps({
            'material_id': material.id, 'activity_type': 'syllable_blending', 'save_progress': True,
            'scores': {'responses': responses, 'discovery_attempts': []},
        }), content_type='application/json')
        self.assertEqual(progress_response.status_code, 200)
        self.assertTrue(progress_response.json()['saved'])

        response = self.client.post(reverse('record_assessment_completion'), json.dumps({
            'material_id': material.id, 'activity_type': 'syllable_blending',
            'items_completed': 5, 'scores': {
                'answers': answers, 'responses': responses, 'discovery_attempts': [], 'duration_seconds': 5,
            },
        }), content_type='application/json')

        self.assertEqual(response.status_code, 200)
        result = material.assessment_results.get(student=self.student, attempt_status='completed')
        self.assertEqual(result.correct_items, 5)
        self.assertEqual(float(result.accuracy), 100.0)
        self.assertTrue(result.remarks.startswith('SYLLABLE_BLENDING_RESULT:'))


class SyllableCatalogContextTests(TestCase):
    def test_teacher_courses_page_exposes_five_choices_per_language_and_format(self):
        teacher = User.objects.create(
            custom_id='TCH-ACTIVITY-RECOVERY', role='teacher', first_name='Activity', last_name='Teacher',
            middle_initial='', suffix='', sex='female', birth_month=1, birth_day=1, birth_year=1990,
            email='activity-teacher@example.com', password_hash='hashed-password', teacher_role='Teacher',
        )
        session = self.client.session
        session.update({'user_id': teacher.id, 'user_role': 'teacher', 'email': teacher.email})
        session.save()

        response = self.client.get(reverse('courses'))

        self.assertEqual(response.status_code, 200)
        catalog = response.context['syllable_blending_catalog']
        for language in ('Filipino', 'English'):
            self.assertEqual(len(catalog[language]['syllable_combination']), 5)
            self.assertEqual(len(catalog[language]['big_box']), 5)

        rendered = response.content.decode('utf-8')
        self.assertIn('id="syllable-blending-catalog"', rendered)
        self.assertIn('filipino_syllable_combination_01', rendered)
        self.assertIn("['05', 'Syllable Blending', 'Syllable Blending']", rendered)
        self.assertIn("function showTemplateBuilder(templateTitle)", rendered)
        self.assertIn("isSyllableBlendingTemplate(templateTitle)", rendered)
        self.assertIn("templateActivityGrid?.addEventListener('click'", rendered)
        self.assertIn("templateActivityTitle.closest('.template-title-field')", rendered)
        self.assertNotIn("templateActivityTitle.closest('.col-12')", rendered)
