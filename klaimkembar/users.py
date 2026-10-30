import hashlib
import hmac
import re
import secrets
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from klaimkembar.errors import Rejection

DEMO_EMAIL = "verifikator@klaimkembar.id"
DEMO_PASSWORD = "Healthkathon2026!"
DEMO_NAME = "dr. Nadia Putri, M.Kes"
DEMO_INSTITUTION = "BPJS Kesehatan — Unit Telaah Klaim FKRTL"

_EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    salt_hex = salt.hex()
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 120000)
    hash_hex = key.hex()
    return f"pbkdf2_sha256$120000${salt_hex}${hash_hex}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        parts = stored_hash.split("$")
        if len(parts) != 4 or parts[0] != "pbkdf2_sha256":
            return False
        iterations = int(parts[1])
        salt = bytes.fromhex(parts[2])
        expected_key = bytes.fromhex(parts[3])
        computed_key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
        return hmac.compare_digest(computed_key, expected_key)
    except (ValueError, TypeError, IndexError):
        return False


def ensure_demo_user(db: Any) -> dict[str, str]:
    if db is None:
        return {
            "id": "demo-reviewer-id",
            "email": DEMO_EMAIL,
            "full_name": DEMO_NAME,
            "role": "reviewer",
            "institution": DEMO_INSTITUTION,
        }

    with db.connect() as conn:
        row = conn.execute(
            "SELECT id, email, full_name, role, institution FROM users WHERE LOWER(email) = ?",
            (DEMO_EMAIL.lower(),),
        ).fetchone()
        if row is not None:
            return {
                "id": str(row["id"]),
                "email": str(row["email"]),
                "full_name": str(row["full_name"]),
                "role": str(row["role"]),
                "institution": str(row["institution"]),
            }

        user_id = str(uuid4())
        pw_hash = hash_password(DEMO_PASSWORD)
        created_at = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "INSERT INTO users (id, email, full_name, institution, role, password_hash, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (user_id, DEMO_EMAIL, DEMO_NAME, DEMO_INSTITUTION, "reviewer", pw_hash, created_at),
        )
        return {
            "id": user_id,
            "email": DEMO_EMAIL,
            "full_name": DEMO_NAME,
            "role": "reviewer",
            "institution": DEMO_INSTITUTION,
        }


def register_user(
    db: Any,
    email: str,
    password: str,
    full_name: str,
    role: str = "reviewer",
    institution: str = "BPJS Kesehatan — Unit Telaah Klaim",
) -> dict[str, str]:
    email = email.strip()
    if not _EMAIL_REGEX.match(email) or len(email) > 254:
        raise Rejection(422, "EMAIL_INVALID", "Format email tidak valid.")

    full_name = full_name.strip()
    if len(full_name) < 2 or len(full_name) > 100:
        raise Rejection(422, "NAME_INVALID", "Nama lengkap harus antara 2 hingga 100 karakter.")

    if len(password) < 6:
        raise Rejection(422, "PASSWORD_TOO_SHORT", "Kata sandi minimal 6 karakter.")

    role = role.strip().lower()
    if role not in ("reviewer", "auditor"):
        raise Rejection(422, "ROLE_INVALID", "Peran harus reviewer atau auditor.")

    institution = (institution or "BPJS Kesehatan — Unit Telaah Klaim").strip()
    if len(institution) < 2 or len(institution) > 200:
        raise Rejection(422, "INSTITUTION_INVALID", "Nama instansi tidak valid.")

    if db is None:
        raise Rejection(500, "DATABASE_UNAVAILABLE", "Database tidak tersedia.")

    with db.connect() as conn:
        row = conn.execute(
            "SELECT id FROM users WHERE LOWER(email) = ?",
            (email.lower(),),
        ).fetchone()
        if row is not None:
            raise Rejection(409, "EMAIL_EXISTS", "Email sudah terdaftar. Silakan masuk menggunakan akun Anda.")

        user_id = str(uuid4())
        pw_hash = hash_password(password)
        created_at = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "INSERT INTO users (id, email, full_name, institution, role, password_hash, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (user_id, email, full_name, institution, role, pw_hash, created_at),
        )
        return {
            "id": user_id,
            "email": email,
            "full_name": full_name,
            "role": role,
            "institution": institution,
        }


def authenticate_user(db: Any, email: str, password: str) -> dict[str, str] | None:
    cleaned_email = email.strip()
    if not cleaned_email or not password:
        return None

    if cleaned_email.lower() == DEMO_EMAIL.lower() and db is not None:
        ensure_demo_user(db)

    if db is None:
        if cleaned_email.lower() == DEMO_EMAIL.lower() and password == DEMO_PASSWORD:
            return {
                "id": "demo-reviewer-id",
                "email": DEMO_EMAIL,
                "full_name": DEMO_NAME,
                "role": "reviewer",
                "institution": DEMO_INSTITUTION,
            }
        return None

    with db.connect() as conn:
        row = conn.execute(
            "SELECT id, email, full_name, role, institution, password_hash FROM users WHERE LOWER(email) = ?",
            (cleaned_email.lower(),),
        ).fetchone()
        if row is None:
            return None
        if not verify_password(password, str(row["password_hash"])):
            return None
        return {
            "id": str(row["id"]),
            "email": str(row["email"]),
            "full_name": str(row["full_name"]),
            "role": str(row["role"]),
            "institution": str(row["institution"]),
        }
