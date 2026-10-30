"""Unit tests for the BPJS 2025 Adapter and empirical dataset generation."""

from pathlib import Path

import pytest

from klaimkembar.bpjs_adapter import (
    BPJSFieldMapping,
    generate_bpjs_calibrated_dataset,
    load_bpjs_profile,
    pseudonymize_claim,
    pseudonymize_episode,
    pseudonymize_facility,
    pseudonymize_participant,
    pseudonymize_token,
    pseudonymize_visit,
    raw_fkrtl_to_claim,
    write_claims_csv,
    write_truth_csv,
)
from klaimkembar.models import Claim
from klaimkembar.settings import ROOT, Rules
from klaimkembar.validation import parse_claims, parse_truth


def test_pseudonymization_enforces_syn_prefix_and_privacy() -> None:
    raw_id = "0001234567890"
    token = pseudonymize_token(raw_id, prefix="SYN-P-")
    assert token.startswith("SYN-P-")
    assert raw_id not in token
    assert len(token) > 8

    # Determinism
    token_repeat = pseudonymize_token(raw_id, prefix="SYN-P-")
    assert token == token_repeat

    # Distinct inputs produce distinct tokens
    token_diff = pseudonymize_token("0009876543210", prefix="SYN-P-")
    assert token != token_diff

    # Specialized helpers
    assert pseudonymize_participant(raw_id).startswith("SYN-P-")
    assert pseudonymize_claim("100200300").startswith("SYN-BPJS-")
    assert pseudonymize_facility("11-1173-1").startswith("SYN-F-")
    assert pseudonymize_visit("VISIT-99").startswith("SYN-V-")
    assert pseudonymize_episode("EPISODE-88").startswith("SYN-E-")


def test_raw_fkrtl_to_claim_canonical_mapping() -> None:
    raw_record = {
        "PSTV01": "000192837465",
        "FKL02": "FKRTL-2024-998811",
        "FKL03": "2024-03-15",
        "FKL04": "2024-03-15",
        "FKL05": "31",
        "FKL06": "3171",
        "FKL07": "1",
        "FKL09": "2",
        "FKL10": "1",
        "FKL11": "15",
        "FKL15A": "Z50",
        "FKL17A": "Z50",
        "FKL18": "Z501",
        "FKL30": "9339 - Other physical therapy",
        "FKL47": 138000.0,
        "FKL48": 138000.0,
    }

    claim = raw_fkrtl_to_claim(raw_record)
    assert isinstance(claim, Claim)
    assert claim.claim_id.startswith("SYN-BPJS-")
    assert claim.participant_token.startswith("SYN-P-")
    assert claim.facility_id.startswith("SYN-F-")
    assert claim.service_date == "2024-03-15"
    assert claim.submission_date == "2024-03-15"
    assert claim.diagnosis_group == "Z50.1"
    assert claim.procedure_group == "93.39"
    assert claim.claim_amount == "138000.00"
    assert claim.claim_status == "active"
    assert claim.visit_id.startswith("SYN-V-")

    # Privacy constraint: raw PSTV01 and FKL02 are never in the claim fields
    assert "000192837465" not in claim.participant_token
    assert "FKRTL-2024-998811" not in claim.claim_id


def test_raw_fkrtl_to_claim_with_missing_and_fallback_fields() -> None:
    empty_record: dict[str, str] = {}
    claim = raw_fkrtl_to_claim(empty_record)
    assert claim.claim_id.startswith("SYN-BPJS-")
    assert claim.participant_token.startswith("SYN-P-")
    assert claim.facility_id.startswith("SYN-F-")
    assert claim.service_date == "2024-01-01"
    assert claim.submission_date == "2024-01-01"
    assert claim.diagnosis_group == ""
    assert claim.procedure_group == ""
    assert claim.claim_amount == "138000.00"


