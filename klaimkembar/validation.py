import csv
import io
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from itertools import combinations

from klaimkembar.errors import Rejection
from klaimkembar.models import Claim, FieldIssue, TruthPair, ValidationSummary
from klaimkembar.settings import Rules

COLUMNS = ['claim_id', 'participant_token', 'facility_id', 'service_date', 'submission_date',
           'diagnosis_group', 'procedure_group', 'claim_amount', 'claim_status', 'original_claim_id']
OPTIONAL = ['facility_group', 'episode_id', 'visit_id', 'scheduled_service', 'scheduled_date']
DATE_PATTERN = re.compile(r'^\d{4}-\d{2}-\d{2}$')


@dataclass
class ParsedClaims:
    claims: list[Claim]
    summary: ValidationSummary


def calendar_date(value: str) -> date:
    if not DATE_PATTERN.fullmatch(value):
        raise ValueError('date must be YYYY-MM-DD')
    return date.fromisoformat(value)


def _reader(content: bytes) -> csv.DictReader[str]:
    try:
        decoded = content.decode('utf-8-sig')
    except UnicodeDecodeError as exc:
        raise Rejection(422, 'FILE_ENCODING', 'Gunakan CSV dengan encoding UTF-8.') from exc
    if not decoded.strip():
        raise Rejection(422, 'FILE_EMPTY', 'File kosong. Pilih CSV yang berisi data klaim.')
    return csv.DictReader(io.StringIO(decoded, newline=''), strict=True)


