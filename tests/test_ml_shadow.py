import json
import math
from pathlib import Path

import pytest

from klaimkembar.ml_shadow import (
    FEATURE_NAMES,
    CalibratedPairScorer,
    clear_scorer_cache,
    evaluate_pair_ml,
    extract_features,
    load_default_scorer,
    score_in_shadow,
)
from klaimkembar.models import Claim
from klaimkembar.settings import ROOT, Rules
from klaimkembar.synthetic import generate
from tests.test_api import api, assert_contract  # noqa: F401


class Scorer:
    version = 'test-only'

    def score(self, features: tuple[float, ...]) -> float:
        return 0.7


class BrokenScorer:
    version = 'test-only'

    def score(self, features: tuple[float, ...]) -> float:
        raise RuntimeError('sensitive detail')


def test_shadow_scaffold_is_opt_in_and_fails_closed() -> None:
    assert score_in_shadow((1.0,), None).status == 'not_available'
    assert score_in_shadow((math.nan,), Scorer()).status == 'fallback'
    assert score_in_shadow((1.0,), BrokenScorer()).status == 'fallback'
    result = score_in_shadow((1.0,), Scorer())
    assert result.status == 'shadow_scored'
    assert result.score == 0.7
    assert result.model_version == 'test-only'


def test_status_is_authenticated_and_truthful(api: tuple) -> None:  # noqa: F811
    client, reviewer, *_ = api
    path = '/api/v1/ml/status'
    response = client.get(path)
    assert response.status_code == 401
    assert_contract(response, 'get', path)
    response = client.get(path, headers=reviewer)
    assert response.status_code == 200
    assert_contract(response, 'get', path)
    assert response.json()['mode'] == 'shadow'
    assert response.json()['model_status'] == 'active'
    assert response.json()['shadow_enabled'] is True
    assert response.json()['bpjs2025_calibrated'] is True
    assert response.json()['model_version'] == 'kk-catboost-logreg-v1.0'
    assert len(response.json()['algorithms']) == 2


def test_feature_extraction_normalized_and_finite() -> None:
    rules = Rules.load(ROOT / 'rules.json')
    c1 = Claim(
        claim_id='C1',
        participant_token='P1',
        facility_id='F1',
        service_date='2026-05-10',
        submission_date='2026-05-12',
        diagnosis_group='M54.5',
        procedure_group='PHYSIO-SESSION',
        claim_amount='350000.00',
        claim_status='active',
        facility_group='FG1',
        episode_id='E1',
    )
    c2 = Claim(
        claim_id='C2',
        participant_token='P1',
        facility_id='F1',
        service_date='2026-05-10',
        submission_date='2026-05-13',
        diagnosis_group='M54.5',
        procedure_group='PHYSIO-SESSION',
        claim_amount='350000.00',
        claim_status='active',
        facility_group='FG1',
        episode_id='E1',
    )
    features = extract_features(c1, c2, rules)
    assert len(features) == len(FEATURE_NAMES)
    assert all(math.isfinite(x) for x in features)
    assert all(0.0 <= x <= 1.0 for x in features)

    # Identical participant, facility, date, amount
    feat_dict = dict(zip(FEATURE_NAMES, features))
    assert feat_dict['same_participant'] == 1.0
    assert feat_dict['same_facility'] == 1.0
    assert feat_dict['same_facility_group'] == 1.0
    assert feat_dict['exact_service_date'] == 1.0
    assert feat_dict['exact_amount'] == 1.0
    assert feat_dict['procedure_similarity'] == 1.0
    assert feat_dict['diagnosis_similarity'] == 1.0

    # Cross participant
    c3 = Claim(
        claim_id='C3',
        participant_token='P2',
        facility_id='F2',
        service_date='2026-05-20',
        submission_date='2026-05-25',
        diagnosis_group='',
        procedure_group='',
        claim_amount='100000.00',
        claim_status='active',
    )
    cross_feats = dict(zip(FEATURE_NAMES, extract_features(c1, c3, rules)))
    assert cross_feats['same_participant'] == 0.0
    assert cross_feats['same_facility'] == 0.0
    assert cross_feats['missing_clinical_info'] == 1.0
    assert cross_feats['exact_service_date'] == 0.0

    # Cancelled + corrected guardrail signal
    c_cancel = Claim(
        claim_id='C-OLD',
        participant_token='P1',
        facility_id='F1',
        service_date='2026-05-10',
        submission_date='2026-05-11',
        diagnosis_group='M54.5',
        procedure_group='PHYSIO',
        claim_amount='200000.00',
        claim_status='cancelled',
    )
    c_correct = Claim(
        claim_id='C-NEW',
        participant_token='P1',
        facility_id='F1',
        service_date='2026-05-10',
        submission_date='2026-05-12',
        diagnosis_group='M54.5',
        procedure_group='PHYSIO',
        claim_amount='200000.00',
        claim_status='corrected',
        original_claim_id='C-OLD',
    )
    corr_feats = dict(zip(FEATURE_NAMES, extract_features(c_cancel, c_correct, rules)))
    assert corr_feats['guardrail_correction_signal'] == 1.0

    # Scheduled service guardrail signal
    c_sched1 = Claim(
        claim_id='C-S1',
        participant_token='P1',
        facility_id='F1',
        service_date='2026-05-10',
        submission_date='2026-05-12',
        diagnosis_group='M54.5',
        procedure_group='PHYSIO',
        claim_amount='200000.00',
        claim_status='active',
        scheduled_service=True,
        scheduled_date='2026-05-10',
    )
    c_sched2 = Claim(
        claim_id='C-S2',
        participant_token='P1',
        facility_id='F1',
        service_date='2026-05-17',
        submission_date='2026-05-18',
        diagnosis_group='M54.5',
        procedure_group='PHYSIO',
        claim_amount='200000.00',
        claim_status='active',
        scheduled_service=True,
        scheduled_date='2026-05-17',
    )
    sched_feats = dict(zip(FEATURE_NAMES, extract_features(c_sched1, c_sched2, rules)))
    assert sched_feats['guardrail_schedule_or_visit_signal'] == 1.0


