"""BPJS 2025 Real Data Profiler & Adapter Architect module.

Bridges empirical BPJS Kesehatan 2025 release datasets (FKRTL / Non-Kapitasi)
with the canonical klaimkembar Claim models and validation pipeline.
Provides deterministic HMAC-SHA256 pseudonymization, empirical distribution loading,
and calibrated synthetic dataset generation.
"""

import hashlib
import hmac
import json
import random
import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from itertools import combinations
from pathlib import Path
from typing import Any, Literal

from klaimkembar.models import Claim, TruthPair

# Default salt for deterministic pseudonymization
DEFAULT_SALT = "klaimkembar-bpjs-2025"

# Empirical ICD-10 and ICD-9-CM defaults from BPJS 2025 regular sample
EMPIRICAL_DIAGNOSES = [
    ("Z50.1", 0.42),   # Other physical therapy / rehab
    ("Z09.8", 0.19),   # Follow-up examination after other treatment
    ("Z50.9", 0.08),   # Care involving rehabilitation procedure, unspecified
    ("Z48.0", 0.05),   # Surgical follow-up & dressing
    ("M54.5", 0.05),   # Low back pain
    ("M54.1", 0.03),   # Radiculopathy
    ("M17.9", 0.03),   # Gonarthrosis / knee arthrosis
    ("M79.1", 0.03),   # Myalgia / fibrositis
    ("I69.3", 0.03),   # Sequelae of stroke / hemiparesis
    ("M51.2", 0.02),   # Lumbar disc displacement
    ("M75.0", 0.02),   # Adhesive capsulitis / frozen shoulder
    ("I63.9", 0.02),   # Cerebral infarction / stroke
    ("M25.5", 0.02),   # Joint pain
    ("G81.9", 0.01),   # Hemiplegia
]

EMPIRICAL_PROCEDURES = [
    ("93.39", 0.35),   # Other physical therapy
    ("93.35", 0.18),   # Other heat therapy
    ("93.34", 0.14),   # Diathermy
    ("93.57", 0.10),   # Application of other wound dressing
    ("93.12", 0.08),   # Other active musculoskeletal exercise
    ("93.11", 0.06),   # Assisting exercise
    ("93.75", 0.04),   # Speech therapy
    ("93.83", 0.03),   # Occupational therapy
    ("93.22", 0.02),   # Ambulation and gait training
]

EMPIRICAL_TARIFFS = [
    (106200, 0.05),    # Minimum baseline outpatient tariff
    (134300, 0.25),    # P25 outpatient rehab tariff
    (138000, 0.40),    # Median standard outpatient rehab tariff
    (191900, 0.18),    # P75 multi-modality rehab tariff
    (205200, 0.07),    # P90 advanced rehab tariff
    (224400, 0.04),    # P95 specialized therapy tariff
    (385000, 0.01),    # Higher tier hospital tariff
]

EMPIRICAL_INTER_VISIT_GAPS = [
    (0, 0.001),        # Same-day repeat (empirical baseline 0.01%, modeled for duplicates)
    (1, 0.029),        # Next-day follow-up
    (2, 0.141),        # 2-day cadence (e.g. Mon -> Wed)
    (3, 0.141),        # 3-day cadence (e.g. Wed -> Fri)
    (5, 0.228),        # 5-day cadence
    (7, 0.228),        # Weekly recurrence
    (14, 0.129),       # Bi-weekly recurrence
    (21, 0.060),       # 3-week cadence
    (30, 0.043),       # Monthly cadence
]


def pseudonymize_token(raw_value: str, prefix: str = "SYN-", salt: str = DEFAULT_SALT) -> str:
    """Deterministically pseudonymize any identifier using HMAC-SHA256 into SYN-... format.

    Guarantees strict privacy compliance by never leaking raw participant or claim IDs.
    """
    clean_val = str(raw_value).strip()
    if not clean_val:
        return f"{prefix}ANON-{hashlib.sha256(salt.encode()).hexdigest()[:8].upper()}"
    digest = hmac.new(salt.encode("utf-8"), clean_val.encode("utf-8"), hashlib.sha256).hexdigest()[:12].upper()
    return f"{prefix}{digest}"


