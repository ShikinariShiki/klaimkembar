BEGIN IMMEDIATE;
CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY);
CREATE TABLE IF NOT EXISTS datasets (
 id TEXT PRIMARY KEY, filename TEXT NOT NULL, size_bytes INTEGER NOT NULL CHECK(size_bytes > 0),
 created_at TEXT NOT NULL, claim_count INTEGER NOT NULL CHECK(claim_count > 0),
 validation TEXT NOT NULL, rules_json TEXT NOT NULL, rules_hash TEXT NOT NULL, labels_available INTEGER NOT NULL CHECK(labels_available IN (0,1))
);
CREATE TABLE IF NOT EXISTS claims (
 dataset_id TEXT NOT NULL REFERENCES datasets(id), claim_id TEXT NOT NULL,
 participant_token TEXT NOT NULL, facility_id TEXT NOT NULL, service_date TEXT NOT NULL,
 payload TEXT NOT NULL, PRIMARY KEY(dataset_id, claim_id)
);
CREATE INDEX IF NOT EXISTS claim_block ON claims(dataset_id,participant_token,facility_id,service_date);
CREATE TABLE IF NOT EXISTS cases (
 id TEXT PRIMARY KEY, dataset_id TEXT NOT NULL REFERENCES datasets(id),
 claim_a TEXT NOT NULL, claim_b TEXT NOT NULL, payload TEXT NOT NULL,
 protected INTEGER NOT NULL CHECK(protected IN (0,1)), risk_score REAL NOT NULL CHECK(risk_score BETWEEN 0 AND 100),
 review_status TEXT NOT NULL DEFAULT 'unreviewed' CHECK(review_status IN ('unreviewed','valid','needs_documents','further_review')),
 version INTEGER NOT NULL DEFAULT 0 CHECK(version >= 0),
 FOREIGN KEY(dataset_id,claim_a) REFERENCES claims(dataset_id,claim_id),
 FOREIGN KEY(dataset_id,claim_b) REFERENCES claims(dataset_id,claim_id),
 CHECK(claim_a < claim_b), UNIQUE(dataset_id,claim_a,claim_b)
);
CREATE INDEX IF NOT EXISTS queue_order ON cases(dataset_id,protected,review_status,risk_score DESC);
CREATE TABLE IF NOT EXISTS truth_pairs (
 dataset_id TEXT NOT NULL REFERENCES datasets(id), claim_a TEXT NOT NULL, claim_b TEXT NOT NULL,
 is_duplicate INTEGER NOT NULL CHECK(is_duplicate IN (0,1)),
 FOREIGN KEY(dataset_id,claim_a) REFERENCES claims(dataset_id,claim_id),
 FOREIGN KEY(dataset_id,claim_b) REFERENCES claims(dataset_id,claim_id),
 CHECK(claim_a < claim_b), PRIMARY KEY(dataset_id,claim_a,claim_b)
);
CREATE TABLE IF NOT EXISTS reviews (
 case_id TEXT NOT NULL REFERENCES cases(id), review_id TEXT NOT NULL,
 request_json TEXT NOT NULL, response_json TEXT NOT NULL, payload TEXT NOT NULL,
 version INTEGER NOT NULL CHECK(version > 0),
 PRIMARY KEY(case_id,review_id), UNIQUE(case_id,version)
);
CREATE TRIGGER IF NOT EXISTS immutable_review_update BEFORE UPDATE ON reviews BEGIN
 SELECT RAISE(ABORT,'review audit is append-only');
END;
CREATE TRIGGER IF NOT EXISTS immutable_review_delete BEFORE DELETE ON reviews BEGIN
 SELECT RAISE(ABORT,'review audit is append-only');
END;
INSERT OR IGNORE INTO schema_version(version) VALUES (1);
COMMIT;
