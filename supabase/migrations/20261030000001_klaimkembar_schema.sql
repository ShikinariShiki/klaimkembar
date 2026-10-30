-- PostgreSQL schema for klaimkembar
BEGIN;
CREATE SCHEMA IF NOT EXISTS klaimkembar;
REVOKE ALL ON SCHEMA klaimkembar FROM PUBLIC;
CREATE TABLE IF NOT EXISTS klaimkembar.schema_version (version INTEGER PRIMARY KEY);
CREATE TABLE IF NOT EXISTS klaimkembar.datasets (
 id TEXT PRIMARY KEY, filename TEXT NOT NULL, size_bytes INTEGER NOT NULL CHECK(size_bytes > 0),
 created_at TEXT NOT NULL, claim_count INTEGER NOT NULL CHECK(claim_count > 0),
 validation TEXT NOT NULL, rules_json TEXT NOT NULL, rules_hash TEXT NOT NULL,
 labels_available INTEGER NOT NULL CHECK(labels_available IN (0,1))
);
CREATE TABLE IF NOT EXISTS klaimkembar.claims (
 dataset_id TEXT NOT NULL REFERENCES klaimkembar.datasets(id), claim_id TEXT NOT NULL,
 participant_token TEXT NOT NULL, facility_id TEXT NOT NULL, service_date TEXT NOT NULL,
 payload TEXT NOT NULL, PRIMARY KEY(dataset_id, claim_id)
);
CREATE INDEX IF NOT EXISTS claim_block ON klaimkembar.claims(dataset_id,participant_token,facility_id,service_date);
CREATE INDEX IF NOT EXISTS claims_dataset_facility_idx ON klaimkembar.claims(dataset_id, facility_id);
CREATE TABLE IF NOT EXISTS klaimkembar.cases (
 id TEXT PRIMARY KEY, dataset_id TEXT NOT NULL REFERENCES klaimkembar.datasets(id),
 claim_a TEXT NOT NULL, claim_b TEXT NOT NULL, payload TEXT NOT NULL,
 protected INTEGER NOT NULL CHECK(protected IN (0,1)), risk_score DOUBLE PRECISION NOT NULL CHECK(risk_score BETWEEN 0 AND 100),
 review_status TEXT NOT NULL DEFAULT 'unreviewed' CHECK(review_status IN ('unreviewed','valid','needs_documents','further_review')),
 version INTEGER NOT NULL DEFAULT 0 CHECK(version >= 0),
 FOREIGN KEY(dataset_id,claim_a) REFERENCES klaimkembar.claims(dataset_id,claim_id),
 FOREIGN KEY(dataset_id,claim_b) REFERENCES klaimkembar.claims(dataset_id,claim_id),
 CHECK(claim_a < claim_b), UNIQUE(dataset_id,claim_a,claim_b)
);
CREATE INDEX IF NOT EXISTS queue_order ON klaimkembar.cases(dataset_id,protected,review_status,risk_score DESC);
CREATE INDEX IF NOT EXISTS cases_payload_gin ON klaimkembar.cases USING gin ((payload::jsonb));
CREATE INDEX IF NOT EXISTS cases_risk_level_idx ON klaimkembar.cases(dataset_id, (payload::jsonb->>'risk_level'));
CREATE INDEX IF NOT EXISTS cases_ml_score_idx ON klaimkembar.cases(dataset_id, (COALESCE((payload::jsonb->>'ml_score')::double precision, 0.0)) DESC);
CREATE TABLE IF NOT EXISTS klaimkembar.truth_pairs (
 dataset_id TEXT NOT NULL REFERENCES klaimkembar.datasets(id), claim_a TEXT NOT NULL, claim_b TEXT NOT NULL,
 is_duplicate INTEGER NOT NULL CHECK(is_duplicate IN (0,1)),
 FOREIGN KEY(dataset_id,claim_a) REFERENCES klaimkembar.claims(dataset_id,claim_id),
 FOREIGN KEY(dataset_id,claim_b) REFERENCES klaimkembar.claims(dataset_id,claim_id),
 CHECK(claim_a < claim_b), PRIMARY KEY(dataset_id,claim_a,claim_b)
);
CREATE TABLE IF NOT EXISTS klaimkembar.reviews (
 case_id TEXT NOT NULL REFERENCES klaimkembar.cases(id), review_id TEXT NOT NULL,
 request_json TEXT NOT NULL, response_json TEXT NOT NULL, payload TEXT NOT NULL,
 version INTEGER NOT NULL CHECK(version > 0), PRIMARY KEY(case_id,review_id), UNIQUE(case_id,version)
);
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
CREATE OR REPLACE FUNCTION klaimkembar.reject_review_change() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 RAISE EXCEPTION 'review audit is append-only';
END;
$$;
DROP TRIGGER IF EXISTS immutable_review_update ON klaimkembar.reviews;
CREATE TRIGGER immutable_review_update BEFORE UPDATE OR DELETE ON klaimkembar.reviews
 FOR EACH ROW EXECUTE FUNCTION klaimkembar.reject_review_change();
REVOKE ALL ON ALL TABLES IN SCHEMA klaimkembar FROM PUBLIC;
REVOKE ALL ON SCHEMA klaimkembar FROM anon, authenticated;
REVOKE ALL ON ALL TABLES IN SCHEMA klaimkembar FROM anon, authenticated;
ALTER TABLE klaimkembar.schema_version ENABLE ROW LEVEL SECURITY;
ALTER TABLE klaimkembar.datasets ENABLE ROW LEVEL SECURITY;
ALTER TABLE klaimkembar.claims ENABLE ROW LEVEL SECURITY;
ALTER TABLE klaimkembar.cases ENABLE ROW LEVEL SECURITY;
ALTER TABLE klaimkembar.truth_pairs ENABLE ROW LEVEL SECURITY;
ALTER TABLE klaimkembar.reviews ENABLE ROW LEVEL SECURITY;
ALTER TABLE klaimkembar.users ENABLE ROW LEVEL SECURITY;
INSERT INTO klaimkembar.schema_version(version) VALUES (1) ON CONFLICT DO NOTHING;
COMMIT;
