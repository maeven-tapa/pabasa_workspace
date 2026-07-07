import os
os.environ['DJANGO_SETTINGS_MODULE'] = 'pabasa_site.settings'
import django
django.setup()
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
import pytesseract
from pabasa_app.views import _extract_text_from_image
img = Image.new('RGB', (400, 120), color='white')
d = ImageDraw.Draw(img)
try:
    font = ImageFont.truetype('arial.ttf', 32)
except Exception:
    font = ImageFont.load_default()
d.text((10, 30), 'Hello 123', fill='black', font=font)
buf = BytesIO()
img.save(buf, format='PNG')
buf.seek(0)
class DummyUpload(BytesIO):
    def __init__(self, data):
        super().__init__(data)
        self.name = 'test.png'
        self.size = len(data)
upload = DummyUpload(buf.read())
print('tesseract_cmd=', pytesseract.pytesseract.tesseract_cmd)
print('ocr=', repr(_extract_text_from_image(upload)))
