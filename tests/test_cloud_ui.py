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


def test_users_module_lifecycle(tmp_path):
    from klaimkembar.errors import Rejection
    from klaimkembar.users import (
        DEMO_EMAIL,
        DEMO_PASSWORD,
        authenticate_user,
        ensure_demo_user,
        hash_password,
        register_user,
        verify_password,
    )

    db = Database(tmp_path / "users_test.sqlite")
    db.migrate()

    # 1. Password hashing & verification
    pwd = "SecretPass123!"
    hashed = hash_password(pwd)
    assert hashed.startswith("pbkdf2_sha256$120000$")
    assert verify_password(pwd, hashed)
    assert not verify_password("WrongPass", hashed)
    assert not verify_password(pwd, "invalid$format")

    # 2. Demo user auto-provisioning
    demo = ensure_demo_user(db)
    assert demo["email"] == DEMO_EMAIL
    assert demo["role"] == "reviewer"

    # Subsequent call returns same user
    demo2 = ensure_demo_user(db)
    assert demo2["id"] == demo["id"]

    # Authenticate demo user
    auth_demo = authenticate_user(db, DEMO_EMAIL, DEMO_PASSWORD)
    assert auth_demo is not None
    assert auth_demo["email"] == DEMO_EMAIL

    # 3. User registration
    new_user = register_user(
        db,
        email="auditor@bpjs.go.id",
        password="AuditorPassword123!",
        full_name="dr. Hendra Auditor",
        role="auditor",
        institution="BPJS Kedeputian Wilayah",
    )
    assert new_user["email"] == "auditor@bpjs.go.id"
    assert new_user["role"] == "auditor"

    # Duplicate registration fails
    with pytest.raises(Rejection) as exc_info:
        register_user(
            db,
            email="auditor@bpjs.go.id",
            password="OtherPassword123!",
            full_name="dr. Hendra Duplikat",
        )
    assert exc_info.value.status == 409
    assert exc_info.value.code == "EMAIL_EXISTS"

    # Validation errors
    with pytest.raises(Rejection):
        register_user(db, email="invalid-email", password="123", full_name="X")
    with pytest.raises(Rejection):
        register_user(db, email="valid@bpjs.go.id", password="123", full_name="Valid Name")
    with pytest.raises(Rejection):
        register_user(db, email="valid2@bpjs.go.id", password="ValidPassword123!", full_name="Valid", role="superadmin")

    # Authenticate registered user
    auth_user = authenticate_user(db, "auditor@bpjs.go.id", "AuditorPassword123!")
    assert auth_user is not None
    assert auth_user["role"] == "auditor"

    # Non-existent or wrong password returns None
    assert authenticate_user(db, "auditor@bpjs.go.id", "WrongPassword") is None
    assert authenticate_user(db, "nonexistent@bpjs.go.id", "AnyPassword") is None


