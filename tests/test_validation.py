import csv
import io

import pytest

from klaimkembar.errors import Rejection
from klaimkembar.settings import ROOT, Rules
from klaimkembar.validation import COLUMNS, parse_claims, parse_truth


def csv_bytes(rows, columns=None):
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=columns or COLUMNS)
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue().encode()


def claim_row(**changes):
    row = dict(claim_id='SYN-C-A', participant_token='SYN-P-A', facility_id='SYN-F-A',
               service_date='2026-05-10', submission_date='2026-05-12', diagnosis_group='M54',
               procedure_group='PHYSIO', claim_amount='350000.00', claim_status='active', original_claim_id='')
    row.update(changes)
    return row


@pytest.fixture
def rules():
    return Rules.load(ROOT / 'rules.json')


def test_valid_csv_uses_decimal_money_and_real_dates(rules):
    batch = parse_claims(csv_bytes([claim_row()]), 'claims.csv', 10000)
    assert batch.claims[0].claim_amount == '350000.00'
    assert batch.summary.valid_rows == 1
    assert batch.summary.invalid_rows == 0


@pytest.mark.parametrize('payload,filename,code', [
    (b'abc', 'claim.txt', 'FILE_FORMAT'), (b'', 'claims.csv', 'FILE_EMPTY'),
    (b'claim_id\n', 'claims.csv', 'MISSING_COLUMNS'),
    (b'claim_id,claim_id\nx,x\n', 'claims.csv', 'DUPLICATE_COLUMNS'),
    (b'\xff\xfe', 'claims.csv', 'FILE_ENCODING')])
def test_file_failures_have_stable_codes(payload, filename, code):
    with pytest.raises(Rejection) as caught:
        parse_claims(payload, filename, 10000)
    assert caught.value.code == code


@pytest.mark.parametrize('changes,field', [
    ({'claim_amount': '-1'}, 'claim_amount'), ({'claim_amount': 'NaN'}, 'claim_amount'),
    ({'claim_amount': '1.234'}, 'claim_amount'), ({'service_date': '2026-02-30'}, 'service_date'),
    ({'claim_id': ''}, 'claim_id'), ({'participant_token': 'REAL123'}, 'participant_token'),
    ({'claim_status': 'paid'}, 'claim_status'), ({'original_claim_id': 'SYN-C-unknown'}, 'original_claim_id'),
    ({'claim_status': 'corrected'}, 'original_claim_id')])
def test_invalid_rows_are_reported_without_partial_acceptance(changes, field):
    with pytest.raises(Rejection) as caught:
        parse_claims(csv_bytes([claim_row(), claim_row(**({'claim_id': 'SYN-C-B'} | changes))]), 'claims.csv', 10000)
    assert caught.value.validation.invalid_rows >= 1
    assert any(issue.field == field for issue in caught.value.details)


def test_incomplete_clinical_information_is_visible_not_invalid():
    batch = parse_claims(csv_bytes([claim_row(diagnosis_group='', procedure_group='')]), 'claims.csv', 10000)
    assert batch.summary.incomplete_rows == 1
    assert batch.summary.valid_rows == 1
    assert len(batch.summary.issues) == 2


def test_duplicate_claims_and_rows_rejected():
    with pytest.raises(Rejection) as caught:
        parse_claims(csv_bytes([claim_row(), claim_row()]), 'claims.csv', 10000)
    assert {'DUPLICATE_ROW', 'DUPLICATE_ID'} <= {issue.code for issue in caught.value.details}


def test_row_limit_and_unknown_columns_rejected():
    with pytest.raises(Rejection) as caught:
        parse_claims(csv_bytes([claim_row(), claim_row(claim_id='SYN-C-B')]), 'claims.csv', 1)
    assert caught.value.status == 413
    with pytest.raises(Rejection) as caught:
        parse_claims(csv_bytes([claim_row(name='private')], COLUMNS + ['name']), 'claims.csv', 10000)
    assert caught.value.code == 'UNSUPPORTED_COLUMNS'


def test_truth_requires_complete_separate_pair_universe(rules):
    batch = parse_claims(csv_bytes([claim_row(), claim_row(claim_id='SYN-C-B')]), 'claims.csv', 10000)
    content = b'claim_a,claim_b,is_duplicate\nSYN-C-A,SYN-C-B,true\n'
    truth = parse_truth(content, batch.claims, rules)
    assert truth[0].is_duplicate
    with pytest.raises(Rejection):
        parse_truth(b'claim_a,claim_b,is_duplicate\n', batch.claims, rules)
    with pytest.raises(Rejection):
        parse_truth(content.replace(b'SYN-C-B', b'SYN-C-A'), batch.claims, rules)


def test_boolean_date_width_and_syntax_errors_are_reported():
    with pytest.raises(Rejection):
        parse_claims(csv_bytes([claim_row(scheduled_service='yes')], COLUMNS + ['scheduled_service']), 'claims.csv', 1000)
    with pytest.raises(Rejection):
        parse_claims(csv_bytes([claim_row(service_date='20260510')]), 'claims.csv', 1000)
    header = ','.join(COLUMNS) + '\n'
    with pytest.raises(Rejection):
        parse_claims((header + 'one,two\n').encode(), 'claims.csv', 1000)
    with pytest.raises(Rejection) as caught:
        parse_claims((header + '"unterminated').encode(), 'claims.csv', 1000)
    assert caught.value.code == 'CSV_SYNTAX'
