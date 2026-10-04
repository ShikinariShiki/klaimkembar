import hashlib
from collections import defaultdict
from datetime import date
from decimal import Decimal
from difflib import SequenceMatcher

from klaimkembar.errors import Rejection
from klaimkembar.models import Claim, Contribution, PairAssessment, Priority, Reducer
from klaimkembar.settings import Rules


def code_similarity(left: str, right: str) -> float:
    if not left or not right:
        return 0
    return SequenceMatcher(None, left.casefold(), right.casefold(), autojunk=False).ratio()


def date_distance(left: str, right: str) -> int:
    return abs((date.fromisoformat(left) - date.fromisoformat(right)).days)


def exact_match(left: Claim, right: Claim) -> bool:
    return (left.participant_token, left.facility_id, left.service_date, left.procedure_group,
            Decimal(left.claim_amount)) == (right.participant_token, right.facility_id,
                                          right.service_date, right.procedure_group, Decimal(right.claim_amount))


def assess(left: Claim, right: Claim, rules: Rules, episode_group: str) -> PairAssessment:
    if left.claim_id > right.claim_id:
        left, right = right, left
    days = date_distance(left.service_date, right.service_date)
    submission_days = date_distance(left.submission_date, right.submission_date)
    amounts = [Decimal(left.claim_amount), Decimal(right.claim_amount)]
    relative_difference = float(abs(amounts[0] - amounts[1]) / max(amounts)) if max(amounts) else 0
    procedure = code_similarity(left.procedure_group, right.procedure_group)
    diagnosis = code_similarity(left.diagnosis_group, right.diagnosis_group)
    similarities = {
        'SAME_PARTICIPANT': float(left.participant_token == right.participant_token),
        'SAME_FACILITY': float(left.facility_id == right.facility_id),
        'SERVICE_DATE_NEAR': max(0.0, 1 - days / (rules.blocking_days + 1)),
        'SIMILAR_PROCEDURE': procedure if procedure >= rules.code_similarity_minimum else 0,
        'SIMILAR_DIAGNOSIS': diagnosis if diagnosis >= rules.code_similarity_minimum else 0,
        'SIMILAR_AMOUNT': max(0.0, 1 - relative_difference / rules.amount_relative_tolerance),
        'SUBMISSION_DATE_NEAR': max(0.0, 1 - submission_days / (rules.submission_days + 1)),
    }
    contributions = [Contribution(code=code, points=round(maximum * similarities[code], 4), maximum=maximum)
                     for code, maximum in rules.weights.items()]
    raw_score = round(sum(item.points for item in contributions), 4)
    reasons = [item.code for item in contributions if item.points > 0]
    reducers: list[Reducer] = []
    missing = [f'{side}.{field}' for side, claim in [('claim_a', left), ('claim_b', right)]
               for field in ['diagnosis_group', 'procedure_group'] if not getattr(claim, field)]
    protected = False
    correction = ((left.claim_status == 'cancelled' and right.claim_status == 'corrected' and right.original_claim_id == left.claim_id)
                  or (right.claim_status == 'cancelled' and left.claim_status == 'corrected' and left.original_claim_id == right.claim_id))
    if correction:
        reducers.append(Reducer(code='PREVIOUS_CLAIM_CANCELLED', points=rules.protect_reduction,
                                evidence='Klaim koreksi merujuk klaim yang dibatalkan dalam dataset.'))
        protected = True
    elif 'cancelled' in [left.claim_status, right.claim_status]:
        reducers.append(Reducer(code='CANCELLED_CLAIM', points=rules.cancelled_reduction,
                                evidence='Salah satu klaim berstatus cancelled; tautan koreksi belum tersedia.'))
    schedule_evidence = (left.scheduled_service and right.scheduled_service
                         and left.scheduled_date == left.service_date and right.scheduled_date == right.service_date
                         and left.service_date != right.service_date)
    if schedule_evidence:
        reducers.append(Reducer(code='SCHEDULED_RECURRING_SERVICE', points=rules.protect_reduction,
                                evidence='Kedua tanggal layanan cocok dengan jadwal sintetis yang dinyatakan.'))
        protected = True
    elif left.procedure_group == right.procedure_group and days > 0:
        missing.append('scheduled_service_evidence')
    if left.visit_id and right.visit_id and left.visit_id != right.visit_id:
        reducers.append(Reducer(code='DISTINCT_VISITS', points=rules.protect_reduction,
                                evidence='Dua visit_id sintetis berbeda. Bukti di data sumber, bukan tebakan skor.'))
        protected = True
    elif days > 0:
        missing.append('visit_evidence')
    needs_data = any(not claim.diagnosis_group or not claim.procedure_group for claim in [left, right])
    if needs_data:
        reducers.append(Reducer(code='MISSING_INFORMATION', points=rules.missing_information_reduction,
                                evidence='Diagnosis atau tindakan belum tersedia. Data kurang bukan bukti pelanggaran.'))
    if left.episode_id and left.episode_id == right.episode_id and left.claim_amount != right.claim_amount:
        reasons.append('POSSIBLE_EPISODE_SPLIT')
    score = 0.0 if protected else round(max(0.0, raw_score - sum(item.points for item in reducers)), 4)
    priority: Priority = 'high' if score >= rules.high_priority else 'medium' if score >= rules.medium_priority else 'low'
    a, b = sorted([left.claim_id, right.claim_id])
    return PairAssessment(claim_a=a, claim_b=b, episode_group=episode_group, baseline_match=exact_match(left, right),
                          raw_score=raw_score, risk_score=score, risk_level=priority, triggered_reasons=reasons,
                          contributions=contributions, risk_reducers=reducers, missing_information=missing,
                          protected=protected, needs_data=needs_data)


def detect(claims: list[Claim], rules: Rules) -> list[PairAssessment]:
    participants: dict[str, list[Claim]] = defaultdict(list)
    for claim in claims:
        participants[claim.participant_token].append(claim)
    candidates: list[tuple[Claim, Claim]] = []
    parents = {claim.claim_id: claim.claim_id for claim in claims}

    def root(identity: str) -> str:
        while parents[identity] != identity:
            parents[identity] = parents[parents[identity]]
            identity = parents[identity]
        return identity

    for group in participants.values():
        ordered = sorted(group, key=lambda claim: (claim.service_date, claim.claim_id))
        for index, left in enumerate(ordered):
            for right in ordered[index + 1:]:
                if date_distance(left.service_date, right.service_date) > rules.blocking_days:
                    break
                related = left.facility_id == right.facility_id or bool(left.facility_group and left.facility_group == right.facility_group)
                similar = (not left.procedure_group or not right.procedure_group or
                           code_similarity(left.procedure_group, right.procedure_group) >= rules.procedure_candidate_similarity)
                if not (related and similar):
                    continue
                candidates.append((left, right))
                if len(candidates) > rules.maximum_candidates:
                    raise Rejection(413, 'CANDIDATE_LIMIT', 'Terlalu banyak kandidat pasangan. Pecah dataset menjadi file lebih kecil.')
                parents[root(right.claim_id)] = root(left.claim_id)
    members: dict[str, list[str]] = defaultdict(list)
    for identity in parents:
        members[root(identity)].append(identity)
    group_ids = {identity: hashlib.sha256('|'.join(sorted(group)).encode()).hexdigest()[:20]
                 for identity, group in members.items()}
    pairs = [assess(left, right, rules, group_ids[root(left.claim_id)]) for left, right in candidates]
    return sorted(pairs, key=lambda pair: (-pair.risk_score, pair.claim_a, pair.claim_b))
