import os
os.environ['DJANGO_SETTINGS_MODULE'] = 'pabasa_site.settings'
import django
django.setup()
from pabasa_app.views import _extract_text_from_image
from pathlib import Path
import io

p = Path('pabasa_app/static/pabasa_app/images/reading.png')
data = p.read_bytes()

class U(io.BytesIO):
    def __init__(self, b, name):
        super().__init__(b)
        self.name = name
        self.size = len(b)

res = _extract_text_from_image(U(data, p.name))
print(repr(res[:500]))
