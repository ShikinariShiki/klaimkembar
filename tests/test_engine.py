from dataclasses import replace

from klaimkembar.engine import assess, detect
from klaimkembar.models import Claim
from klaimkembar.settings import ROOT, Rules

RULES = Rules.load(ROOT / 'rules.json')


def claim(identity='SYN-C-A', **changes):
    fields = dict(claim_id=identity, participant_token='SYN-P-A', facility_id='SYN-F-A',
                  service_date='2026-05-10', submission_date='2026-05-12', diagnosis_group='M54',
                  procedure_group='PHYSIO', claim_amount='350000.00', claim_status='active')
    fields.update(changes)
    return Claim(**fields)


def test_exact_pair_has_explainable_hundred_point_score():
    pair = assess(claim(), claim('SYN-C-B'), RULES, 'group')
    assert pair.baseline_match
    assert pair.risk_score == 100
    assert sum(factor.points for factor in pair.contributions) == pair.raw_score
    assert pair.risk_level == 'high'


def test_changed_date_and_amount_is_near_duplicate_not_exact():
    pair = assess(claim(), claim('SYN-C-B', service_date='2026-05-11', claim_amount='355000.00'), RULES, 'group')
    assert not pair.baseline_match
    assert pair.risk_score >= RULES.queue_threshold
    assert 'SERVICE_DATE_NEAR' in pair.triggered_reasons


def test_candidate_blocks_by_participant_facility_date_and_procedure():
    assert not detect([claim(), claim('SYN-C-B', participant_token='SYN-P-other')], RULES)
    assert not detect([claim(), claim('SYN-C-B', facility_id='SYN-F-other')], RULES)
    assert not detect([claim(), claim('SYN-C-B', service_date='2026-05-20')], RULES)
    assert not detect([claim(), claim('SYN-C-B', procedure_group='XRAY')], RULES)
    related = [claim(facility_group='SYN-F-GROUP'), claim('SYN-C-B', facility_id='SYN-F-other', facility_group='SYN-F-GROUP')]
    assert len(detect(related, RULES)) == 1


def test_cancellation_correction_is_protected_in_both_input_orders():
    original = claim(claim_status='cancelled')
    corrected = claim('SYN-C-B', claim_status='corrected', original_claim_id=original.claim_id)
    for a, b in [(original, corrected), (corrected, original)]:
        pair = assess(a, b, RULES, 'group')
        assert pair.protected and pair.risk_score == 0
        assert pair.risk_reducers[0].code == 'PREVIOUS_CLAIM_CANCELLED'


def test_schedule_protection_requires_both_dates_and_distinct_services():
    a = claim(scheduled_service=True, scheduled_date='2026-05-10')
    b = claim('SYN-C-B', service_date='2026-05-11', scheduled_service=True, scheduled_date='2026-05-11')
    assert assess(a, b, RULES, 'group').protected
    assert not assess(a, b.model_copy(update={'scheduled_date': ''}), RULES, 'group').protected
    assert not assess(a, b.model_copy(update={'service_date': a.service_date}), RULES, 'group').protected


def test_distinct_visits_and_missing_clinical_fields_have_separate_semantics():
    pair = assess(claim(visit_id='SYN-V-A'), claim('SYN-C-B', visit_id='SYN-V-B'), RULES, 'group')
    assert pair.protected and pair.risk_score == 0
    missing = assess(claim(), claim('SYN-C-B', diagnosis_group='', procedure_group=''), RULES, 'group')
    assert missing.needs_data
    assert not missing.protected
    assert missing.risk_score < missing.raw_score
    assert 'MISSING_INFORMATION' in [reducer.code for reducer in missing.risk_reducers]


def test_absent_cancellation_is_never_a_risk_reducer():
    pair = assess(claim(), claim('SYN-C-B'), RULES, 'group')
    assert not pair.risk_reducers


def test_explicit_split_episode_is_explained_and_grouped():
    claims = [claim(f'SYN-C-{i}', episode_id='SYN-E-A', claim_amount=f'{100000+i*10000}.00') for i in range(3)]
    pairs = detect(claims, RULES)
    assert len(pairs) == 3
    assert len({pair.episode_group for pair in pairs}) == 1
    assert all('POSSIBLE_EPISODE_SPLIT' in pair.triggered_reasons for pair in pairs)


def test_candidate_cap_fails_without_partial_processing():
    import pytest

    from klaimkembar.errors import Rejection
    claims = [claim(f'SYN-C-{i}') for i in range(3)]
    with pytest.raises(Rejection) as caught:
        detect(claims, replace(RULES, maximum_candidates=1))
    assert caught.value.code == 'CANDIDATE_LIMIT'


def test_missing_field_sides_match_canonical_claim_ids():
    pair = assess(claim('SYN-C-Z', diagnosis_group=''), claim('SYN-C-A'), RULES, 'group')
    assert pair.claim_a == 'SYN-C-A'
    assert 'claim_b.diagnosis_group' in pair.missing_information
    assert 'claim_a.diagnosis_group' not in pair.missing_information


def test_unlinked_cancellation_lowers_score_without_proving_correction():
    pair = assess(claim(claim_status='cancelled'), claim('SYN-C-B'), RULES, 'group')
    assert not pair.protected
    assert pair.raw_score - pair.risk_score == RULES.cancelled_reduction
