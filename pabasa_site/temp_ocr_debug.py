import os
os.environ['DJANGO_SETTINGS_MODULE'] = 'pabasa_site.settings'
import django
django.setup()
import pytesseract
from pabasa_app.views import _extract_text_from_image
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO

print('before', pytesseract.pytesseract.tesseract_cmd)

img = Image.new('RGB', (200, 80), color='white')
d = ImageDraw.Draw(img)
font = ImageFont.load_default()
d.text((10, 20), 'Hello', fill='black', font=font)
buf = BytesIO()
img.save(buf, format='PNG')
buf.seek(0)

class DummyUpload(BytesIO):
    def __init__(self, data):
        super().__init__(data)
        self.name = 'test.png'
        self.size = len(data)

print('result', repr(_extract_text_from_image(DummyUpload(buf.getvalue()))))
print('after', pytesseract.pytesseract.tesseract_cmd)
