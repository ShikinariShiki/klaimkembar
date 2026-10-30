"""Stateless shared-passcode and user authentication gateway for a synthetic-data demo.

This is individual authentication for the cloud prototype and must not be used for real claims.
"""
import base64
import hashlib
import hmac
import json
import secrets
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from starlette.staticfiles import StaticFiles

from klaimkembar.errors import Rejection
from klaimkembar.users import (
    DEMO_EMAIL,
    DEMO_INSTITUTION,
    DEMO_NAME,
    DEMO_PASSWORD,
    authenticate_user,
    ensure_demo_user,
    register_user,
)

_COOKIE = "kk_demo_session"
_TTL = 8 * 3600


def _sign(payload: str, secret: str) -> str:
    return hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()


def _issue(secret: str, user: dict[str, str] | None = None) -> tuple[str, str]:
    csrf = secrets.token_urlsafe(32)
    session_data = {
        "exp": int(time.time()) + _TTL,
        "csrf": csrf,
        "email": user.get("email", DEMO_EMAIL) if user else DEMO_EMAIL,
        "full_name": user.get("full_name", DEMO_NAME) if user else DEMO_NAME,
        "role": user.get("role", "reviewer") if user else "reviewer",
        "institution": user.get("institution", DEMO_INSTITUTION) if user else DEMO_INSTITUTION,
    }
    raw = json.dumps(session_data, separators=(",", ":")).encode()
    payload = base64.urlsafe_b64encode(raw).decode()
    return f"{payload}.{_sign(payload, secret)}", csrf


def _read_session(request: Request, secret: str) -> dict[str, Any] | None:
    token = request.cookies.get(_COOKIE, "")
    if not token or len(token) > 2048:
        return None
    try:
        payload, signature = token.split(".", 1)
        if not hmac.compare_digest(signature, _sign(payload, secret)):
            return None
        decoded = base64.b64decode(payload.encode(), altchars=b"-_", validate=True).decode()
        if decoded.startswith("{"):
            data = json.loads(decoded)
            exp = int(data.get("exp", 0))
            csrf = str(data.get("csrf", ""))
            if exp <= int(time.time()) or len(csrf) < 32:
                return None
            return {
                "csrf": csrf,
                "expiration": exp,
                "email": str(data.get("email", DEMO_EMAIL)),
                "full_name": str(data.get("full_name", DEMO_NAME)),
                "role": str(data.get("role", "reviewer")),
                "institution": str(data.get("institution", DEMO_INSTITUTION)),
            }
        else:
            expiration, csrf = decoded.split(":", 1)
            if int(expiration) <= int(time.time()) or len(csrf) < 32:
                return None
            return {
                "csrf": csrf,
                "expiration": int(expiration),
                "email": DEMO_EMAIL,
                "full_name": DEMO_NAME,
                "role": "reviewer",
                "institution": DEMO_INSTITUTION,
            }
    except (ValueError, UnicodeDecodeError, KeyError, json.JSONDecodeError):
        return None


def _read(request: Request, secret: str) -> str | None:
    session = _read_session(request, secret)
    return session["csrf"] if session else None


def cloud_session_user(request: Request, secret: str) -> dict[str, Any] | None:
    return _read_session(request, secret)


def _origin_allowed(request: Request, configured_origin: str, allow_null_form: bool = False) -> bool:
    origin_header = request.headers.get("origin")

    # Allow null or missing origin only for form submissions from same-origin / navigation
    if origin_header is None or origin_header == "null":
        if allow_null_form:
            sec_fetch_site = request.headers.get("sec-fetch-site")
            if sec_fetch_site in (None, "same-origin", "none"):
                return True
        return False

    # Normalize configured origin
    configured = configured_origin.rstrip("/")
    allowed = {configured}

    # Request host/netloc origin
    host_header = request.headers.get("host") or request.url.netloc
    scheme = request.headers.get("x-forwarded-proto") or request.url.scheme or "https"
    if host_header:
        allowed.add(f"{scheme}://{host_header}".rstrip("/"))

    # Forwarded host origin
    x_forwarded_host = request.headers.get("x-forwarded-host")
    if x_forwarded_host:
        allowed.add(f"https://{x_forwarded_host}".rstrip("/"))

    header_clean = origin_header.rstrip("/")
    if header_clean in allowed:
        return True

    # Allow official Vercel preview/production domains for klaimkembar-demo
    if header_clean.startswith("https://klaimkembar-demo") and header_clean.endswith(".vercel.app"):
        return True

    return False