def test_custom_field_mapping() -> None:
    custom_mapping = BPJSFieldMapping(
        participant_col="CUSTOM_PESERTA",
        visit_id_col="CUSTOM_KUNJUNGAN",
        service_date_col="CUSTOM_TGL",
        procedure_col="CUSTOM_TINDAKAN",
    )
    record = {
        "CUSTOM_PESERTA": "999888777",
        "CUSTOM_KUNJUNGAN": "VIS-101",
        "CUSTOM_TGL": "2024-05-20",
        "CUSTOM_TINDAKAN": "93.39 - Fisioterapi",
    }
    claim = raw_fkrtl_to_claim(record, mapping=custom_mapping)
    assert claim.service_date == "2024-05-20"
    assert claim.procedure_group == "93.39"
    assert claim.participant_token.startswith("SYN-P-")


def test_load_bpjs_profile() -> None:
    profile = load_bpjs_profile()
    assert profile["total_rows_inspected"] == 1699219
    assert profile["physiotherapy_subset_size"] == 229682
    assert "FKL30_procedure_missingness_rate" in profile["missingness"]["full_dataset"]
    assert profile["missingness"]["full_dataset"]["FKL30_procedure_missingness_rate"] > 0.40
    assert "Z50" in profile["top_diagnosis_groups_icd10"]
    assert "9339 - Other physical therapy" in profile["top_procedure_codes_icd9cm"]
    assert profile["tariffs_idr"]["FKL47_biaya_tagih"]["median"] == 138000.0

    # Non-existent path raises FileNotFoundError
    with pytest.raises(FileNotFoundError):
        load_bpjs_profile(Path("/nonexistent/profile.json"))


def test_generate_bpjs_calibrated_dataset_properties() -> None:
    claims, truth = generate_bpjs_calibrated_dataset(seed=42, count=100)
    assert len(claims) == 100
    assert len(truth) > 0

    for c in claims:
        assert c.claim_id.startswith("SYN-BPJS-")
        assert c.participant_token.startswith("SYN-P-")
        assert c.facility_id.startswith("SYN-F-")
        assert c.claim_status in ["active", "cancelled", "corrected"]

    # Determinism
    claims_repeat, truth_repeat = generate_bpjs_calibrated_dataset(seed=42, count=100)
    assert [c.claim_id for c in claims] == [c.claim_id for c in claims_repeat]
    assert len(truth) == len(truth_repeat)


def test_calibrated_dataset_passes_validation_pipeline(tmp_path: Path) -> None:
    rules = Rules.load(ROOT / "rules.json")
    claims, truth = generate_bpjs_calibrated_dataset(seed=777, count=250)

    claims_file = tmp_path / "test_claims.csv"
    labels_file = tmp_path / "test_labels.csv"

    write_claims_csv(claims, claims_file)
    write_truth_csv(truth, labels_file)

    parsed = parse_claims(claims_file.read_bytes(), "test_claims.csv", max_rows=1000)
    assert parsed.summary.valid_rows == 250
    assert parsed.summary.invalid_rows == 0

    truth_pairs = parse_truth(labels_file.read_bytes(), parsed.claims, rules)
    assert len(truth_pairs) == len(truth)


def test_existing_bpjs2025_example_files() -> None:
    rules = Rules.load(ROOT / "rules.json")
    claims_path = ROOT / "examples" / "bpjs2025_claims.csv"
    labels_path = ROOT / "examples" / "bpjs2025_labels.csv"

    assert claims_path.exists(), "bpjs2025_claims.csv must exist in examples"
    assert labels_path.exists(), "bpjs2025_labels.csv must exist in examples"

    parsed = parse_claims(claims_path.read_bytes(), "bpjs2025_claims.csv", max_rows=10000)
    assert parsed.summary.total_rows == 5000
    assert parsed.summary.valid_rows == 5000
    assert parsed.summary.invalid_rows == 0

    truth = parse_truth(labels_path.read_bytes(), parsed.claims, rules)
    assert len(truth) == 2036