def test_calibrated_scorer_inference_and_explainability() -> None:
    clear_scorer_cache()
    scorer = load_default_scorer()
    assert isinstance(scorer, CalibratedPairScorer)
    assert scorer.version == 'kk-catboost-logreg-v1.0'

    # High match vector (duplicate signals active, guardrails inactive)
    high_features = (1.0, 1.0, 0.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 0.0, 0.0, 0.0, 0.0)
    score_high = scorer.score(high_features)
    assert 0.85 <= score_high <= 1.0
    assert 0.85 <= scorer.score_catboost(high_features) <= 1.0
    assert 0.85 <= scorer.score_logreg(high_features) <= 1.0

    factors = scorer.explain(high_features, top_k=3)
    assert isinstance(factors, tuple)
    assert 1 <= len(factors) <= 3
    assert any('EXACT' in f or 'SAME' in f or 'PROCEDURE' in f for f in factors)

    # Guardrail suppressed vector (recurring legitimate visit)
    guardrail_features = (1.0, 1.0, 0.0, 0.5, 0.0, 0.5, 1.0, 1.0, 1.0, 1.0, 0.0, 0.0, 0.0, 1.0)
    score_suppressed = scorer.score(guardrail_features)
    assert score_suppressed < 0.20

    # Explain empty or invalid
    assert scorer.explain((1.0,)) == ()
    with pytest.raises(ValueError, match='Expected'):
        scorer.score((1.0,))
    with pytest.raises(ValueError, match='finite'):
        scorer.score((math.nan,) * len(FEATURE_NAMES))


def test_checksum_verification_and_tamper_detection(tmp_path: Path) -> None:
    model_path = Path(__file__).resolve().parent.parent / 'klaimkembar/ml_model.json'
    data = json.loads(model_path.read_text(encoding='utf-8'))

    # Verifies cleanly with valid data
    scorer = CalibratedPairScorer.from_dict(data)
    assert scorer.version == data['model_version']

    # Tampering with weights fails checksum
    tampered_data = dict(data)
    tampered_data['weights'] = dict(data['weights'])
    tampered_data['weights']['same_participant'] = 999.0
    with pytest.raises(ValueError, match='checksum verification failed'):
        CalibratedPairScorer.from_dict(tampered_data)

    # Missing checksum fails
    no_checksum = dict(data)
    del no_checksum['checksum']
    with pytest.raises(ValueError, match='missing a valid checksum'):
        CalibratedPairScorer.from_dict(no_checksum)


