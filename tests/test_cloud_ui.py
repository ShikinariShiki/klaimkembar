import secrets

import pytest
from fastapi.testclient import TestClient

from klaimkembar.app import create_app
from klaimkembar.database import Database
from klaimkembar.settings import ROOT, Settings
from tests.test_api import demo_csv

ORIGIN = 'https://demo.example.test'


def test_cloud_auth_csrf_and_stateless_session(tmp_path):
    db = Database(tmp_path / 'cloud.sqlite')
    db.migrate()
    password, secret = secrets.token_urlsafe(40), secrets.token_urlsafe(40)
    config = Settings(db.path, secrets.token_urlsafe(32), secrets.token_urlsafe(32),
                      cloud_demo=True, cloud_origin=ORIGIN, cloud_session_secret=secret, cloud_demo_passcode=password)
    with TestClient(create_app(config), base_url=ORIGIN, follow_redirects=False) as c:
        assert c.get('/').status_code == 303
        assert c.get('/sample.csv').status_code == 401
        assert c.get('/api/v1/ml/status').status_code == 401
        assert c.post('/ui/login', data={'passcode': password}, headers={'origin': 'https://evil.example'}).status_code == 403
        assert c.post('/ui/login', data={'passcode': 'invalid'}, headers={'origin': ORIGIN}).status_code == 403
        resp = c.post('/ui/login', data={'passcode': password}, headers={'origin': ORIGIN})
        assert resp.status_code == 303
        for value in ['HttpOnly', 'Secure', 'SameSite=strict']:
            assert value in resp.headers['set-cookie']
        assert c.get('/').status_code == 200
        assert c.get('/api/v1/ml/status').status_code == 200
        csrf = c.post('/ui/session', headers={'origin': ORIGIN}).json()['csrf']
        assert c.post('/api/v1/datasets/upload', data={'synthetic': 'true'}, files={'file': ('sample.csv', demo_csv(), 'text/csv')}).status_code == 403
        assert c.post('/api/v1/datasets/upload', headers={'origin': 'https://evil.example', 'x-csrf-token': csrf}, data={'synthetic': 'true'}, files={'file': ('sample.csv', demo_csv(), 'text/csv')}).status_code == 403
        headers = {'origin': ORIGIN, 'x-csrf-token': csrf}
        assert c.post('/api/v1/datasets/upload', headers=headers, data={'synthetic': 'true'}, files={'file': ('other.csv', demo_csv(), 'text/csv')}).status_code == 422
        sample = (ROOT / 'examples/claims.csv').read_bytes()
        assert c.post('/api/v1/datasets/upload', headers=headers, data={'synthetic': 'true'}, files={'file': ('sample.csv', sample, 'text/csv')}).status_code == 201
        assert c.get('/api/v1/ml/status').headers['cache-control'] == 'no-store'
        cookie = c.cookies.get('kk_demo_session')
    with TestClient(create_app(config), base_url=ORIGIN) as c2:
        c2.cookies.set('kk_demo_session', cookie, domain='demo.example.test', path='/')
        assert c2.get('/api/v1/ml/status').status_code == 200
        assert c2.post('/ui/logout', headers={'origin': ORIGIN, 'x-csrf-token': csrf}).status_code == 200
        assert c2.get('/api/v1/ml/status').status_code == 401
        c2.cookies.set('kk_demo_session', cookie + 'bad', domain='demo.example.test', path='/')
        assert c2.get('/api/v1/ml/status').status_code == 401


def test_cloud_settings_fail_closed(tmp_path):
    tokens = (tmp_path / 'db', 'r' * 32, 'a' * 32)
    with pytest.raises(ValueError):
        Settings(*tokens, cloud_demo=True, cloud_origin='http://example.test', cloud_session_secret='s'*32, cloud_demo_passcode='p'*32)
    with pytest.raises(ValueError):
        Settings(*tokens, cloud_demo=True, cloud_origin=ORIGIN, cloud_session_secret='short', cloud_demo_passcode='p'*32)
    with pytest.raises(ValueError):
        Settings(*tokens, cloud_demo=True, local_ui=True, cloud_origin=ORIGIN, cloud_session_secret='s'*32, cloud_demo_passcode='p'*32)
