"""Stateless shared-passcode gateway for a synthetic-data demo only.

This is not individual authentication and must not be used for real claims.
"""
import base64
import hashlib
import hmac
import secrets
import time
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Form, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from starlette.staticfiles import StaticFiles

from klaimkembar.errors import Rejection

_COOKIE = 'kk_demo_session'
_TTL = 8 * 3600


def _sign(payload: str, secret: str) -> str:
    return hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()


def _issue(secret: str) -> tuple[str, str]:
    csrf = secrets.token_urlsafe(32)
    payload = base64.urlsafe_b64encode(f'{int(time.time()) + _TTL}:{csrf}'.encode()).decode()
    return f'{payload}.{_sign(payload, secret)}', csrf


def _read(request: Request, secret: str) -> str | None:
    token = request.cookies.get(_COOKIE, '')
    if len(token) > 512:
        return None
    try:
        payload, signature = token.split('.', 1)
        if not hmac.compare_digest(signature, _sign(payload, secret)):
            return None
        expiration, csrf = base64.b64decode(payload.encode(), altchars=b'-_', validate=True).decode().split(':', 1)
        if int(expiration) <= int(time.time()) or len(csrf) < 32:
            return None
        return csrf
    except (ValueError, UnicodeDecodeError):
        return None


def cloud_session_actor(request: Request, secret: str, origin: str) -> bool:
    csrf = _read(request, secret)
    if csrf is None:
        return False
    if request.method not in {'GET', 'HEAD', 'OPTIONS'}:
        if request.headers.get('origin') != origin or not hmac.compare_digest(request.headers.get('x-csrf-token', ''), csrf):
            raise Rejection(403, 'CSRF_REJECTED', 'Permintaan harus berasal dari aplikasi yang sama.')
    return True


def install_cloud_ui(app: FastAPI, root: Path, origin: str, secret: str, passcode: str) -> None:
    @app.get('/login', include_in_schema=False)
    def login_page() -> HTMLResponse:
        return HTMLResponse('''<!doctype html><html lang="id"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Masuk KlaimKembar</title><style>body{font-family:system-ui;background:#f5f6ff;color:#202441;display:grid;place-items:center;min-height:100vh;margin:0}main{background:#fff;padding:2rem;border-radius:16px;width:min(90vw,390px);box-sizing:border-box;box-shadow:0 8px 32px #2222}input,button{width:100%;box-sizing:border-box;padding:12px;font:inherit;border-radius:8px}input{border:1px solid #aaa}button{margin-top:16px;background:#5141ed;color:white;border:0;cursor:pointer}p{line-height:1.5}</style></head><body><main><h1>KlaimKembar</h1><p>Demo dengan data sintetis. Masukkan kode akses untuk melanjutkan.</p><form action="/ui/login" method="post"><label for="passcode">Kode akses demo</label><input id="passcode" name="passcode" type="password" autocomplete="current-password" required maxlength="256"><button type="submit">Masuk</button></form></main></body></html>''', headers={'Cache-Control': 'no-store'})

    @app.post('/ui/login', include_in_schema=False)
    def login(request: Request, passcode_input: str = Form(alias='passcode', max_length=256)) -> Any:
        if request.headers.get('origin') != origin or not hmac.compare_digest(passcode_input.encode(), passcode.encode()):
            return HTMLResponse('Kode akses tidak sesuai atau permintaan ditolak. <a href="/login">Coba lagi</a>.', status_code=403, headers={'Cache-Control': 'no-store'})
        token, _ = _issue(secret)
        response = RedirectResponse('/', status_code=303, headers={'Cache-Control': 'no-store'})
        response.set_cookie(_COOKIE, token, secure=True, httponly=True, samesite='strict', max_age=_TTL, path='/')
        return response

    @app.post('/ui/session', include_in_schema=False)
    def bootstrap(request: Request) -> JSONResponse:
        csrf = _read(request, secret)
        if csrf is None or request.headers.get('origin') != origin:
            raise Rejection(401, 'AUTH_REQUIRED', 'Sesi demo berakhir. Masuk kembali.')
        return JSONResponse({'csrf': csrf, 'mode': 'cloud_synthetic_demo'}, headers={'Cache-Control': 'no-store'})

    @app.post('/ui/logout', include_in_schema=False)
    def logout(request: Request) -> JSONResponse:
        if not cloud_session_actor(request, secret, origin):
            raise Rejection(401, 'AUTH_REQUIRED', 'Sesi demo berakhir.')
        response = JSONResponse({'ok': True}, headers={'Cache-Control': 'no-store'})
        response.delete_cookie(_COOKIE, secure=True, httponly=True, samesite='strict', path='/')
        return response

    @app.get('/', include_in_schema=False)
    def index(request: Request) -> Any:
        if _read(request, secret) is None:
            return RedirectResponse('/login', status_code=303, headers={'Cache-Control': 'no-store'})
        return FileResponse(root / 'frontend/index.html', headers={'Cache-Control': 'no-store'})

    @app.get('/sample.csv', include_in_schema=False)
    def sample(request: Request) -> Any:
        if _read(request, secret) is None:
            raise Rejection(401, 'AUTH_REQUIRED', 'Masuk terlebih dahulu.')
        return FileResponse(root / 'examples/claims.csv', filename='klaim_fisioterapi_sintetis.csv', media_type='text/csv', headers={'Cache-Control': 'no-store'})

    app.mount('/assets', StaticFiles(directory=root / 'frontend'), name='frontend')
