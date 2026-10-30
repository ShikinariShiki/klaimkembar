"""Explicit loopback-only demo session adapter. Not production authentication."""
import hmac
import secrets
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from starlette.staticfiles import StaticFiles

from klaimkembar.errors import Rejection


def local_request(request: Request) -> bool:
    host = urlsplit(str(request.url)).hostname
    return host in {'localhost', '127.0.0.1', '::1'} and request.client is not None and request.client.host in {'127.0.0.1', '::1', 'testclient'}


def same_origin(request: Request) -> bool:
    origin = request.headers.get('origin')
    return origin == str(request.base_url).rstrip('/')


def session_actor(request: Request, sessions: dict[str, tuple[str, float]]) -> bool:
    if not local_request(request):
        return False
    item = sessions.get(request.cookies.get('kk_session', ''))
    if item is None or item[1] < time.monotonic():
        return False
    if request.method not in {'GET', 'HEAD'}:
        if not same_origin(request) or not hmac.compare_digest(request.headers.get('x-csrf-token', ''), item[0]):
            raise Rejection(403, 'CSRF_REJECTED', 'Permintaan harus berasal dari aplikasi lokal yang sama. Muat ulang halaman.')
    return True


def install_ui(app: FastAPI, root: Path) -> None:
    sessions: dict[str, tuple[str, float]] = {}
    app.state.ui_sessions = sessions

    @app.post('/ui/session')
    def bootstrap(request: Request) -> JSONResponse:
        if not local_request(request) or not same_origin(request):
            raise Rejection(403, 'LOCAL_ONLY', 'Antarmuka demo hanya tersedia dari localhost dengan origin yang sama.')
        now = time.monotonic()
        expired = [key for key, value in sessions.items() if value[1] <= now]
        for key in expired:
            del sessions[key]
        if len(sessions) >= 100:
            raise Rejection(429, 'SESSION_LIMIT', 'Terlalu banyak sesi lokal. Tutup aplikasi dan jalankan ulang.')
        identity, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        sessions[identity] = (csrf, now + 8 * 3600)
        response = JSONResponse({'csrf': csrf, 'mode': 'local_synthetic_demo'}, headers={'Cache-Control': 'no-store'})
        response.set_cookie('kk_session', identity, httponly=True, samesite='strict', max_age=8 * 3600, path='/')
        return response

    @app.get('/', include_in_schema=False)
    def index(request: Request) -> Any:
        if not local_request(request):
            raise Rejection(403, 'LOCAL_ONLY', 'Gunakan aplikasi melalui localhost.')
        return FileResponse(root / 'frontend/index.html', headers={'Cache-Control': 'no-cache'})

    @app.get('/sample.csv', include_in_schema=False)
    def sample(request: Request) -> Any:
        if not local_request(request):
            raise Rejection(403, 'LOCAL_ONLY', 'Gunakan aplikasi melalui localhost.')
        return FileResponse(root / 'examples/claims.csv', filename='klaim_fisioterapi_sintetis.csv', media_type='text/csv')

    @app.get('/bpjs2025-sample.csv', include_in_schema=False)
    def bpjs_sample(request: Request) -> Any:
        if not local_request(request):
            raise Rejection(403, 'LOCAL_ONLY', 'Gunakan aplikasi melalui localhost.')
        return FileResponse(root / 'examples/bpjs2025_claims.csv', filename='klaim_fisioterapi_bpjs2025_sintetis.csv', media_type='text/csv')

    app.mount('/assets', StaticFiles(directory=root / 'frontend'), name='frontend')
