"""End-to-end business and role-isolation tests against the running stack."""
import json
import os
import time
import urllib.request
import urllib.error
import http.cookiejar
import uuid
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

BASE = os.getenv('BASE_URL', 'http://127.0.0.1:8080')
config = dict(line.split('=',1) for line in Path('.env').read_text().splitlines()
              if '=' in line and not line.startswith('#')) if Path('.env').exists() else {}
PASSWORD = os.getenv('ADMIN_PASSWORD') or config['ADMIN_PASSWORD']

class Client:
    def __init__(self):
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))
        self.csrf = ''

    def call(self, path, method='GET', data=None, expected=200, csrf=True, extra_headers=None):
        time.sleep(0.12)  # Respect Nginx's 10 requests/second API limit.
        headers = {'Content-Type':'application/json','Origin':BASE}
        if csrf:
            headers['X-CSRF-Token'] = self.csrf
        headers.update(extra_headers or {})
        req = urllib.request.Request(BASE+path, method=method,
            data=json.dumps(data).encode() if data is not None else None, headers=headers)
        try:
            response = self.opener.open(req, timeout=10)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            content = response.read()
            assert response.status == expected, (path, response.status, content)
            return json.loads(content)

    def login(self, username, password):
        result = self.call('/api/auth/login', 'POST', {'username':username,'password':password})
        self.csrf = result['csrf_token']
        return result['user']