def pseudonymize_participant(raw_pstv01: str, salt: str = DEFAULT_SALT) -> str:
    """Pseudonymize raw PSTV01 participant number into SYN-P-... token."""
    return pseudonymize_token(raw_pstv01, prefix="SYN-P-", salt=salt)


def pseudonymize_claim(raw_fkl02: str, salt: str = DEFAULT_SALT) -> str:
    """Pseudonymize raw FKL02 claim / visit ID into SYN-BPJS-... format."""
    return pseudonymize_token(raw_fkl02, prefix="SYN-BPJS-", salt=salt)


def pseudonymize_facility(facility_key: str, salt: str = DEFAULT_SALT) -> str:
    """Pseudonymize hospital / provider characteristics into SYN-F-... facility ID."""
    return pseudonymize_token(facility_key, prefix="SYN-F-", salt=salt)


def pseudonymize_visit(raw_visit: str, salt: str = DEFAULT_SALT) -> str:
    """Pseudonymize visit identifier into SYN-V-... format."""
    return pseudonymize_token(raw_visit, prefix="SYN-V-", salt=salt)


def pseudonymize_episode(raw_episode: str, salt: str = DEFAULT_SALT) -> str:
    """Pseudonymize episode identifier into SYN-E-... format."""
    return pseudonymize_token(raw_episode, prefix="SYN-E-", salt=salt)


@dataclass(frozen=True)
class BPJSFieldMapping:
    """Mapping configuration from raw BPJS FKRTL dictionary columns to canonical fields."""

    participant_col: str = "PSTV01"
    visit_id_col: str = "FKL02"
    service_date_col: str = "FKL03"
    discharge_date_col: str = "FKL04"
    province_col: str = "FKL05"
    regency_col: str = "FKL06"
    ownership_col: str = "FKL07"
    facility_type_col: str = "FKL09"
    service_level_col: str = "FKL10"
    polyclinic_col: str = "FKL11"
    dx_in_col: str = "FKL15A"
    dx_primary_col: str = "FKL17A"
    dx_detailed_col: str = "FKL18"
    procedure_col: str = "FKL30"
    tariff_billed_col: str = "FKL47"
    tariff_verified_col: str = "FKL48"


def _clean_icd10(code: str) -> str:
    """Format ICD-10 code (e.g. 'M545' -> 'M54.5', 'Z501' -> 'Z50.1')."""
    raw = code.strip().upper()
    if not raw:
        return ""
    if len(raw) > 3 and "." not in raw:
        return f"{raw[:3]}.{raw[3:]}"
    return raw


def _clean_icd9cm(proc: str) -> str:
    """Extract and format ICD-9-CM procedure code from raw FKL30 string."""
    raw = proc.strip()
    if not raw:
        return ""
    match = re.search(r"\b(\d{2}\.?\d{1,2})\b", raw)
    if match:
        code = match.group(1)
        if "." not in code and len(code) == 4:
            return f"{code[:2]}.{code[2:]}"
        return code
    return raw[:50]