def cloud_session_actor(request: Request, secret: str, origin: str) -> bool:
    csrf = _read(request, secret)
    if csrf is None:
        return False
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        if not _origin_allowed(request, origin, allow_null_form=False) or not hmac.compare_digest(request.headers.get("x-csrf-token", ""), csrf):
            raise Rejection(403, "CSRF_REJECTED", "Permintaan harus berasal dari aplikasi yang sama.")
    return True


def _render_auth_page(tab: str = "login", error: str = "") -> str:
    is_reg = tab == "register"
    error_box = f'<div class="alert-error">{error}</div>' if error else ""
    return f"""<!doctype html>
<html lang="id">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>KlaimKembar — Masuk / Daftar</title>
  <style>
    :root {{
      --primary: #0284c7;
      --primary-dark: #0369a1;
      --bg: #f8fafc;
      --card-bg: #ffffff;
      --text: #0f172a;
      --text-muted: #64748b;
      --border: #e2e8f0;
      --radius: 12px;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      background: var(--bg);
      color: var(--text);
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      padding: 1.5rem;
    }}
    .auth-container {{
      background: var(--card-bg);
      width: 100%;
      max-width: 440px;
      border-radius: var(--radius);
      box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.05), 0 8px 10px -6px rgba(0, 0, 0, 0.05);
      border: 1px solid var(--border);
      overflow: hidden;
    }}
    .auth-header {{
      padding: 2rem 2rem 1.25rem;
      text-align: center;
      background: linear-gradient(180deg, #f0f9ff 0%, #ffffff 100%);
      border-bottom: 1px solid var(--border);
    }}
    .brand-badge {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      font-size: 0.75rem;
      font-weight: 600;
      color: var(--primary-dark);
      background: #e0f2fe;
      padding: 4px 10px;
      border-radius: 9999px;
      margin-bottom: 0.75rem;
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }}
    .auth-header h1 {{
      font-size: 1.5rem;
      font-weight: 700;
      color: var(--text);
      letter-spacing: -0.025em;
    }}
    .auth-header p {{
      font-size: 0.875rem;
      color: var(--text-muted);
      margin-top: 0.35rem;
    }}
    .tabs {{
      display: flex;
      border-bottom: 1px solid var(--border);
      background: #f1f5f9;
    }}
    .tab-btn {{
      flex: 1;
      padding: 0.75rem;
      text-align: center;
      font-size: 0.875rem;
      font-weight: 600;
      color: var(--text-muted);
      text-decoration: none;
      border-bottom: 2px solid transparent;
      transition: all 0.2s;
    }}
    .tab-btn.active {{
      background: #ffffff;
      color: var(--primary);
      border-bottom-color: var(--primary);
    }}
    .auth-body {{
      padding: 1.75rem 2rem 2rem;
    }}
    .alert-error {{
      background: #fef2f2;
      border: 1px solid #fecaca;
      color: #b91c1c;
      padding: 0.75rem 1rem;
      border-radius: 8px;
      font-size: 0.875rem;
      margin-bottom: 1.25rem;
    }}
    .form-group {{
      margin-bottom: 1.15rem;
    }}
    .form-group label {{
      display: block;
      font-size: 0.8125rem;
      font-weight: 600;
      color: var(--text);
      margin-bottom: 0.35rem;
    }}
    .form-control {{
      width: 100%;
      padding: 0.65rem 0.85rem;
      font-size: 0.875rem;
      border: 1px solid var(--border);
      border-radius: 8px;
      outline: none;
      transition: border-color 0.15s;
    }}
    .form-control:focus {{
      border-color: var(--primary);
      box-shadow: 0 0 0 3px rgba(2, 132, 199, 0.15);
    }}
    .btn {{
      display: block;
      width: 100%;
      padding: 0.75rem 1rem;
      font-size: 0.875rem;
      font-weight: 600;
      text-align: center;
      border-radius: 8px;
      border: none;
      cursor: pointer;
      transition: background-color 0.15s;
    }}
    .btn-primary {{
      background: var(--primary);
      color: #ffffff;
    }}
    .btn-primary:hover {{
      background: var(--primary-dark);
    }}
    .btn-demo {{
      background: #f0fdf4;
      color: #166534;
      border: 1px solid #bbf7d0;
      margin-top: 1rem;
    }}
    .btn-demo:hover {{
      background: #dcfce7;
    }}
    .divider {{
      position: relative;
      text-align: center;
      margin: 1.5rem 0 1rem;
    }}
    .divider::before {{
      content: "";
      position: absolute;
      left: 0;
      top: 50%;
      width: 100%;
      height: 1px;
      background: var(--border);
    }}
    .divider span {{
      position: relative;
      background: var(--card-bg);
      padding: 0 0.75rem;
      font-size: 0.75rem;
      color: var(--text-muted);
      text-transform: uppercase;
    }}
    .footer-note {{
      margin-top: 1.5rem;
      text-align: center;
      font-size: 0.75rem;
      color: var(--text-muted);
    }}
  </style>
</head>
<body>
  <div class="auth-container">
    <div class="auth-header">
      <div class="brand-badge">BPJS Kesehatan — Unit Telaah Klaim</div>
      <h1>KlaimKembar</h1>
      <p>Sistem Deteksi Duplikasi & Audit Klaim FKRTL</p>
    </div>

    <div class="tabs">
      <a href="/login" class="tab-btn {'active' if not is_reg else ''}">Masuk</a>
      <a href="/register" class="tab-btn {'active' if is_reg else ''}">Daftar Akun</a>
    </div>

    <div class="auth-body">
      {error_box}

      {"<!-- Register Form -->" if is_reg else "<!-- Login Form -->"}
      {'''
      <form action="/ui/register" method="post">
        <div class="form-group">
          <label for="reg-name">Nama Lengkap</label>
          <input id="reg-name" name="full_name" type="text" class="form-control" required placeholder="dr. Ahmad Fauzi" maxlength="100">
        </div>
        <div class="form-group">
          <label for="reg-email">Email Instansi / Pribadi</label>
          <input id="reg-email" name="email" type="email" class="form-control" required placeholder="verifikator@instansi.id" maxlength="254">
        </div>
        <div class="form-group">
          <label for="reg-password">Kata Sandi (min. 6 karakter)</label>
          <input id="reg-password" name="password" type="password" class="form-control" required minlength="6" placeholder="••••••••">
        </div>
        <div class="form-group">
          <label for="reg-role">Peran Penelaah</label>
          <select id="reg-role" name="role" class="form-control">
            <option value="reviewer" selected>Petugas Pemeriksa (Reviewer)</option>
            <option value="auditor">Auditor Independen (Read-only)</option>
          </select>
        </div>
        <div class="form-group">
          <label for="reg-inst">Instansi</label>
          <input id="reg-inst" name="institution" type="text" class="form-control" value="BPJS Kesehatan — Unit Telaah Klaim" maxlength="200">
        </div>
        <button type="submit" class="btn btn-primary">Daftar & Masuk</button>
      </form>
      ''' if is_reg else f'''
      <form action="/ui/login" method="post">
        <div class="form-group">
          <label for="log-email">Email</label>
          <input id="log-email" name="email" type="email" class="form-control" required placeholder="{DEMO_EMAIL}" value="{DEMO_EMAIL}">
        </div>
        <div class="form-group">
          <label for="log-password">Kata Sandi</label>
          <input id="log-password" name="password" type="password" class="form-control" required placeholder="••••••••" value="{DEMO_PASSWORD}">
        </div>
        <button type="submit" class="btn btn-primary">Masuk</button>
      </form>

      <div class="divider"><span>Atau</span></div>

      <form action="/ui/login" method="post">
        <input type="hidden" name="demo" value="1">
        <button type="submit" class="btn btn-demo">⚡ Masuk Cepat Demo (1-Klik)</button>
      </form>
      '''}

      <div class="footer-note">
        Lingkungan demo data sintetis terisolasi. Seluruh data pasien telah dianonimisasi.
      </div>
    </div>
  </div>
</body>
</html>"""


