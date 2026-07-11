from io import BytesIO
from unittest.mock import patch

from django.test import SimpleTestCase
from PIL import Image

from .views import _extract_text_from_image


class ImageOcrTests(SimpleTestCase):
    def _image_upload(self):
        upload = BytesIO()
        Image.new('RGB', (500, 160), 'white').save(upload, format='PNG')
        upload.seek(0)
        return upload

    @patch('pytesseract.get_languages', return_value=['eng', 'fil'])
    @patch('pytesseract.image_to_data')
    def test_extracts_text_and_layout(self, image_to_data, _get_languages):
        image_to_data.return_value = {
            'text': ['', 'Masayang', 'bumasa'], 'conf': ['-1', '95.2', '92.8'],
            'left': [0, 10, 150], 'top': [0, 20, 20], 'width': [0, 120, 100],
            'height': [0, 35, 35], 'block_num': [0, 1, 1], 'par_num': [0, 1, 1],
            'line_num': [0, 1, 1], 'word_num': [0, 1, 2],
        }
        result = _extract_text_from_image(self._image_upload())
        self.assertEqual(result['text'], 'Masayang bumasa')
        self.assertEqual(len(result['layout']), 2)
        self.assertEqual(result['debug']['ocr_status'], 'success')
        self.assertEqual(result['debug']['languages'], ['eng', 'fil'])

    @patch('pytesseract.get_languages', return_value=['eng'])
    @patch('pytesseract.image_to_data')
    def test_falls_back_to_installed_english_data(self, image_to_data, _get_languages):
        image_to_data.return_value = {key: [] for key in (
            'text', 'conf', 'left', 'top', 'width', 'height',
            'block_num', 'par_num', 'line_num', 'word_num')}
        result = _extract_text_from_image(self._image_upload())
        self.assertEqual(result['debug']['languages'], ['eng'])
        self.assertEqual(result['debug']['missing_languages'], ['fil'])
        self.assertEqual(result['debug']['ocr_status'], 'empty')