def test_load_default_scorer_caching_and_error_handling(tmp_path: Path) -> None:
    clear_scorer_cache()
    scorer1 = load_default_scorer()
    scorer2 = load_default_scorer()
    assert scorer1 is scorer2

    clear_scorer_cache()
    non_existent = tmp_path / 'missing_model.json'
    with pytest.raises(FileNotFoundError):
        load_default_scorer(non_existent)


def test_evaluate_pair_ml_hybrid_scoring_and_guardrails() -> None:
    rules = Rules.load(ROOT / 'rules.json')
    c1 = Claim(
        claim_id='C1',
        participant_token='P1',
        facility_id='F1',
        service_date='2026-05-10',
        submission_date='2026-05-12',
        diagnosis_group='M54.5',
        procedure_group='PHYSIO-SESSION',
        claim_amount='350000.00',
        claim_status='active',
    )
    c2 = Claim(
        claim_id='C2',
        participant_token='P1',
        facility_id='F1',
        service_date='2026-05-10',
        submission_date='2026-05-12',
        diagnosis_group='M54.5',
        procedure_group='PHYSIO-SESSION',
        claim_amount='350000.00',
        claim_status='active',
    )

    # Active duplicate pair without guardrails
    rule_score = 90.0
    res = evaluate_pair_ml(c1, c2, rules, rule_score=rule_score, protected=False)
    assert res.status == 'shadow_scored'
    assert res.score is not None and res.score > 0.8
    assert res.hybrid_score is not None
    expected_hybrid = round(0.6 * rule_score + 0.4 * (res.score * 100.0), 4)
    assert res.hybrid_score == expected_hybrid
    assert len(res.top_factors) > 0

    # Protected pair: hybrid score must strictly be 0.0
    res_protected = evaluate_pair_ml(c1, c2, rules, rule_score=rule_score, protected=True)
    assert res_protected.status == 'shadow_scored'
    assert res_protected.hybrid_score == 0.0

    # Broken scorer fallback
    res_broken = evaluate_pair_ml(c1, c2, rules, rule_score=rule_score, protected=False, scorer=BrokenScorer())
    assert res_broken.status == 'fallback'
    assert res_broken.hybrid_score == rule_score


def test_trained_model_holdout_performance() -> None:
    model_path = Path(__file__).resolve().parent.parent / 'klaimkembar/ml_model.json'
    data = json.loads(model_path.read_text(encoding='utf-8'))
    metrics_info = data['validation_metrics']

    assert metrics_info['pr_auc'] >= 0.95
    assert metrics_info['f1'] >= 0.95
    assert metrics_info['precision'] >= 0.95
    assert metrics_info['recall'] >= 0.95
    assert metrics_info['false_positive_pairs_per_1000_claims'] <= 5.0

    # Real inference on holdout seed 503
    rules = Rules.load(ROOT / 'rules.json')
    scorer = load_default_scorer()
    claims, truth = generate(503, count=500)
    by_id = {c.claim_id: c for c in claims}

    pos_scores: list[float] = []
    neg_scores: list[float] = []

    for t in truth:
        left = by_id[t.claim_a]
        right = by_id[t.claim_b]
        feats = extract_features(left, right, rules)
        score = scorer.score(feats)
        if t.is_duplicate:
            pos_scores.append(score)
        else:
            neg_scores.append(score)

    assert len(pos_scores) > 0
    assert len(neg_scores) > 0
    # True duplicates should on average score significantly higher than non-duplicates
    assert (sum(pos_scores) / len(pos_scores)) > 0.80
    assert (sum(neg_scores) / len(neg_scores)) < 0.20


def test_train_and_calibrate_model_end_to_end(tmp_path: Path) -> None:
    from klaimkembar.ml_shadow import train_and_calibrate_model
    out_file = tmp_path / 'test_ml_model.json'
    artifact = train_and_calibrate_model(
        seeds=(104, 211),
        holdout_seeds=(211,),
        claim_count=60,
        epochs=5,
        output_path=out_file,
    )
    assert out_file.exists()
    assert artifact['model_version'] == 'kk-catboost-logreg-v1.0'
    assert 'catboost_trees' in artifact and len(artifact['catboost_trees']) == 12
    scorer = load_default_scorer(out_file)
    assert scorer.version == 'kk-catboost-logreg-v1.0'
    clear_scorer_cache()