def raw_fkrtl_to_claim(
    record: dict[str, Any],
    mapping: BPJSFieldMapping | None = None,
    salt: str = DEFAULT_SALT,
) -> Claim:
    """Convert a single raw BPJS FKRTL dictionary row into a canonical Claim object.

    Applies deterministic pseudonymization to all identifiers and validates formatting.
    """
    m = mapping or BPJSFieldMapping()

    raw_participant = str(record.get(m.participant_col, "")).strip()
    raw_visit = str(record.get(m.visit_id_col, "")).strip()
    service_date_raw = str(record.get(m.service_date_col, "")).strip()
    discharge_date_raw = str(record.get(m.discharge_date_col, "")).strip()

    claim_id = pseudonymize_claim(raw_visit, salt=salt)
    participant_token = pseudonymize_participant(raw_participant, salt=salt)

    facility_composite = f"{record.get(m.province_col, '')}-{record.get(m.regency_col, '')}-{record.get(m.facility_type_col, '')}"
    facility_id = pseudonymize_facility(facility_composite, salt=salt)

    service_date = service_date_raw if re.match(r"^\d{4}-\d{2}-\d{2}$", service_date_raw) else "2024-01-01"
    submission_date = discharge_date_raw if re.match(r"^\d{4}-\d{2}-\d{2}$", discharge_date_raw) else service_date

    dx_raw = str(record.get(m.dx_detailed_col) or record.get(m.dx_primary_col) or record.get(m.dx_in_col) or "").strip()
    diagnosis_group = _clean_icd10(dx_raw)

    proc_raw = str(record.get(m.procedure_col, "")).strip()
    procedure_group = _clean_icd9cm(proc_raw)

    raw_amount = record.get(m.tariff_billed_col) or record.get(m.tariff_verified_col) or 138000.0
    try:
        amount_dec = Decimal(str(raw_amount)).quantize(Decimal("0.01"))
        claim_amount = f"{amount_dec:.2f}"
    except Exception:
        claim_amount = "138000.00"

    raw_visit_evidence = str(record.get("visit_evidence") or raw_visit).strip()
    visit_id = pseudonymize_visit(raw_visit_evidence, salt=salt) if raw_visit_evidence else ""

    return Claim(
        claim_id=claim_id,
        participant_token=participant_token,
        facility_id=facility_id,
        service_date=service_date,
        submission_date=submission_date,
        diagnosis_group=diagnosis_group,
        procedure_group=procedure_group,
        claim_amount=claim_amount,
        claim_status="active",
        original_claim_id="",
        facility_group="",
        episode_id="",
        visit_id=visit_id,
        scheduled_service=False,
        scheduled_date="",
    )


def load_bpjs_profile(path: Path | str | None = None) -> dict[str, Any]:
    """Load empirical BPJS 2025 metadata profile JSON."""
    if path is None:
        target = Path(__file__).resolve().parent.parent / "examples" / "bpjs2025_profile.json"
    else:
        target = Path(path)
    if not target.exists():
        raise FileNotFoundError(f"BPJS profile not found at {target}")
    return json.loads(target.read_text(encoding="utf-8"))  # type: ignore[no-any-return]


def _pick_weighted(rng: random.Random, items_with_weights: Sequence[tuple[Any, float]]) -> Any:
    """Helper to pick an item from a list of (item, weight) tuples."""
    items = [item for item, _ in items_with_weights]
    weights = [weight for _, weight in items_with_weights]
    return rng.choices(items, weights=weights, k=1)[0]


