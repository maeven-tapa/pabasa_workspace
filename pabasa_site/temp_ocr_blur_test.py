import os
os.environ['DJANGO_SETTINGS_MODULE'] = 'pabasa_site.settings'
import django
django.setup()
from pabasa_app.views import _extract_text_from_image
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from io import BytesIO
import io

img = Image.new('RGB', (320, 100), (245, 245, 245))
draw = ImageDraw.Draw(img)
font = ImageFont.load_default()
draw.text((20, 20), 'Hello OCR', fill=(180, 180, 180), font=font)
img = img.filter(ImageFilter.GaussianBlur(0.8))
buf = BytesIO()
img.save(buf, format='PNG')
buf.seek(0)

class U(io.BytesIO):
    def __init__(self, b, name):
        super().__init__(b)
        self.name = name
        self.size = len(b)

res = _extract_text_from_image(U(buf.getvalue(), 'test.png'))
print(repr(res))
