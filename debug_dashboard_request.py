import urllib.request
import urllib.parse
import http.cookiejar
import re
import json

base = 'http://127.0.0.1:8000'
jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

print('-> GET /auth/')
with opener.open(f'{base}/auth/', timeout=20) as auth_resp:
    auth_html = auth_resp.read().decode('utf-8')
    print('AUTH_STATUS', auth_resp.status)
    m = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', auth_html)
    csrf_token = m.group(1) if m else None
    print('CSRF_TOKEN', csrf_token)

if not csrf_token:
    raise SystemExit('No CSRF token found')

login_data = urllib.parse.urlencode({
    'csrfmiddlewaretoken': csrf_token,
    'custom_id': 'STD-9999',
    'password': 'student123',
}).encode()

login_req = urllib.request.Request(
    f'{base}/api/login/',
    data=login_data,
    method='POST',
    headers={
        'Referer': f'{base}/auth/',
        'Content-Type': 'application/x-www-form-urlencoded',
    },
)
print('-> POST /api/login/')
with opener.open(login_req, timeout=20) as login_resp:
    print('LOGIN_STATUS', login_resp.status)
    login_body = login_resp.read().decode('utf-8')
    print('LOGIN_BODY', login_body)
    login_json = json.loads(login_body)
    print('LOGIN_JSON', login_json)

    if 'redirect_url' in login_json:
        dash_url = f'{base}{login_json["redirect_url"]}'
        dash_req = urllib.request.Request(
            dash_url,
            method='GET',
            headers={'Referer': f'{base}/auth/'},
        )
        print('-> GET', dash_req.full_url)
        try:
            with opener.open(dash_req, timeout=10) as dash_resp:
                print('DASH_STATUS', dash_resp.status)
                body_snippet = dash_resp.read(1000).decode('utf-8', errors='replace')
                print('DASH_BODY_START', body_snippet)
        except Exception as exc:
            print('DASH_ERROR', type(exc).__name__, exc)
    else:
        print('NO_REDIRECT_URL')