def generate_bpjs_calibrated_dataset(
    seed: int = 2025,
    count: int = 5000,
) -> tuple[list[Claim], list[TruthPair]]:
    """Generate a calibrated dataset grounded in empirical BPJS 2025 distributions.

    Features:
    - Real ICD-10 diagnosis codes (Z50.1, Z09.8, M54.5, M17.9, etc.)
    - Real ICD-9-CM procedure codes (93.39, 93.35, 93.34, 93.11, 93.12, 93.57, etc.)
    - Realistic FKRTL claim amounts (IDR 106,200 to 385,000)
    - Realistic 41.7% procedure / diagnosis missingness pattern in incomplete scenarios
    - Realistic repeat billing vs legitimate recurring physiotherapy cadences
    - 100% complete TruthPair universe for all multi-visit participants
    """
    rng = random.Random(seed)
    claims: list[Claim] = []
    truth: list[TruthPair] = []

    # Scenario distributions calibrated for realistic audit proportions
    # normal: single visit (no duplicate)
    # recurring: legitimate multi-session physical therapy (scheduled, not duplicate)
    # exact_dup: accidental double submission (same day/service, duplicate)
    # changed_dup: duplicate with adjusted tariff or slightly altered dates
    # coding_var: duplicate with unbundled or altered procedure/diagnosis code
    # split_bill: duplicate split into multiple claim items
    # correction: legitimate replacement claim linked to cancelled original (not duplicate)
    # missing_info: duplicate with 41.7% missing procedure/diagnosis information
    # evasive_facility: duplicate submitted across related sister facilities
    scenarios = [
        "normal",
        "recurring",
        "distinct_visits",
        "exact_dup",
        "changed_dup",
        "coding_var",
        "split_bill",
        "correction",
        "missing_info",
        "evasive_facility",
    ]
    weights = [
        40.0,  # Single normal visits
        18.0,  # Legitimate scheduled recurring physical therapy
        8.0,   # Legitimate distinct visits with attendance verification
        8.0,   # Exact duplicate submission
        8.0,   # Changed amount/date near-duplicate
        5.0,   # Coding / procedure variation duplicate
        3.0,   # Split billing across episode
        4.0,   # Cancelled and corrected replacement pair
        3.0,   # Incomplete clinical info (41.7% FKL30 missingness)
        3.0,   # Evasive sister-facility duplicate
    ]

    group = 0
    while len(claims) < count:
        group += 1
        scenario = rng.choices(scenarios, weights=weights, k=1)[0]
        size = 1 if scenario == "normal" else 3 if scenario == "split_bill" else 2
        size = min(size, count - len(claims))

        base_date = date(2024, 1, 15) + timedelta(days=rng.randrange(300))
        base_tariff = _pick_weighted(rng, EMPIRICAL_TARIFFS)
        base_facility = f"SYN-F-{rng.randrange(1, 20):02}"
        participant_token = f"SYN-P-{seed}-{group:05}"
        episode_id = f"SYN-E-{seed}-{group:05}" if scenario == "split_bill" else ""
        facility_group = f"SYN-FG-{seed % 5 + 1}" if scenario == "evasive_facility" else ""

        base_diag = _pick_weighted(rng, EMPIRICAL_DIAGNOSES)
        base_proc = _pick_weighted(rng, EMPIRICAL_PROCEDURES)

        members: list[Claim] = []

        for offset in range(size):
            claim_id = f"SYN-BPJS-{seed}-{len(claims) + 1:06}"
            current_date = base_date
            current_amount = base_tariff
            current_facility = base_facility
            current_diag = base_diag
            current_proc = base_proc
            status: Literal["active", "cancelled", "corrected"] = "active"
            original_claim_id = ""
            scheduled_service = False
            scheduled_date = ""
            visit_id = ""

            if scenario == "recurring":
                # Legitimate therapy recurring cadence within blocking window (1-3 days) or weekly
                gap_days = _pick_weighted(rng, [(1, 0.25), (2, 0.45), (3, 0.30)])
                current_date = base_date + timedelta(days=offset * gap_days)
                scheduled_service = True
                scheduled_date = current_date.isoformat()

            elif scenario == "distinct_visits":
                # Legitimate distinct attendance verified via visit_id
                current_date = base_date + timedelta(days=offset * rng.choice([0, 1, 2]))
                visit_id = f"SYN-V-{seed}-{group:05}-{offset + 1}"

            elif scenario == "exact_dup":
                # Same day, exact same amount & diagnosis/procedure
                if offset > 0:
                    current_date = base_date

            elif scenario == "changed_dup":
                # Slight variation in amount (+/- 2,000 to 10,000 IDR) and 1-2 days gap
                if offset > 0:
                    current_date = base_date + timedelta(days=rng.choice([1, 2, 3]))
                    current_amount += rng.choice([-5000, 5000, 10000])

            elif scenario == "coding_var":
                # Procedure or diagnosis code variation within >=0.6 similarity
                if offset > 0:
                    current_date = base_date + timedelta(days=rng.choice([1, 2]))
                    current_proc = "93.39" if base_proc.startswith("93.3") else base_proc
                    current_diag = "Z50.1" if base_diag.startswith("Z50") else base_diag

            elif scenario == "split_bill":
                # Multiple components billed on same day or consecutive days
                current_date = base_date + timedelta(days=offset)
                current_amount = base_tariff // size + (offset * 1500)

            elif scenario == "correction":
                # Original claim cancelled, replacement claim corrected with link
                if offset == 0:
                    status = "cancelled"
                else:
                    status = "corrected"
                    original_claim_id = members[0].claim_id
                    current_amount += 2000

            elif scenario == "missing_info":
                # Simulates 41.7% empirical missingness on procedure or diagnosis
                if offset > 0:
                    current_date = base_date + timedelta(days=rng.choice([1, 2]))
                    current_diag = ""
                    if rng.random() < 0.417:
                        current_proc = ""

            elif scenario == "evasive_facility":
                # Sister branch / related facility billing
                if offset > 0:
                    current_date = base_date + timedelta(days=rng.choice([1, 2, 5]))
                    current_amount += rng.choice([5000, 15000])
                    if rng.random() < 0.5:
                        current_facility = f"SYN-F-SISTER-{rng.randrange(1, 6):02}"

            submission_date = current_date + timedelta(days=rng.randrange(1, 6))

            claim = Claim(
                claim_id=claim_id,
                participant_token=participant_token,
                facility_id=current_facility,
                service_date=current_date.isoformat(),
                submission_date=submission_date.isoformat(),
                diagnosis_group=current_diag,
                procedure_group=current_proc,
                claim_amount=f"{Decimal(current_amount):.2f}",
                claim_status=status,
                original_claim_id=original_claim_id,
                facility_group=facility_group,
                episode_id=episode_id,
                visit_id=visit_id,
                scheduled_service=scheduled_service,
                scheduled_date=scheduled_date,
            )
            claims.append(claim)
            members.append(claim)

        # Ground-truth determination:
        # Duplicates are only true for planted repeat billing scenarios
        is_dup = scenario in ["exact_dup", "changed_dup", "coding_var", "split_bill", "evasive_facility"]

        for c1, c2 in combinations(members, 2):
            first, second = sorted([c1.claim_id, c2.claim_id])
            truth.append(TruthPair(claim_a=first, claim_b=second, is_duplicate=is_dup))

    return claims, truth


