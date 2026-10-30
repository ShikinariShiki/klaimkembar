from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Decision = Literal['valid', 'needs_documents', 'further_review']
ReviewStatus = Literal['unreviewed', 'valid', 'needs_documents', 'further_review']
Priority = Literal['high', 'medium', 'low']


class Record(BaseModel):
    model_config = ConfigDict(extra='forbid')


class Claim(Record):
    claim_id: str
    participant_token: str
    facility_id: str
    service_date: str
    submission_date: str
    diagnosis_group: str
    procedure_group: str
    claim_amount: str
    claim_status: Literal['active', 'cancelled', 'corrected']
    original_claim_id: str = ''
    facility_group: str = ''
    episode_id: str = ''
    visit_id: str = ''
    scheduled_service: bool = False
    scheduled_date: str = ''


class FieldIssue(Record):
    row: int | None = None
    field: str
    code: str
    message: str


class ValidationSummary(Record):
    total_rows: int
    valid_rows: int
    invalid_rows: int
    incomplete_rows: int
    missing_columns: list[str]
    issues: list[FieldIssue]
    issues_total: int


class ErrorBody(Record):
    code: str
    message: str
    details: list[FieldIssue]
    request_id: str
    validation: ValidationSummary | None = None


class ErrorEnvelope(Record):
    error: ErrorBody


class UploadResponse(Record):
    dataset_id: str
    filename: str
    size_bytes: int
    status: Literal['ready']
    created_at: str
    validation: ValidationSummary
    case_count: int
    protected_pair_count: int
    rules_version: str
    rules_hash: str
    simulation: bool


class Contribution(Record):
    code: str
    points: float
    maximum: float


class Reducer(Record):
    code: str
    points: float
    evidence: str


class PairAssessment(Record):
    claim_a: str
    claim_b: str
    episode_group: str
    baseline_match: bool
    raw_score: float
    risk_score: float
    risk_level: Priority
    triggered_reasons: list[str]
    contributions: list[Contribution]
    risk_reducers: list[Reducer]
    missing_information: list[str]
    protected: bool
    needs_data: bool
    ml_status: Literal['shadow_scored', 'fallback', 'not_available'] = 'not_available'
    ml_score: float | None = None
    ml_catboost_score: float | None = None
    ml_logreg_score: float | None = None
    ml_hybrid_score: float | None = None
    ml_model_version: str | None = None
    ml_top_factors: list[str] = Field(default_factory=list)


class CaseSummary(Record):
    case_id: str
    dataset_id: str
    claim_a: Claim
    claim_b: Claim
    assessment: PairAssessment
    review_status: ReviewStatus
    version: int


class QueueSummary(Record):
    total_cases: int
    reviewed_cases: int
    remaining_cases: int
    next_case_id: str | None


class CasesResponse(Record):
    items: list[CaseSummary]
    total: int
    page: int
    page_size: int
    queue: QueueSummary


class ComparedField(Record):
    field: str
    claim_a: str
    claim_b: str
    state: Literal['same', 'different', 'missing']


class TimelineEvent(Record):
    date: str
    event: str
    claim_id: str


class ReviewRecord(Record):
    review_id: str
    actor: str
    decision: Decision
    note: str
    reviewed_at: str
    elapsed_seconds: float | None
    rules_version: str
    rules_hash: str
    version: int


class CaseDetail(CaseSummary):
    fields: list[ComparedField]
    timeline: list[TimelineEvent]
    reviews: list[ReviewRecord]
    queue: QueueSummary
    advisory: str


class ReviewRequest(Record):
    review_id: str = Field(pattern=r'^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$')
    expected_version: int = Field(ge=0, strict=True)
    decision: Decision
    note: str = Field(default='', max_length=2000)
    elapsed_seconds: float | None = Field(default=None, ge=0, le=3600, allow_inf_nan=False)


class ReviewResponse(Record):
    case_id: str
    review_status: ReviewStatus
    version: int
    review: ReviewRecord
    queue: QueueSummary


class TruthPair(Record):
    claim_a: str
    claim_b: str
    is_duplicate: bool


class MethodMetrics(Record):
    detected_pairs: int
    true_positives: int
    false_positives: int
    false_negatives: int
    precision: float | None
    recall: float | None
    f1: float | None
    pr_auc: float | None
    false_positive_pairs_per_1000_claims: float
    recall_at_top_10_percent: float | None


class MetricRange(Record):
    mean: float | None
    minimum: float | None
    maximum: float | None


class SeedReport(Record):
    seed: int
    claim_count: int
    eligible_pair_count: int
    positive_pairs: int
    prevalence: float
    methods: dict[str, MethodMetrics]
    failure_examples: dict[str, list[TruthPair]]
    missing_information_count: int


class BenchmarkReport(Record):
    simulation: bool
    rules_version: str
    rules_hash: str
    generated_at: str
    seeds: list[SeedReport]
    aggregates: dict[str, dict[str, MetricRange]]
    limitations: list[str]


class EvaluationResponse(Record):
    dataset_id: str
    simulation: bool
    label_status: Literal['available', 'not_provided']
    dataset_methods: dict[str, MethodMetrics] | None
    benchmark: BenchmarkReport | None
    queue: QueueSummary
    median_review_seconds: float | None
    review_time_source: str
    rules_version: str
    rules_hash: str
    metric_definitions: dict[str, str]


class HealthResponse(Record):
    status: Literal['ok']
    database: Literal['sqlite', 'postgres']
    rules_version: str


class FacetsResponse(Record):
    facilities: list[str]
    reasons: list[str]

class MLStatusResponse(Record):
    mode: Literal['rules_only', 'shadow'] = 'shadow'
    model_status: Literal['active', 'fallback', 'not_available'] = 'active'
    model_version: str | None = None
    algorithms: list[str] = Field(default_factory=list)
    shadow_enabled: bool = True
    bpjs2025_calibrated: bool = True
    validation_metrics: dict[str, float] = Field(default_factory=dict)
    message: str = 'Penilai ML (CatBoost & Logistic Regression) aktif dalam mode shadow dan terkalibrasi distribusi BPJS 2025.'
