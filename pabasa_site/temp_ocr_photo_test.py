import os
os.environ['DJANGO_SETTINGS_MODULE'] = 'pabasa_site.settings'
import django
django.setup()
from pabasa_app.views import _extract_text_from_image
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from io import BytesIO
import io

img = Image.new('RGB', (320, 110), (255,255,255))
d = ImageDraw.Draw(img)
font = ImageFont.load_default()
d.text((15, 25), 'Photo Scan Text', fill=(90,90,90), font=font)
for _ in range(1000):
    x = __import__('random').randrange(320)
    y = __import__('random').randrange(110)
    img.putpixel((x,y), (x % 255, y % 255, (x+y) % 255))
img = img.filter(ImageFilter.MedianFilter(3))
buf = BytesIO()
img.save(buf, format='PNG')
buf.seek(0)

class U(io.BytesIO):
    def __init__(self, b, name):
        super().__init__(b)
        self.name = name
        self.size = len(b)

res = _extract_text_from_image(U(buf.getvalue(), 'photo.png'))
print(repr(res))
