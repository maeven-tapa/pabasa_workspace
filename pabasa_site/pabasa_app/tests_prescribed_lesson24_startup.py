from pathlib import Path

from django.test import SimpleTestCase

from .prescribed_workbook import ACTIVITIES, get_activity


class Lesson24StartupTests(SimpleTestCase):
    keys = (
        'aral-l24-g1-v-syllable-builder',
        'aral-l24-g2-v-word-reading',
        'aral-l24-g3-x-repeat',
        'aral-l24-g4-x-pictures',
        'aral-l24-g3-x-word-reading',
        'aral-l24-g4-x-syllable-builder',
        'aral-l24-g5-z-syllabication',
        'aral-l24-g6-z-word-search',
        'aral-l24-g7-z-word-reading',
    )

    def test_authoritative_bahagi_order_and_display_numbers(self):
        self.assertEqual(
            [(key, ACTIVITIES[key]['section_label'], ACTIVITIES[key]['display_gawain_number']) for key in self.keys],
            [
                ('aral-l24-g1-v-syllable-builder', 'Bahagi 1', '1'),
                ('aral-l24-g2-v-word-reading', 'Bahagi 1', '2'),
                ('aral-l24-g3-x-repeat', 'Bahagi 1', '3'),
                ('aral-l24-g4-x-pictures', 'Bahagi 2', '2'),
                ('aral-l24-g3-x-word-reading', 'Bahagi 2', '3'),
                ('aral-l24-g4-x-syllable-builder', 'Bahagi 2', '4'),
                ('aral-l24-g5-z-syllabication', 'Bahagi 2', '5'),
                ('aral-l24-g6-z-word-search', 'Bahagi 2', '6'),
                ('aral-l24-g7-z-word-reading', 'Bahagi 2', '7'),
            ],
        )
        self.assertEqual([get_activity(key)['instruction'] for key in self.keys], [
            'Basahin ang mga pantig sa loob ng Big Box at subuking bumuo ng mga salita.',
            'Basahin ang mga salita sa ibaba na nagtataglay ng hiram na letrang Vv.',
            'Pakinggang mabuti ang mga salitang bibigkasin ng guro pagkatapos ay ulitin ito.',
            'Kilalanin ang bawat larawan at subuking basahin ito kasabay ng guro.',
            'Basahin ang mga salita sa ibaba na nagtataglay ng hiram na letrang Xx.',
            'Basahin ang mga pantig sa loob ng Big Box at subuking bumuo ng mga salita mula rito.',
            'Pantigin ang sumusunod na salitang may letrang Zz. Ginawa ang unang bilang para sa iyo.',
            'Panuto: Hanapin at bilugan sa loob ng Big Box ang sumusunod na mga salita.',
            'Basahin ang mga salita sa ibaba na may hiram na letrang Zz.',
        ])

    def test_each_template_has_one_startup_modal_and_helper(self):
        root = Path(__file__).parent
        templates = [
            root / 'templates/pabasa_app/prescribed_workbook_page.html',
            root / 'templates/pabasa_app/prescribed_l24_g2_reading_page.html',
            root / 'templates/pabasa_app/prescribed_l24_g3_repeat_page.html',
        ]
        helper = (root / 'static/pabasa_app/js/prescribed_l24_startup.js').read_text(encoding='utf-8')
        self.assertEqual(helper.count("document.dispatchEvent(new CustomEvent('pabasa:l24-started'"), 1)
        for template in templates:
            text = template.read_text(encoding='utf-8')
            self.assertEqual(text.count('id="wb-l24-start"'), 1)
            self.assertIn('data-l24-start-button', text)
            self.assertIn('data-l24-later-button', text)
            self.assertIn('prescribed_l24_startup.js', text)

    def test_mapped_instruction_files_are_existing_files_and_fallback_activities_have_no_duplicate(self):
        audio = Path(__file__).parent / 'static/pabasa_app/prescribed/audio/SESSION_8/LESSON_24'
        mapped = {
            'BAHAGI_1/GAWAIN_1/Basahin ang mga pantig sa loob ng Big Box at subuking bumuo ng mga salita._TTS.mp3',
            'BAHAGI_1/GAWAIN_2/Basahin ang mga salita sa ibaba na nagtataglay ng hiram na letrang Vv._TTS.mp3',
            'BAHAGI_1/GAWAIN_3/Pakinggang mabuti ang mga salitang bibigkasin ng guro pagkatapos ay ulitin ito._TTS.mp3',
            'BAHAGI_2/GAWAIN_2/Kilalanin ang bawat larawan at subuking basahin ito kasabay ng guro._TTS.mp3',
            'BAHAGI_2/GAWAIN_3/Basahin ang mga salita sa ibaba na nagtataglay ng hiram na letrang Xx._TTS.mp3',
            'BAHAGI_2/GAWAIN_4/Basahin ang mga pantig sa loob ng Big Box at subuking bumuo ng mga salita mula rito._TTS.mp3',
            'BAHAGI_2/GAWAIN_6/Panuto Hanapin at bilugan sa loob ng Big Box ang sumusunod na mga salita._TTS.mp3',
            'BAHAGI_2/GAWAIN_7/Basahin ang mga salita sa ibaba na may hiram na letrang Zz._TTS.mp3',
        }
        for relative in mapped:
            self.assertTrue((audio / relative).is_file(), relative)
        self.assertFalse((audio / 'BAHAGI_2/GAWAIN_5/Pantigin ang sumusunod na salitang may letrang Zz. Ginawa ang unang bilang para sa iyo._TTS.mp3').exists())