def install_cloud_ui(
    app: FastAPI,
    root: Path,
    origin: str,
    secret: str,
    passcode: str,
    db: Any = None,
) -> None:
    def get_db() -> Any:
        if db is not None:
            return db
        wf = getattr(getattr(app, "state", None), "workflow", None)
        return getattr(wf, "db", None)

    @app.get("/login", include_in_schema=False)
    @app.get("/register", include_in_schema=False)
    def auth_page(request: Request) -> Any:
        landing_file = root / "frontend/landing.html"
        if landing_file.exists():
            return FileResponse(landing_file, headers={"Cache-Control": "no-store"})

        tab = "register" if request.url.path == "/register" or request.query_params.get("tab") == "register" else "login"
        error = request.query_params.get("error", "")
        return HTMLResponse(_render_auth_page(tab=tab, error=error), headers={"Cache-Control": "no-store"})

    @app.post("/ui/register", include_in_schema=False)
    async def register(request: Request) -> Any:
        if not _origin_allowed(request, origin, allow_null_form=True):
            raise Rejection(403, "ORIGIN_REJECTED", "Permintaan harus berasal dari aplikasi yang sama.")

        content_type = request.headers.get("content-type", "")
        is_json = "application/json" in content_type or request.headers.get("accept") == "application/json"

        if "application/json" in content_type:
            try:
                data = await request.json()
            except Exception:
                raise Rejection(400, "INVALID_JSON", "Format JSON tidak valid.")
        else:
            form = await request.form()
            data = dict(form)

        email = str(data.get("email", ""))
        password = str(data.get("password", ""))
        full_name = str(data.get("full_name", ""))
        role = str(data.get("role", "reviewer"))
        institution = str(data.get("institution", "BPJS Kesehatan — Unit Telaah Klaim"))

        try:
            target_db = get_db()
            user = register_user(
                target_db,
                email=email,
                password=password,
                full_name=full_name,
                role=role,
                institution=institution,
            )
        except Rejection as exc:
            if is_json:
                raise exc
            return RedirectResponse(
                f"/login?tab=register&error={quote_plus(exc.message)}",
                status_code=303,
                headers={"Cache-Control": "no-store"},
            )

        token, _ = _issue(secret, user)
        if is_json:
            response: Any = JSONResponse({"ok": True, "redirect": "/", "user": user}, headers={"Cache-Control": "no-store"})
        else:
            response = RedirectResponse("/", status_code=303, headers={"Cache-Control": "no-store"})
        response.set_cookie(_COOKIE, token, secure=True, httponly=True, samesite="strict", max_age=_TTL, path="/")
        return response

    @app.post("/ui/login", include_in_schema=False)
    async def login(request: Request) -> Any:
        if not _origin_allowed(request, origin, allow_null_form=True):
            return HTMLResponse(
                "Kode akses tidak sesuai atau permintaan ditolak. <a href=\"/login\">Coba lagi</a>.",
                status_code=403,
                headers={"Cache-Control": "no-store"},
            )

        content_type = request.headers.get("content-type", "")
        is_json = "application/json" in content_type or request.headers.get("accept") == "application/json"

        if "application/json" in content_type:
            try:
                data = await request.json()
            except Exception:
                return HTMLResponse("Format JSON tidak valid.", status_code=400, headers={"Cache-Control": "no-store"})
        else:
            form = await request.form()
            data = dict(form)

        target_db = get_db()
        user: dict[str, str] | None = None

        # 1. Quick demo login
        demo_flag = data.get("demo") or request.query_params.get("demo")
        if demo_flag in (True, "1", "true", "True"):
            user = ensure_demo_user(target_db)

        # 2. Email + password login
        elif "email" in data and data["email"] and "password" in data and data["password"]:
            user = authenticate_user(target_db, str(data["email"]), str(data["password"]))
            if user is None:
                if is_json:
                    return JSONResponse({"error": "Email atau kata sandi tidak sesuai."}, status_code=403, headers={"Cache-Control": "no-store"})
                return HTMLResponse(
                    "Email atau kata sandi tidak sesuai. <a href=\"/login\">Coba lagi</a>.",
                    status_code=403,
                    headers={"Cache-Control": "no-store"},
                )

        # 3. Legacy passcode login fallback
        elif "passcode" in data and data["passcode"]:
            passcode_input = str(data["passcode"])
            if passcode and hmac.compare_digest(passcode_input.encode(), passcode.encode()):
                user = ensure_demo_user(target_db)
            else:
                if is_json:
                    return JSONResponse({"error": "Kode akses tidak sesuai."}, status_code=403, headers={"Cache-Control": "no-store"})
                return HTMLResponse(
                    "Kode akses tidak sesuai atau permintaan ditolak. <a href=\"/login\">Coba lagi</a>.",
                    status_code=403,
                    headers={"Cache-Control": "no-store"},
                )

        else:
            if is_json:
                return JSONResponse({"error": "Kredensial diperlukan."}, status_code=403, headers={"Cache-Control": "no-store"})
            return HTMLResponse(
                "Kredensial diperlukan. <a href=\"/login\">Coba lagi</a>.",
                status_code=403,
                headers={"Cache-Control": "no-store"},
            )

        token, _ = _issue(secret, user)
        if is_json:
            response: Any = JSONResponse({"ok": True, "redirect": "/", "user": user}, headers={"Cache-Control": "no-store"})
        else:
            response = RedirectResponse("/", status_code=303, headers={"Cache-Control": "no-store"})
        response.set_cookie(_COOKIE, token, secure=True, httponly=True, samesite="strict", max_age=_TTL, path="/")
        return response

    @app.post("/ui/session", include_in_schema=False)
    def bootstrap(request: Request) -> JSONResponse:
        session = _read_session(request, secret)
        if session is None or not _origin_allowed(request, origin, allow_null_form=False):
            raise Rejection(401, "AUTH_REQUIRED", "Sesi demo berakhir. Masuk kembali.")
        user_info = {
            "email": session["email"],
            "full_name": session["full_name"],
            "role": session["role"],
            "institution": session["institution"],
        }
        return JSONResponse(
            {"csrf": session["csrf"], "mode": "cloud_synthetic_demo", "user": user_info},
            headers={"Cache-Control": "no-store"},
        )

    @app.post("/ui/logout", include_in_schema=False)
    def logout(request: Request) -> JSONResponse:
        if not cloud_session_actor(request, secret, origin):
            raise Rejection(401, "AUTH_REQUIRED", "Sesi demo berakhir.")
        response = JSONResponse({"ok": True}, headers={"Cache-Control": "no-store"})
        response.delete_cookie(_COOKIE, secure=True, httponly=True, samesite="strict", path="/")
        return response

    @app.get("/", include_in_schema=False)
    def index(request: Request) -> Any:
        if _read(request, secret) is None:
            return RedirectResponse("/login", status_code=303, headers={"Cache-Control": "no-store"})
        return FileResponse(root / "frontend/index.html", headers={"Cache-Control": "no-store"})

    @app.get("/sample.csv", include_in_schema=False)
    def sample(request: Request) -> Any:
        if _read(request, secret) is None:
            raise Rejection(401, "AUTH_REQUIRED", "Masuk terlebih dahulu.")
        return FileResponse(
            root / "examples/claims.csv",
            filename="klaim_fisioterapi_sintetis.csv",
            media_type="text/csv",
            headers={"Cache-Control": "no-store"},
        )

    @app.get("/bpjs2025-sample.csv", include_in_schema=False)
    def bpjs_sample(request: Request) -> Any:
        if _read(request, secret) is None:
            raise Rejection(401, "AUTH_REQUIRED", "Masuk terlebih dahulu.")
        return FileResponse(
            root / "examples/bpjs2025_claims.csv",
            filename="klaim_fisioterapi_bpjs2025_sintetis.csv",
            media_type="text/csv",
            headers={"Cache-Control": "no-store"},
        )

    app.mount("/assets", StaticFiles(directory=root / "frontend"), name="frontend")
