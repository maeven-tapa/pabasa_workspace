from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from django.core.files.uploadedfile import SimpleUploadedFile
from pabasa_app.views import _extract_text_from_image

img = Image.new('RGB', (800, 240), 'white')
d = ImageDraw.Draw(img)
font = ImageFont.load_default()
d.text((40, 80), 'Hello world from OCR', fill='black', font=font)
buf = BytesIO()
img.save(buf, format='PNG')
buf.seek(0)
upload = SimpleUploadedFile('sample.png', buf.getvalue(), content_type='image/png')
text = _extract_text_from_image(upload)
print('OCR_TEXT=' + repr(text))