def write_claims_csv(claims: list[Claim], path: Path | str) -> None:
    """Write canonical Claim objects to CSV adhering to validation schema."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    header = [
        "claim_id",
        "participant_token",
        "facility_id",
        "service_date",
        "submission_date",
        "diagnosis_group",
        "procedure_group",
        "claim_amount",
        "claim_status",
        "original_claim_id",
        "facility_group",
        "episode_id",
        "visit_id",
        "scheduled_service",
        "scheduled_date",
    ]
    lines = [",".join(header)]
    for c in claims:
        row = [
            c.claim_id,
            c.participant_token,
            c.facility_id,
            c.service_date,
            c.submission_date,
            c.diagnosis_group,
            c.procedure_group,
            c.claim_amount,
            c.claim_status,
            c.original_claim_id,
            c.facility_group,
            c.episode_id,
            c.visit_id,
            "true" if c.scheduled_service else "false",
            c.scheduled_date,
        ]
        lines.append(",".join(row))
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_truth_csv(truth: list[TruthPair], path: Path | str) -> None:
    """Write TruthPair labels to CSV adhering to validation schema."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    lines = ["claim_a,claim_b,is_duplicate"]
    for t in truth:
        label = "true" if t.is_duplicate else "false"
        lines.append(f"{t.claim_a},{t.claim_b},{label}")
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
