import random
from datetime import date, timedelta
from itertools import combinations
from typing import Literal

from klaimkembar.models import Claim, TruthPair


# Generator never imports scoring rules; labels describe planted scenarios.
def generate(seed: int, count: int = 5000) -> tuple[list[Claim], list[TruthPair]]:
    rng = random.Random(seed)
    claims: list[Claim] = []
    truth: list[TruthPair] = []
    scenarios = ['normal', 'exact', 'changed', 'coding', 'split', 'schedule', 'correction', 'visits', 'missing', 'evasive']
    weights = [rng.uniform(20, 38), rng.uniform(5, 11), rng.uniform(8, 18), rng.uniform(3, 9),
               rng.uniform(2, 6), rng.uniform(8, 18), rng.uniform(5, 10), rng.uniform(8, 15), rng.uniform(3, 9), rng.uniform(3, 8)]
    group = 0
    while len(claims) < count:
        group += 1
        scenario = rng.choices(scenarios, weights=weights, k=1)[0]
        size = 1 if scenario == 'normal' else 3 if scenario == 'split' else 2
        size = min(size, count - len(claims))
        service = date(2026, 1, 1) + timedelta(days=rng.randrange(120))
        amount = rng.randrange(120000, 900000, 500)
        facility = f'SYN-F-{rng.randrange(1, 12):02}'
        participant = f'SYN-P-{seed}-{group}'
        episode = f'SYN-E-{seed}-{group}' if scenario == 'split' else ''
        members: list[Claim] = []
        for offset in range(size):
            identity = f'SYN-C-{seed}-{len(claims) + 1:06}'
            current_date = service
            current_amount = amount
            diagnosis = rng.choice(['M54.5', 'M54.1', 'M25.5']) if offset == 0 else members[0].diagnosis_group
            procedure = 'PHYSIO-SESSION'
            status: Literal['active', 'cancelled', 'corrected'] = 'active'
            original = ''
            schedule = False
            schedule_date = ''
            visit = ''
            current_facility = facility
            if offset and scenario in ['changed', 'coding', 'missing']:
                current_date += timedelta(days=rng.choice([1, 2, 3]))
                current_amount += rng.randrange(-5000, 15000, 500)
            if offset and scenario == 'coding':
                diagnosis = 'M54.9'
                procedure = rng.choice(['PHYSIO-SESS', 'REHAB-PHYSIO', 'THERAPY-SESSION'])
            if scenario == 'split':
                current_date += timedelta(days=offset)
                current_amount = amount // size + offset * rng.randrange(1000, 10000)
            if scenario == 'schedule':
                current_date += timedelta(days=offset * rng.choice([1, 2, 7]))
                schedule = True
                schedule_date = current_date.isoformat()
            if scenario == 'correction':
                status = 'cancelled' if offset == 0 else 'corrected'
                if offset:
                    original = members[0].claim_id
                    current_amount += rng.randrange(-1000, 5000, 500)
            if scenario == 'visits':
                current_date += timedelta(days=offset * rng.choice([0, 1, 2]))
                visit = f'SYN-V-{seed}-{group}-{offset}'
            if offset and scenario == 'missing':
                diagnosis = ''
                if rng.random() < 0.45:
                    procedure = ''
            if offset and scenario == 'evasive':
                current_date += timedelta(days=rng.choice([4, 5, 10, 2]))
                current_amount += rng.randrange(20000, 100000, 1000)
                if rng.random() < 0.4:
                    current_facility = f'SYN-F-RELATED-{rng.randrange(1, 5)}'
            submitted = current_date + timedelta(days=rng.randrange(1, 8))
            claim = Claim(claim_id=identity, participant_token=participant, facility_id=current_facility,
                          service_date=current_date.isoformat(), submission_date=submitted.isoformat(),
                          diagnosis_group=diagnosis, procedure_group=procedure, claim_amount=f'{current_amount:.2f}',
                          claim_status=status, original_claim_id=original, episode_id=episode,
                          visit_id=visit, scheduled_service=schedule, scheduled_date=schedule_date)
            claims.append(claim)
            members.append(claim)
        duplicate = scenario in ['exact', 'changed', 'coding', 'split', 'evasive']
        for a, b in combinations(members, 2):
            first, second = sorted([a.claim_id, b.claim_id])
            truth.append(TruthPair(claim_a=first, claim_b=second, is_duplicate=duplicate))
    return claims, truth
