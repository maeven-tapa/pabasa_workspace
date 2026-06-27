import re

t = open('pabasa_site/pabasa_app/templates/pabasa_app/principal_settings.html').read()
forms = re.findall(r'<form[^>]*>.*?</form>', t, re.DOTALL)
print(f'Forms found: {len(forms)}')

for i, f in enumerate(forms):
    has_submit = 'type="submit"' in f or "type='submit'" in f
    has_reset = 'type="reset"' in f or "type='reset'" in f
    print(f'Form {i+1}: has_submit={has_submit}, has_reset={has_reset}')
    if not has_reset:
        # Find what buttons it has
        buttons = re.findall(r'<button[^>]*>', f)
        print(f'  Buttons: {buttons}')