def test_cloud_registration_and_login_flow(tmp_path):
    db = Database(tmp_path / "cloud_auth.sqlite")
    db.migrate()
    password, secret = secrets.token_urlsafe(40), secrets.token_urlsafe(40)
    config = Settings(
        db.path,
        secrets.token_urlsafe(32),
        secrets.token_urlsafe(32),
        cloud_demo=True,
        cloud_origin=ORIGIN,
        cloud_session_secret=secret,
        cloud_demo_passcode=password,
    )

    with TestClient(create_app(config), base_url=ORIGIN, follow_redirects=False) as c:
        # GET pages
        assert c.get("/login").status_code == 200
        assert c.get("/register").status_code == 200

        # Form Registration: reviewer
        reg_resp = c.post(
            "/ui/register",
            data={
                "email": "reviewer2@klaimkembar.id",
                "password": "PasswordReviewer123!",
                "full_name": "dr. Budi Santoso",
                "role": "reviewer",
                "institution": "RSUD Tarakan",
            },
            headers={"origin": ORIGIN},
        )
        assert reg_resp.status_code == 303
        assert reg_resp.headers["location"] == "/"
        assert "kk_demo_session" in reg_resp.headers["set-cookie"]

        # Session inspection
        sess_resp = c.post("/ui/session", headers={"origin": ORIGIN})
        assert sess_resp.status_code == 200
        sess_data = sess_resp.json()
        assert sess_data["user"]["email"] == "reviewer2@klaimkembar.id"
        assert sess_data["user"]["role"] == "reviewer"
        assert sess_data["user"]["full_name"] == "dr. Budi Santoso"
        csrf = sess_data["csrf"]

        # Reviewer can upload
        sample = (ROOT / "examples/claims.csv").read_bytes()
        upload_resp = c.post(
            "/api/v1/datasets/upload",
            headers={"origin": ORIGIN, "x-csrf-token": csrf},
            data={"synthetic": "true"},
            files={"file": ("sample.csv", sample, "text/csv")},
        )
        assert upload_resp.status_code == 201

        # Register JSON as auditor
        json_reg = c.post(
            "/ui/register",
            json={
                "email": "auditor2@klaimkembar.id",
                "password": "PasswordAuditor123!",
                "full_name": "Auditor Independen BPKP",
                "role": "auditor",
                "institution": "BPKP",
            },
            headers={"origin": ORIGIN, "content-type": "application/json"},
        )
        assert json_reg.status_code == 200
        assert json_reg.json()["ok"] is True
        assert json_reg.json()["user"]["role"] == "auditor"

        # Check auditor session
        aud_sess = c.post("/ui/session", headers={"origin": ORIGIN}).json()
        assert aud_sess["user"]["role"] == "auditor"
        aud_csrf = aud_sess["csrf"]

        # Auditor cannot upload (403 ROLE_FORBIDDEN)
        aud_upload = c.post(
            "/api/v1/datasets/upload",
            headers={"origin": ORIGIN, "x-csrf-token": aud_csrf},
            data={"synthetic": "true"},
            files={"file": ("sample.csv", sample, "text/csv")},
        )
        assert aud_upload.status_code == 403
        assert aud_upload.json()["error"]["code"] == "ROLE_FORBIDDEN"

        # Duplicate registration with JSON returns 409
        dup_json = c.post(
            "/ui/register",
            json={
                "email": "auditor2@klaimkembar.id",
                "password": "PasswordAuditor123!",
                "full_name": "Auditor Duplikat",
            },
            headers={"origin": ORIGIN, "content-type": "application/json"},
        )
        assert dup_json.status_code == 409
        assert dup_json.json()["error"]["code"] == "EMAIL_EXISTS"

        # Origin rejection on register
        evil_reg = c.post(
            "/ui/register",
            data={"email": "evil@example.test", "password": "EvilPassword123!"},
            headers={"origin": "https://attacker.example"},
        )
        assert evil_reg.status_code == 403

        # Email + password Login
        login_resp = c.post(
            "/ui/login",
            data={"email": "reviewer2@klaimkembar.id", "password": "PasswordReviewer123!"},
            headers={"origin": ORIGIN},
        )
        assert login_resp.status_code == 303
        assert login_resp.headers["location"] == "/"

        # Wrong password Login
        wrong_resp = c.post(
            "/ui/login",
            data={"email": "reviewer2@klaimkembar.id", "password": "WrongPassword!"},
            headers={"origin": ORIGIN},
        )
        assert wrong_resp.status_code == 403

        # 1-Click Demo Login
        demo_login = c.post(
            "/ui/login",
            data={"demo": "1"},
            headers={"origin": ORIGIN},
        )
        assert demo_login.status_code == 303
        demo_sess = c.post("/ui/session", headers={"origin": ORIGIN}).json()
        assert demo_sess["user"]["email"] == "verifikator@klaimkembar.id"
        assert demo_sess["user"]["role"] == "reviewer"



def test_landing_page_and_extended_auth(tmp_path):
    db = Database(tmp_path / 'cloud_extended.sqlite')
    db.migrate()
    password, secret = secrets.token_urlsafe(40), secrets.token_urlsafe(40)
    config = Settings(db.path, secrets.token_urlsafe(32), secrets.token_urlsafe(32),
                      cloud_demo=True, cloud_origin=ORIGIN, cloud_session_secret=secret, cloud_demo_passcode=password)
    with TestClient(create_app(config), base_url=ORIGIN, follow_redirects=False) as c:
        # Check landing page served at /login and /register
        login_res = c.get('/login')
        assert login_res.status_code == 200
        assert 'KlaimKembar' in login_res.text
        assert 'Prioritaskan Telaah Klaim Kembar' in login_res.text
        assert 'Portal Verifikator &amp; Auditor' in login_res.text
        assert 'CatBoost' in login_res.text

        reg_res = c.get('/register')
        assert reg_res.status_code == 200
        assert 'Daftar Verifikator' in reg_res.text

        # 1-Click Demo Login
        demo_resp = c.post('/ui/login', data={'demo': 'true'}, headers={'origin': ORIGIN})
        assert demo_resp.status_code == 303
        session_info = c.post('/ui/session', headers={'origin': ORIGIN}).json()
        assert session_info['user']['full_name'] == 'dr. Nadia Putri, M.Kes'
        assert session_info['user']['role'] == 'reviewer'

        # Logout
        c.post('/ui/logout', headers={'origin': ORIGIN, 'x-csrf-token': session_info['csrf']})

        # Standard Email & Password Login
        email_resp = c.post('/ui/login', data={'email': 'verifikator@klaimkembar.id', 'password': 'Healthkathon2026!'}, headers={'origin': ORIGIN})
        assert email_resp.status_code == 303
        user_sess = c.post('/ui/session', headers={'origin': ORIGIN}).json()
        assert 'dr. Nadia Putri' in user_sess['user']['full_name']

        # Logout
        c.post('/ui/logout', headers={'origin': ORIGIN, 'x-csrf-token': user_sess['csrf']})

        # Register flow
        reg_submit = c.post('/ui/register', data={
            'full_name': 'dr. Budi Santoso, M.KK',
            'email': 'budi.santoso@bpjs-kesehatan.go.id',
            'institution': 'BPJS Kesehatan — Unit Telaah Klaim FKRTL',
            'role': 'auditor',
            'password': 'strongpassword2026'
        }, headers={'origin': ORIGIN})
        assert reg_submit.status_code == 303
        reg_sess = c.post('/ui/session', headers={'origin': ORIGIN}).json()
        assert reg_sess['user']['full_name'] == 'dr. Budi Santoso, M.KK'
        assert reg_sess['user']['role'] == 'auditor'

