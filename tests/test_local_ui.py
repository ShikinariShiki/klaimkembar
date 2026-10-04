import secrets
import time
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from klaimkembar.app import create_app
from klaimkembar.database import Database
from klaimkembar.settings import Settings
from tests.test_api import demo_csv


@pytest.fixture
def local(tmp_path):
    db = Database(tmp_path / 'ui.sqlite')
    db.migrate()
    config = Settings(db.path, secrets.token_urlsafe(32), secrets.token_urlsafe(32), local_ui=True)
    with TestClient(create_app(config), base_url='http://127.0.0.1:8000') as client:
        yield client


def login(client):
    response = client.post('/ui/session', headers={'origin': 'http://127.0.0.1:8000'})
    assert response.status_code == 200
    assert 'HttpOnly' in response.headers['set-cookie']
    assert 'SameSite=strict' in response.headers['set-cookie']
    assert response.headers['cache-control'] == 'no-store'
    return {'origin': 'http://127.0.0.1:8000', 'x-csrf-token': response.json()['csrf']}


def upload(client, headers):
    return client.post('/api/v1/datasets/upload', headers=headers, data={'synthetic': 'true'},
                       files={'file': ('demo.csv', demo_csv(), 'text/csv')})


def test_local_ui_full_cycle(local):
    assert local.get('/').status_code == 200
    assert local.get('/assets/app.js').status_code == 200
    assert local.get('/sample.csv').status_code == 200
    headers = login(local)
    result = upload(local, headers)
    assert result.status_code == 201
    dataset = result.json()['dataset_id']
    facets = local.get('/api/v1/facets', params={'dataset_id': dataset}).json()
    assert facets['facilities'] and facets['reasons']
    case = local.get('/api/v1/cases', params={'dataset_id': dataset}).json()['items'][0]
    payload = {'review_id': str(uuid4()), 'expected_version': case['version'], 'decision': 'valid', 'note': 'Sintetis.'}
    reviewed = local.post(f"/api/v1/cases/{case['case_id']}/review", headers=headers, json=payload)
    assert reviewed.status_code == 200
    assert local.get(f"/api/v1/cases/{case['case_id']}").json()['reviews'][0]['note'] == 'Sintetis.'
    assert local.get('/api/v1/evaluation', params={'dataset_id': dataset}).status_code == 200


@pytest.mark.parametrize('origin', [None, 'https://evil.example', 'http://localhost:8000'])
def test_bootstrap_requires_exact_origin(local, origin):
    assert local.post('/ui/session', headers={'origin': origin} if origin else {}).status_code == 403


def test_cookie_writes_require_csrf_and_origin(local):
    headers = login(local)
    assert upload(local, {}).status_code == 403
    assert upload(local, {'origin': headers['origin'], 'x-csrf-token': 'incorrect'}).status_code == 403
    assert upload(local, {'origin': 'https://evil.example', 'x-csrf-token': headers['x-csrf-token']}).status_code == 403


def test_session_expiry(local):
    headers = login(local)
    for key, value in local.app.state.ui_sessions.items():
        local.app.state.ui_sessions[key] = (value[0], time.monotonic() - 1)
    assert upload(local, headers).status_code == 401
    assert login(local)


def test_host_and_remote_client_rejected(local):
    assert local.get('/', headers={'host': 'evil.example'}).status_code == 403
    assert local.post('/ui/session', headers={'host': 'evil.example', 'origin': 'http://evil.example'}).status_code == 403
    with TestClient(local.app, base_url='http://127.0.0.1:8000', client=('203.0.113.2', 12345)) as remote:
        assert remote.get('/').status_code == 403
        assert remote.post('/ui/session', headers={'origin': 'http://127.0.0.1:8000'}).status_code == 403


def test_default_mode_has_no_demo_session(tmp_path):
    db = Database(tmp_path / 'no-ui.sqlite')
    db.migrate()
    config = Settings(db.path, secrets.token_urlsafe(32), secrets.token_urlsafe(32))
    with TestClient(create_app(config)) as client:
        assert client.post('/ui/session').status_code == 404
        assert client.get('/').status_code == 404


def test_facets_require_auth_and_known_dataset(local):
    assert local.get('/api/v1/facets', params={'dataset_id': str(uuid4())}).status_code == 401
    login(local)
    assert local.get('/api/v1/facets', params={'dataset_id': 'invalid-uuid'}).status_code == 422
    assert local.get('/api/v1/facets', params={'dataset_id': str(uuid4())}).status_code == 404


def test_session_limit(local):
    local.app.state.ui_sessions.update({str(i): ('csrf', time.monotonic() + 60) for i in range(100)})
    assert local.post('/ui/session', headers={'origin': 'http://127.0.0.1:8000'}).status_code == 429
