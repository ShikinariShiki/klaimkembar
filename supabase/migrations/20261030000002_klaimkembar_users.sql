-- Migration 002: Add users table for authentication in klaimkembar
BEGIN;
CREATE TABLE IF NOT EXISTS klaimkembar.users (
 id TEXT PRIMARY KEY,
 email TEXT NOT NULL UNIQUE,
 full_name TEXT NOT NULL,
 institution TEXT NOT NULL DEFAULT 'BPJS Kesehatan — Unit Telaah Klaim',
 role TEXT NOT NULL DEFAULT 'reviewer' CHECK(role IN ('reviewer','auditor')),
 password_hash TEXT NOT NULL,
 created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS users_email_idx ON klaimkembar.users(email);
REVOKE ALL ON klaimkembar.users FROM PUBLIC;
REVOKE ALL ON klaimkembar.users FROM anon, authenticated;
ALTER TABLE klaimkembar.users ENABLE ROW LEVEL SECURITY;
COMMIT;
