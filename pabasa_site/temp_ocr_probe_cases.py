import os
os.environ['DJANGO_SETTINGS_MODULE'] = 'pabasa_site.settings'
import django
django.setup()
from pabasa_app.views import _extract_text_from_image
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps
from io import BytesIO
import io

font = ImageFont.load_default()

cases = []

# low contrast gray text on gray background
img = Image.new('RGB', (280, 90), (245,245,245))
d = ImageDraw.Draw(img)
d.text((20, 20), 'Hello OCR', fill=(180,180,180), font=font)
img = img.filter(ImageFilter.GaussianBlur(0.8))
cases.append(('gray_text_blur', img))

# screenshot-style with gradient shadow
img2 = Image.new('RGB', (320, 110), (255,255,255))
d = ImageDraw.Draw(img2)
d.rectangle((10, 10, 300, 90), fill=(240,240,240))
d.text((20, 25), 'Screenshot Text', fill=(60,60,60), font=font)
# add subtle shadow
for dx,dy in [(1,1), (2,2)]:
    d.text((20+dx,25+dy), 'Screenshot Text', fill=(220,220,220), font=font)
img2 = img2.filter(ImageFilter.GaussianBlur(0.6))
cases.append(('screenshot_shadow', img2))

# noisy photo-like image
img3 = Image.new('RGB', (320, 110), (255,255,255))
d = ImageDraw.Draw(img3)
d.text((15, 25), 'Photo Scan', fill=(90,90,90), font=font)
for _ in range(900):
    x = __import__('random').randrange(320)
    y = __import__('random').randrange(110)
    img3.putpixel((x,y), (x % 255, y % 255, (x+y) % 255))
img3 = img3.filter(ImageFilter.MedianFilter(3))
cases.append(('noisy_photo', img3))

for name, img in cases:
    buf = BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    class U(io.BytesIO):
        def __init__(self, b, name):
            super().__init__(b)
            self.name = name
            self.size = len(b)
    res = _extract_text_from_image(U(buf.getvalue(), f'{name}.png'))
    print(name, '=>', repr(res))