def eligible_pairs(claims: list[Claim], limit: int) -> set[tuple[str, str]]:
    participants: dict[str, list[str]] = defaultdict(list)
    for claim in claims:
        participants[claim.participant_token].append(claim.claim_id)
    total = sum(len(ids) * (len(ids) - 1) // 2 for ids in participants.values())
    if total > limit:
        raise Rejection(413, 'PAIR_LIMIT', 'Terlalu banyak pasangan per peserta. Pecah dataset menjadi file lebih kecil.')
    return {(min(a, b), max(a, b)) for ids in participants.values() for a, b in combinations(ids, 2)}


def parse_claims(content: bytes, filename: str, max_rows: int) -> ParsedClaims:
    if not filename.lower().endswith('.csv'):
        raise Rejection(422, 'FILE_FORMAT', 'Format file tidak sesuai. Pilih file berformat .csv.')
    reader = _reader(content)
    try:
        header = reader.fieldnames or []
    except csv.Error as exc:
        raise Rejection(422, 'CSV_SYNTAX', 'Header CSV tidak dapat dibaca. Periksa pemisah koma dan tanda kutip.') from exc
    if len(header) != len(set(header)):
        raise Rejection(422, 'DUPLICATE_COLUMNS', 'Header CSV berisi kolom ganda.')
    missing = [field for field in COLUMNS if field not in header]
    if missing:
        missing_issues = [FieldIssue(field=field, code='MISSING_COLUMN', message='Tambahkan kolom wajib pada header CSV.') for field in missing]
        summary = ValidationSummary(total_rows=0, valid_rows=0, invalid_rows=0, incomplete_rows=0,
                                    missing_columns=missing, issues=missing_issues, issues_total=len(missing_issues))
        raise Rejection(422, 'MISSING_COLUMNS', 'Kolom wajib belum lengkap.', missing_issues, summary)
    extra = set(header) - set(COLUMNS + OPTIONAL)
    if extra:
        raise Rejection(422, 'UNSUPPORTED_COLUMNS', 'Hapus kolom di luar kontrak. Jangan unggah identitas pribadi.',
                        [FieldIssue(field='header', code='UNSUPPORTED_COLUMN', message='Gunakan hanya kolom dalam template CSV.')])
    issues: list[FieldIssue] = []
    issue_count = 0
    invalid_rows: set[int] = set()
    incomplete_rows: set[int] = set()
    accepted: list[tuple[int, Claim]] = []
    claim_ids: set[str] = set()
    row_values: set[tuple[str, ...]] = set()
    total = 0

    def issue(row: int, field: str, code: str, message: str, fatal: bool = True) -> None:
        nonlocal issue_count
        issue_count += 1
        if len(issues) < 100:
            issues.append(FieldIssue(row=row, field=field, code=code, message=message))
        if fatal:
            invalid_rows.add(row)
        else:
            incomplete_rows.add(row)

    try:
        for row_no, raw in enumerate(reader, 2):
            total += 1
            if total > max_rows:
                raise Rejection(413, 'ROW_LIMIT', f'Maksimal {max_rows} baris klaim per unggahan.')
            if None in raw or any(value is None for value in raw.values()):
                issue(row_no, 'row', 'CSV_WIDTH', 'Jumlah nilai harus sesuai dengan jumlah kolom.')
                continue
            values = {field: (raw.get(field) or '').strip() for field in COLUMNS + OPTIONAL}
            signature = tuple(values[field] for field in COLUMNS + OPTIONAL)
            if signature in row_values:
                issue(row_no, 'row', 'DUPLICATE_ROW', 'Baris ini berulang. Hapus duplikasi baris.')
            row_values.add(signature)
            if values['claim_id'] in claim_ids:
                issue(row_no, 'claim_id', 'DUPLICATE_ID', 'ID klaim harus unik dalam satu dataset.')
            claim_ids.add(values['claim_id'])
            for field, value in values.items():
                if len(value) > 100 or '\x00' in value:
                    issue(row_no, field, 'FIELD_LENGTH', 'Gunakan maksimal 100 karakter tanpa karakter NUL.')
            for field in ['claim_id', 'participant_token', 'facility_id']:
                if not values[field]:
                    issue(row_no, field, 'REQUIRED', 'Isi kolom wajib ini.')
                elif not values[field].startswith('SYN-'):
                    issue(row_no, field, 'SYNTHETIC_ONLY', 'Gunakan ID sintetis dengan awalan SYN-. Data asli dilarang.')
            for field in ['original_claim_id', 'facility_group', 'episode_id', 'visit_id']:
                if values[field] and not values[field].startswith('SYN-'):
                    issue(row_no, field, 'SYNTHETIC_ONLY', 'Gunakan ID sintetis dengan awalan SYN-.')
            for field in ['service_date', 'submission_date', 'scheduled_date']:
                if field == 'scheduled_date' and not values[field]:
                    continue
                try:
                    calendar_date(values[field])
                except ValueError:
                    issue(row_no, field, 'INVALID_DATE', 'Isi tanggal yang valid dengan format YYYY-MM-DD.')
            try:
                amount = Decimal(values['claim_amount'])
                if not amount.is_finite() or amount < 0 or amount > Decimal('1000000000000') or amount != amount.quantize(Decimal('0.01')):
                    raise ValueError('invalid amount')
                values['claim_amount'] = f'{amount:.2f}'
            except (InvalidOperation, ValueError):
                issue(row_no, 'claim_amount', 'INVALID_AMOUNT', 'Isi nominal 0 sampai 1000000000000 dengan maksimal dua angka desimal.')
            if values['claim_status'] not in ['active', 'cancelled', 'corrected']:
                issue(row_no, 'claim_status', 'INVALID_STATUS', 'Pilih active, cancelled, atau corrected.')
            scheduled = values['scheduled_service'].lower()
            if scheduled not in ['', 'true', 'false']:
                issue(row_no, 'scheduled_service', 'INVALID_BOOLEAN', 'Gunakan true atau false.')
            for field in ['diagnosis_group', 'procedure_group']:
                if not values[field]:
                    issue(row_no, field, 'MISSING_INFORMATION', 'Data belum tersedia. Petugas perlu memverifikasi.', fatal=False)
            if row_no not in invalid_rows:
                fields: dict[str, str | bool] = dict(values)
                fields['scheduled_service'] = scheduled == 'true'
                accepted.append((row_no, Claim.model_validate(fields)))
    except csv.Error as exc:
        raise Rejection(422, 'CSV_SYNTAX', 'CSV tidak dapat dibaca. Periksa pemisah koma dan tanda kutip.') from exc
    if not total:
        raise Rejection(422, 'FILE_EMPTY', 'File kosong. Pilih CSV yang berisi data klaim.')
    known_ids = {claim.claim_id for _, claim in accepted}
    for row_no, claim in accepted:
        original = claim.original_claim_id
        if (claim.claim_status == 'corrected' and not original) or (original and (original not in known_ids or original == claim.claim_id)):
            issue(row_no, 'original_claim_id', 'INVALID_CORRECTION_LINK', 'Koreksi harus merujuk klaim lain yang tersedia dalam dataset.')
    summary = ValidationSummary(total_rows=total, valid_rows=total - len(invalid_rows), invalid_rows=len(invalid_rows),
                                incomplete_rows=len(incomplete_rows - invalid_rows), missing_columns=[], issues=issues, issues_total=issue_count)
    if invalid_rows:
        raise Rejection(422, 'INVALID_ROWS', 'Perbaiki baris bermasalah lalu unggah ulang. Tidak ada klaim yang disimpan.', issues, summary)
    return ParsedClaims([claim for _, claim in accepted], summary)


def parse_truth(content: bytes, claims: list[Claim], rules: Rules) -> list[TruthPair]:
    universe = eligible_pairs(claims, rules.maximum_eligible_pairs)
    reader = _reader(content)
    if reader.fieldnames != ['claim_a', 'claim_b', 'is_duplicate']:
        raise Rejection(422, 'LABEL_COLUMNS', 'Label harus memiliki kolom claim_a,claim_b,is_duplicate.')
    truth: dict[tuple[str, str], TruthPair] = {}
    try:
        for raw in reader:
            if None in raw or any(value is None for value in raw.values()):
                raise Rejection(422, 'LABEL_ROW', 'Jumlah nilai pada label tidak sesuai header.')
            a, b = raw['claim_a'].strip(), raw['claim_b'].strip()
            pair = (min(a, b), max(a, b))
            label = raw['is_duplicate'].strip().lower()
            if pair not in universe or pair in truth or label not in ['true', 'false']:
                raise Rejection(422, 'LABEL_ROW', 'Label harus berupa pasangan unik peserta yang sama dan nilai true/false.')
            truth[pair] = TruthPair(claim_a=pair[0], claim_b=pair[1], is_duplicate=label == 'true')
    except csv.Error as exc:
        raise Rejection(422, 'LABEL_SYNTAX', 'CSV label tidak dapat dibaca.') from exc
    if set(truth) != universe:
        raise Rejection(422, 'LABEL_INCOMPLETE', 'Label harus mencakup seluruh pasangan peserta yang sama, termasuk pasangan normal.')
    return list(truth.values())
