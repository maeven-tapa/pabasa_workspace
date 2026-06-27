import re

p = 'pabasa_site/pabasa_app/templates/pabasa_app/principal_settings.html'
t = open(p, encoding='utf-8').read()

# Replace type="reset" buttons with type="button" + onclick reload
old = '<button type="reset" class="btn btn-outline-secondary">'
new = '<button type="button" class="btn btn-outline-secondary" onclick="location.reload()">'

count = t.count(old)
t = t.replace(old, new)

open(p, 'w', encoding='utf-8').write(t)
print(f'Updated {count} reset buttons to reload on click')
