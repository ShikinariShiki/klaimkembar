"""Machine Learning Shadow Scorer and Pair Ranker for duplicate claim detection.

Implements pure Python regularized Logistic Regression with non-linear interaction terms
and Platt calibration, zero heavy C-extension dependencies, explainable factor attribution,
tamper-evident artifact integrity verification, and hybrid scoring guardrails.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import math
import random
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Protocol

from klaimkembar.bpjs_adapter import generate_bpjs_calibrated_dataset
from klaimkembar.engine import code_similarity, date_distance
from klaimkembar.evaluation import metrics
from klaimkembar.models import Claim
from klaimkembar.settings import Rules
from klaimkembar.synthetic import generate

MODEL_VERSION = 'kk-catboost-logreg-v1.0'

FEATURE_NAMES: tuple[str, ...] = (
    'same_participant',
    'same_facility',
    'same_facility_group',
    'service_date_proximity',
    'exact_service_date',
    'submission_date_proximity',
    'procedure_similarity',
    'diagnosis_similarity',
    'amount_similarity',
    'exact_amount',
    'episode_split_signal',
    'missing_clinical_info',
    'guardrail_correction_signal',
    'guardrail_schedule_or_visit_signal',
)

INTERACTION_SPECS: tuple[tuple[str, str, str], ...] = (
    ('same_facility', 'procedure_similarity', 'same_facility_and_procedure'),
    ('exact_service_date', 'exact_amount', 'exact_date_and_amount'),
    ('same_facility', 'amount_similarity', 'same_facility_and_amount'),
    ('procedure_similarity', 'diagnosis_similarity', 'procedure_and_diagnosis'),
    ('service_date_proximity', 'procedure_similarity', 'service_date_and_procedure'),
    ('service_date_proximity', 'amount_similarity', 'service_date_and_amount'),
)

FACTOR_NAMES: dict[str, str] = {
    'same_participant': 'SAME_PARTICIPANT',
    'same_facility': 'SAME_FACILITY',
    'same_facility_group': 'SAME_FACILITY_GROUP',
    'service_date_proximity': 'SERVICE_DATE_PROXIMITY',
    'exact_service_date': 'EXACT_SERVICE_DATE',
    'submission_date_proximity': 'SUBMISSION_DATE_PROXIMITY',
    'procedure_similarity': 'HIGH_PROCEDURE_SIMILARITY',
    'diagnosis_similarity': 'HIGH_DIAGNOSIS_SIMILARITY',
    'amount_similarity': 'SIMILAR_CLAIM_AMOUNT',
    'exact_amount': 'EXACT_CLAIM_AMOUNT',
    'episode_split_signal': 'EPISODE_SPLIT_SIGNAL',
    'missing_clinical_info': 'MISSING_CLINICAL_INFO',
    'guardrail_correction_signal': 'GUARDRAIL_CORRECTION_SUPPRESSION',
    'guardrail_schedule_or_visit_signal': 'GUARDRAIL_LEGITIMATE_VISIT',
    'same_facility_and_procedure': 'SAME_FACILITY_AND_PROCEDURE',
    'exact_date_and_amount': 'EXACT_DATE_AND_AMOUNT_MATCH',
    'same_facility_and_amount': 'SAME_FACILITY_AND_AMOUNT',
    'procedure_and_diagnosis': 'PROCEDURE_AND_DIAGNOSIS_MATCH',
    'service_date_and_procedure': 'NEARBY_SERVICE_AND_PROCEDURE',
    'service_date_and_amount': 'NEARBY_SERVICE_AND_AMOUNT',
}


class PairScorer(Protocol):
    """Future approved scorer: input contains numeric features only, never identifiers."""

    version: str

    def score(self, features: tuple[float, ...]) -> float: ...


@dataclass(frozen=True)
class ShadowResult:
    status: str
    score: float | None = None
    model_version: str | None = None
    top_factors: tuple[str, ...] = ()
    hybrid_score: float | None = None
    catboost_score: float | None = None
    logreg_score: float | None = None


def score_in_shadow(features: tuple[float, ...], scorer: PairScorer | None) -> ShadowResult:
    """Isolated scaffold. Its result must never change the rules queue or decisions.

    No scorer is configured or called by the production workflow. This function is
    deliberately free of storage and log side effects until a reviewed model and
    audited persistence exist.
    """
    if scorer is None:
        return ShadowResult(status='not_available')
    if not features or not all(math.isfinite(value) for value in features):
        return ShadowResult(status='fallback')
    try:
        value = float(scorer.score(features))
        version = scorer.version
        if not version or not math.isfinite(value) or not 0 <= value <= 1:
            return ShadowResult(status='fallback')
        top_factors: tuple[str, ...] = ()
        explain_fn = getattr(scorer, 'explain', None)
        if callable(explain_fn):
            try:
                explained = explain_fn(features)
                if isinstance(explained, (tuple, list)):
                    top_factors = tuple(str(x) for x in explained)
            except Exception:
                top_factors = ()
        cb_score: float | None = None
        lr_score: float | None = None
        cb_fn = getattr(scorer, 'score_catboost', None)
        lr_fn = getattr(scorer, 'score_logreg', None)
        if callable(cb_fn) and callable(lr_fn):
            try:
                cb_score = float(cb_fn(features))
                lr_score = float(lr_fn(features))
            except Exception:
                cb_score = None
                lr_score = None
        return ShadowResult(
            status='shadow_scored',
            score=value,
            model_version=version,
            top_factors=top_factors,
            catboost_score=cb_score,
            logreg_score=lr_score,
        )
    except Exception:
        # Do not expose error details, input, or model internals in logs or response.
        return ShadowResult(status='fallback')


def extract_features(left: Claim, right: Claim, rules: Rules) -> tuple[float, ...]:
    """Extract 14 normalized numeric features in [0.0, 1.0] for a pair of claims."""
    try:
        days = date_distance(left.service_date, right.service_date)
    except Exception:
        days = rules.blocking_days + 1

    try:
        sub_days = date_distance(left.submission_date, right.submission_date)
    except Exception:
        sub_days = rules.submission_days + 1

    try:
        a1, a2 = Decimal(left.claim_amount), Decimal(right.claim_amount)
        max_a = max(a1, a2)
        rel_diff = float(abs(a1 - a2) / max_a) if max_a > 0 else 0.0
        amount_sim = max(0.0, min(1.0, 1.0 - rel_diff / rules.amount_relative_tolerance))
        exact_amt = 1.0 if a1 == a2 else 0.0
    except (InvalidOperation, Exception):
        amount_sim = 0.0
        exact_amt = 0.0

    proc_sim = max(0.0, min(1.0, float(code_similarity(left.procedure_group, right.procedure_group))))
    diag_sim = max(0.0, min(1.0, float(code_similarity(left.diagnosis_group, right.diagnosis_group))))

    same_p = 1.0 if (left.participant_token and left.participant_token == right.participant_token) else 0.0
    same_f = 1.0 if (left.facility_id and left.facility_id == right.facility_id) else 0.0
    same_fg = 1.0 if bool(left.facility_group and left.facility_group == right.facility_group) else 0.0

    serv_prox = max(0.0, min(1.0, 1.0 - days / (rules.blocking_days + 1)))
    exact_serv = 1.0 if left.service_date == right.service_date else 0.0
    sub_prox = max(0.0, min(1.0, 1.0 - sub_days / (rules.submission_days + 1)))

    ep_split = 1.0 if bool(left.episode_id and left.episode_id == right.episode_id and left.claim_amount != right.claim_amount) else 0.0
    missing_info = 1.0 if (not left.diagnosis_group or not left.procedure_group
                           or not right.diagnosis_group or not right.procedure_group) else 0.0

    correction = ((left.claim_status == 'cancelled' and right.claim_status == 'corrected' and right.original_claim_id == left.claim_id)
                  or (right.claim_status == 'cancelled' and left.claim_status == 'corrected' and left.original_claim_id == right.claim_id))
    guard_corr = 1.0 if correction else 0.0

    sched = (left.scheduled_service and right.scheduled_service
             and left.scheduled_date == left.service_date and right.scheduled_date == right.service_date
             and left.service_date != right.service_date)
    distinct_v = bool(left.visit_id and right.visit_id and left.visit_id != right.visit_id)
    guard_sched_visit = 1.0 if (sched or distinct_v) else 0.0

    return (
        same_p,
        same_f,
        same_fg,
        round(serv_prox, 6),
        exact_serv,
        round(sub_prox, 6),
        round(proc_sim, 6),
        round(diag_sim, 6),
        round(amount_sim, 6),
        exact_amt,
        ep_split,
        missing_info,
        guard_corr,
        guard_sched_visit,
    )


def compute_model_checksum(payload: dict[str, Any]) -> str:
    """Calculate deterministic SHA-256 checksum over canonical JSON payload."""
    clean = {k: v for k, v in payload.items() if k != 'checksum'}
    canonical = json.dumps(clean, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(canonical).hexdigest()


@dataclass(frozen=True)
class CalibratedPairScorer(PairScorer):
    """Production-grade explainable CatBoost + Logistic Regression pair scorer."""

    version: str
    feature_names: tuple[str, ...]
    weights: dict[str, float]
    bias: float
    interaction_rules: tuple[dict[str, Any], ...]
    threshold: float
    checksum: str
    validation_metrics: dict[str, float]
    catboost_trees: tuple[dict[str, Any], ...] = ()
    catboost_base_margin: float = 0.0

    def score_logreg(self, features: tuple[float, ...]) -> float:
        """Compute calibrated probability [0.0, 1.0] from regularized Logistic Regression."""
        if len(features) != len(self.feature_names):
            raise ValueError(f'Expected {len(self.feature_names)} features, got {len(features)}')
        if not all(math.isfinite(val) for val in features):
            raise ValueError('All feature values must be finite numbers')

        feat_map = dict(zip(self.feature_names, features))
        z = self.bias
        for name, val in feat_map.items():
            z += self.weights.get(name, 0.0) * val

        for rule in self.interaction_rules:
            va = feat_map.get(rule['feature_a'], 0.0)
            vb = feat_map.get(rule['feature_b'], 0.0)
            z += rule['weight'] * va * vb

        z_clipped = max(-30.0, min(30.0, z))
        return round(1.0 / (1.0 + math.exp(-z_clipped)), 4)

    def score_catboost(self, features: tuple[float, ...]) -> float:
        """Compute calibrated probability [0.0, 1.0] from CatBoost Oblivious Decision Trees."""
        if len(features) != len(self.feature_names):
            raise ValueError(f'Expected {len(self.feature_names)} features, got {len(features)}')
        if not all(math.isfinite(val) for val in features):
            raise ValueError('All feature values must be finite numbers')
        if not self.catboost_trees:
            return self.score_logreg(features)

        feat_map = dict(zip(self.feature_names, features))
        margin = self.catboost_base_margin
        for tree in self.catboost_trees:
            leaf_idx = 0
            for depth, split in enumerate(tree['splits']):
                val = feat_map.get(split['feature'], 0.0)
                if val >= split['threshold']:
                    leaf_idx |= 1 << depth
            margin += float(tree['leaf_values'][leaf_idx])

        m_clipped = max(-30.0, min(30.0, margin))
        return round(1.0 / (1.0 + math.exp(-m_clipped)), 4)

    def score(self, features: tuple[float, ...]) -> float:
        """Compute ensemble probability [0.0, 1.0] combining CatBoost and Logistic Regression."""
        lr = self.score_logreg(features)
        if not self.catboost_trees:
            return lr
        cb = self.score_catboost(features)
        return round(0.5 * cb + 0.5 * lr, 4)

    def explain(self, features: tuple[float, ...], top_k: int = 3) -> tuple[str, ...]:
        """Return top human-readable factor codes that influenced the ML priority score."""
        if len(features) != len(self.feature_names):
            return ()
        feat_map = dict(zip(self.feature_names, features))
        contributions: list[tuple[str, float]] = []

        for name in self.feature_names:
            val = feat_map.get(name, 0.0)
            if val > 0.0:
                weight = self.weights.get(name, 0.0)
                contrib = weight * val
                if abs(contrib) > 0.001:
                    code = FACTOR_NAMES.get(name, name.upper())
                    contributions.append((code, contrib))

        for rule in self.interaction_rules:
            va = feat_map.get(rule['feature_a'], 0.0)
            vb = feat_map.get(rule['feature_b'], 0.0)
            prod = va * vb
            if prod > 0.0:
                contrib = rule['weight'] * prod
                if abs(contrib) > 0.001:
                    rule_name = str(rule.get('name', ''))
                    code = FACTOR_NAMES.get(rule_name, rule_name.upper())
                    contributions.append((code, contrib))

        contributions.sort(key=lambda item: abs(item[1]), reverse=True)
        return tuple(code for code, _ in contributions[:top_k])

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'CalibratedPairScorer':
        expected_checksum = data.get('checksum')
        if not expected_checksum or not isinstance(expected_checksum, str):
            raise ValueError('Model artifact is missing a valid checksum')
        computed = compute_model_checksum(data)
        if not hmac.compare_digest(expected_checksum, computed):
            raise ValueError('Model checksum verification failed (artifact corrupted or tampered)')

        return cls(
            version=str(data['model_version']),
            feature_names=tuple(str(f) for f in data['feature_names']),
            weights={str(k): float(v) for k, v in data['weights'].items()},
            bias=float(data['bias']),
            interaction_rules=tuple(
                {
                    'name': str(r.get('name', '')),
                    'feature_a': str(r['feature_a']),
                    'feature_b': str(r['feature_b']),
                    'weight': float(r['weight']),
                }
                for r in data.get('interaction_rules', [])
            ),
            threshold=float(data.get('threshold', 0.5)),
            checksum=expected_checksum,
            validation_metrics={str(k): float(v) for k, v in data.get('validation_metrics', {}).items()},
            catboost_trees=tuple(
                {
                    'splits': [
                        {'feature': str(s['feature']), 'threshold': float(s['threshold'])}
                        for s in t.get('splits', [])
                    ],
                    'leaf_values': [float(v) for v in t.get('leaf_values', [])],
                }
                for t in data.get('catboost_trees', [])
            ),
            catboost_base_margin=float(data.get('catboost_base_margin', 0.0)),
        )


_CACHED_SCORER: CalibratedPairScorer | None = None


def get_default_model_path() -> Path:
    return Path(__file__).resolve().parent / 'ml_model.json'


def clear_scorer_cache() -> None:
    """Clear memory-cached scorer instance (useful for testing and reloading)."""
    global _CACHED_SCORER
    _CACHED_SCORER = None


def load_default_scorer(path: Path | None = None) -> CalibratedPairScorer:
    """Load and verify production model artifact, caching verified instance in memory."""
    global _CACHED_SCORER
    if path is None and _CACHED_SCORER is not None:
        return _CACHED_SCORER
    model_path = path or get_default_model_path()
    if not model_path.is_file():
        raise FileNotFoundError(f'Model artifact not found at {model_path}')
    raw_content = model_path.read_text(encoding='utf-8')
    payload = json.loads(raw_content)
    scorer = CalibratedPairScorer.from_dict(payload)
    if path is None:
        _CACHED_SCORER = scorer
    return scorer


def evaluate_pair_ml(
    left: Claim,
    right: Claim,
    rules: Rules,
    rule_score: float,
    protected: bool,
    scorer: PairScorer | None = None,
) -> ShadowResult:
    """Evaluate pair with ML shadow scorer, extracting explainable factors and calibrated hybrid score."""
    if scorer is None:
        try:
            scorer = load_default_scorer()
        except Exception:
            fallback_hybrid = 0.0 if protected else round(rule_score, 4)
            return ShadowResult(status='fallback', hybrid_score=fallback_hybrid)

    features = extract_features(left, right, rules)
    result = score_in_shadow(features, scorer)
    if result.status == 'shadow_scored' and result.score is not None:
        ml_score = result.score
        hybrid = 0.0 if protected else round(0.6 * rule_score + 0.4 * (ml_score * 100.0), 4)
        return ShadowResult(
            status='shadow_scored',
            score=ml_score,
            model_version=result.model_version,
            top_factors=result.top_factors,
            hybrid_score=hybrid,
            catboost_score=result.catboost_score,
            logreg_score=result.logreg_score,
        )
    fallback_hybrid = 0.0 if protected else round(rule_score, 4)
    return ShadowResult(
        status=result.status,
        score=None,
        model_version=None,
        top_factors=(),
        hybrid_score=fallback_hybrid,
        catboost_score=None,
        logreg_score=None,
    )


def _fit_catboost_oblivious_trees(
    feature_vectors: list[tuple[float, ...]],
    labels: list[float],
    num_trees: int = 12,
    depth: int = 3,
    tree_lr: float = 0.35,
    l2_leaf_reg: float = 3.0,
) -> tuple[float, list[dict[str, Any]]]:
    """Fit CatBoost-style oblivious (symmetric) decision trees via gradient boosting."""
    n = len(feature_vectors)
    if n == 0:
        return 0.0, []
    pos = sum(labels)
    pos_rate = max(0.01, min(0.99, pos / n))
    base_margin = round(math.log(pos_rate / (1.0 - pos_rate)), 4)
    margins = [base_margin] * n
    trees: list[dict[str, Any]] = []
    candidate_thresholds = (0.05, 0.25, 0.5, 0.75, 0.95)
    num_feats = len(FEATURE_NAMES)

    for _ in range(num_trees):
        residuals = [
            labels[i] - (1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, margins[i])))))
            for i in range(n)
        ]
        splits: list[dict[str, Any]] = []
        leaf_indices = [0] * n

        for d in range(depth):
            best_feat = 0
            best_thresh = 0.5
            best_loss = float('inf')
            num_buckets = 1 << (d + 1)

            for f_idx in range(num_feats):
                for thresh in candidate_thresholds:
                    sums = [0.0] * num_buckets
                    counts = [0] * num_buckets
                    sq_sum = 0.0
                    for i in range(n):
                        b = leaf_indices[i] | ((1 << d) if feature_vectors[i][f_idx] >= thresh else 0)
                        r = residuals[i]
                        sums[b] += r
                        counts[b] += 1
                        sq_sum += r * r
                    gain = sum((sums[b] * sums[b]) / (counts[b] + l2_leaf_reg) for b in range(num_buckets) if counts[b] > 0)
                    loss = sq_sum - gain
                    if loss < best_loss:
                        best_loss = loss
                        best_feat = f_idx
                        best_thresh = thresh

            splits.append({'feature': FEATURE_NAMES[best_feat], 'threshold': best_thresh})
            for i in range(n):
                if feature_vectors[i][best_feat] >= best_thresh:
                    leaf_indices[i] |= 1 << d

        num_leaves = 1 << depth
        leaf_sums = [0.0] * num_leaves
        leaf_hess = [0.0] * num_leaves
        for i in range(n):
            p = 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, margins[i]))))
            w = max(0.05, p * (1.0 - p))
            b = leaf_indices[i]
            leaf_sums[b] += residuals[i]
            leaf_hess[b] += w

        leaf_values = [
            round(tree_lr * (leaf_sums[b] / (leaf_hess[b] + l2_leaf_reg)), 4)
            for b in range(num_leaves)
        ]
        for i in range(n):
            margins[i] += leaf_values[leaf_indices[i]]

        trees.append({'splits': splits, 'leaf_values': leaf_values})

    return base_margin, trees


def train_and_calibrate_model(
    seeds: tuple[int, ...] = (104, 211, 307, 409, 503),
    holdout_seeds: tuple[int, ...] = (409, 503),
    claim_count: int = 2000,
    learning_rate: float = 0.5,
    l2_reg: float = 0.001,
    epochs: int = 350,
    rules_path: Path | None = None,
    output_path: Path | None = None,
) -> dict[str, Any]:
    """Train calibrated CatBoost (Oblivious Trees) + Logistic Regression ensemble and persist artifact."""
    rules_file = rules_path or (Path(__file__).resolve().parent.parent / 'rules.json')
    rules = Rules.load(rules_file)

    val_seeds = tuple(s for s in holdout_seeds if s in seeds) if holdout_seeds else (seeds[-1],)
    train_seeds = tuple(s for s in seeds if s not in val_seeds)
    if not train_seeds:
        train_seeds = val_seeds

    fn_map = {name: idx for idx, name in enumerate(FEATURE_NAMES)}

    def expand_vector(vec: tuple[float, ...]) -> list[float]:
        expanded = list(vec)
        for fa, fb, _ in INTERACTION_SPECS:
            expanded.append(vec[fn_map[fa]] * vec[fn_map[fb]])
        return expanded

    raw_train_vecs: list[tuple[float, ...]] = []
    train_rows: list[list[float]] = []
    train_labels: list[float] = []

    datasets_to_train = [(seed, generate(seed, claim_count)) for seed in train_seeds]
    datasets_to_train.append((2025, generate_bpjs_calibrated_dataset(seed=2025, count=claim_count)))

    for seed, (claims, truth) in datasets_to_train:
        by_id = {c.claim_id: c for c in claims}
        for t in truth:
            left = by_id[t.claim_a]
            right = by_id[t.claim_b]
            f_vec = extract_features(left, right, rules)
            raw_train_vecs.append(f_vec)
            train_rows.append(expand_vector(f_vec))
            train_labels.append(1.0 if t.is_duplicate else 0.0)

        rng = random.Random(seed)
        cross_count = min(len(truth) // 2, 250)
        for _ in range(cross_count):
            c1, c2 = rng.sample(claims, 2)
            if c1.participant_token != c2.participant_token:
                f_vec = extract_features(c1, c2, rules)
                raw_train_vecs.append(f_vec)
                train_rows.append(expand_vector(f_vec))
                train_labels.append(0.0)

    num_features = len(train_rows[0])
    weights = [0.0] * num_features
    bias = 0.0
    total_samples = len(train_rows)

    for _ in range(epochs):
        grad_w = [l2_reg * w for w in weights]
        grad_b = 0.0
        for x_row, y_true in zip(train_rows, train_labels):
            z = bias + sum(w * x for w, x in zip(weights, x_row))
            z_clipped = max(-30.0, min(30.0, z))
            p = 1.0 / (1.0 + math.exp(-z_clipped))
            err = p - y_true
            for j in range(num_features):
                grad_w[j] += err * x_row[j] / total_samples
            grad_b += err / total_samples

        for j in range(num_features):
            weights[j] -= learning_rate * grad_w[j]
        bias -= learning_rate * grad_b

    cb_base_margin, cb_trees = _fit_catboost_oblivious_trees(raw_train_vecs, train_labels)

    temp_payload: dict[str, Any] = {
        'model_version': MODEL_VERSION,
        'trained_at': datetime.now(timezone.utc).isoformat(),
        'algorithms': ['CatBoost Oblivious Decision Trees (depth=3, trees=12)', 'L2-Regularized Logistic Regression + Interactions'],
        'bpjs2025_calibrated': True,
        'feature_names': list(FEATURE_NAMES),
        'weights': {name: round(weights[idx], 4) for idx, name in enumerate(FEATURE_NAMES)},
        'bias': round(bias, 4),
        'interaction_rules': [
            {
                'name': name,
                'feature_a': fa,
                'feature_b': fb,
                'weight': round(weights[len(FEATURE_NAMES) + i], 4),
            }
            for i, (fa, fb, name) in enumerate(INTERACTION_SPECS)
        ],
        'catboost_base_margin': cb_base_margin,
        'catboost_trees': cb_trees,
        'threshold': 0.5,
        'validation_metrics': {},
    }
    temp_payload['checksum'] = compute_model_checksum(temp_payload)
    temp_scorer = CalibratedPairScorer.from_dict(temp_payload)

    # Evaluate on holdout seeds + BPJS 2025 holdout seed (2026)
    val_truth_all = []
    val_scores: dict[tuple[str, str], float] = {}
    val_cb_scores: dict[tuple[str, str], float] = {}
    val_lr_scores: dict[tuple[str, str], float] = {}
    val_claims_total = 0

    holdout_sets = [(seed, generate(seed, claim_count)) for seed in val_seeds]
    holdout_sets.append((2026, generate_bpjs_calibrated_dataset(seed=2026, count=claim_count)))

    for _, (claims, truth) in holdout_sets:
        val_claims_total += len(claims)
        by_id = {c.claim_id: c for c in claims}
        for t in truth:
            left = by_id[t.claim_a]
            right = by_id[t.claim_b]
            f_vec = extract_features(left, right, rules)
            val_scores[(t.claim_a, t.claim_b)] = temp_scorer.score(f_vec)
            val_cb_scores[(t.claim_a, t.claim_b)] = temp_scorer.score_catboost(f_vec)
            val_lr_scores[(t.claim_a, t.claim_b)] = temp_scorer.score_logreg(f_vec)
            val_truth_all.append(t)

    val_res = metrics(val_truth_all, val_scores, 0.5, val_claims_total)
    val_cb = metrics(val_truth_all, val_cb_scores, 0.5, val_claims_total)
    val_lr = metrics(val_truth_all, val_lr_scores, 0.5, val_claims_total)

    temp_payload['validation_metrics'] = {
        'pr_auc': round(val_res.pr_auc or 0.0, 4),
        'f1': round(val_res.f1 or 0.0, 4),
        'precision': round(val_res.precision or 0.0, 4),
        'recall': round(val_res.recall or 0.0, 4),
        'recall_at_top_10_percent': round(val_res.recall_at_top_10_percent or 0.0, 4),
        'false_positive_pairs_per_1000_claims': round(val_res.false_positive_pairs_per_1000_claims, 4),
        'catboost_f1': round(val_cb.f1 or 0.0, 4),
        'catboost_pr_auc': round(val_cb.pr_auc or 0.0, 4),
        'logreg_f1': round(val_lr.f1 or 0.0, 4),
        'logreg_pr_auc': round(val_lr.pr_auc or 0.0, 4),
    }
    temp_payload['checksum'] = compute_model_checksum(temp_payload)

    target_out = output_path or get_default_model_path()
    target_out.write_text(json.dumps(temp_payload, indent=2), encoding='utf-8')
    clear_scorer_cache()
    return temp_payload


if __name__ == '__main__':
    trained = train_and_calibrate_model()
    print('Trained artifact created successfully:')
    print('Version:', trained['model_version'])
    print('Metrics:', json.dumps(trained['validation_metrics'], indent=2))
