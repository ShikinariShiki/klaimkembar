ERD ini menunjukkan truth terpisah dari input detector dan review audit append-only.

```mermaid
erDiagram
  DATASET ||--o{ CLAIM : contains
  DATASET ||--o{ CASE : candidates
  DATASET ||--o{ TRUTH_PAIR : evaluation_only
  CLAIM ||--o{ CASE : claim_a
  CLAIM ||--o{ CASE : claim_b
  CASE ||--o{ REVIEW : audit
  DATASET {
    uuid id
    string rules_hash
    boolean labels_available
  }
  CLAIM {
    string claim_id
    string participant_token
    string facility_id
    date service_date
  }
  CASE {
    uuid id
    number risk_score
    boolean protected
    string review_status
    integer version
  }
  REVIEW {
    uuid review_id
    integer version
    string actor
    string rules_hash
    timestamp reviewed_at
  }
```

Diagram upload membedakan loading UI dari transaksi server yang sinkron.

```mermaid
sequenceDiagram
  participant FE
  participant API
  participant Validator
  participant Detector
  participant DB
  FE->>API: Multipart CSV + synthetic declaration + optional labels
  API->>Validator: Validate format/rows and separate truth
  alt Invalid upload
    Validator-->>API: Issues and counts
    API-->>FE: 422, no database writes
  else Valid upload
    API->>Detector: Claims only, never truth
    Detector-->>API: Explainable candidates and guardrails
    API->>DB: One transaction: dataset/claims/cases/truth tables
    DB-->>API: Commit
    API-->>FE: 201 ready + dataset_id
  end
```

State diagram review menunjukkan revision guard, bukan keputusan pembayaran.

```mermaid
stateDiagram-v2
  [*] --> unreviewed
  unreviewed --> valid: reviewer, expected_version
  unreviewed --> needs_documents: reviewer, expected_version
  unreviewed --> further_review: reviewer, expected_version
  valid --> needs_documents: revision, new review_id
  needs_documents --> further_review: revision, new review_id
  further_review --> valid: revision, new review_id
```

Semua pasangan status akhir boleh direvisi, bukan hanya tiga panah contoh. Setiap transisi menambah audit. Payload retry identik tidak menambah audit; stale version ditolak. Membuka detail bukan transisi state DB.
