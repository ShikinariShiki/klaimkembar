import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Literal, cast
from uuid import uuid4

from klaimkembar.database import Database
from klaimkembar.engine import detect
from klaimkembar.errors import Rejection
from klaimkembar.evaluation import DEFINITIONS, evaluate
from klaimkembar.models import (
    BenchmarkReport,
    CaseDetail,
    CasesResponse,
    CaseSummary,
    Claim,
    ComparedField,
    EvaluationResponse,
    PairAssessment,
    QueueSummary,
    ReviewRecord,
    ReviewRequest,
    ReviewResponse,
    TimelineEvent,
    TruthPair,
    UploadResponse,
)
from klaimkembar.settings import Rules, Settings
from klaimkembar.validation import COLUMNS, eligible_pairs, parse_claims, parse_truth


@dataclass(frozen=True)
class Actor:
    name: str
    role: str


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


class ClaimsWorkflow:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.rules = Rules.load(settings.rules_path)
        self.db = Database(settings.db_path)
        self.db.verify_schema()

    def _dataset(self, connection: sqlite3.Connection, dataset_id: str) -> sqlite3.Row:
        row = connection.execute('SELECT * FROM datasets WHERE id=?', (dataset_id,)).fetchone()
        if row is None:
            raise Rejection(404, 'DATASET_NOT_FOUND', 'Dataset tidak ditemukan. Unggah data terlebih dahulu.')
        return cast(sqlite3.Row, row)

    def _case_row(self, connection: sqlite3.Connection, case_id: str) -> sqlite3.Row:
        row = connection.execute('SELECT * FROM cases WHERE id=?', (case_id,)).fetchone()
        if row is None:
            raise Rejection(404, 'CASE_NOT_FOUND', 'Kasus tidak ditemukan. Kembali ke antrean.')
        return cast(sqlite3.Row, row)

    def _rules_for(self, row: sqlite3.Row) -> Rules:
        return Rules(**json.loads(row['rules_json']), fingerprint=row['rules_hash'], snapshot=row['rules_json'])

    def _queue(self, connection: sqlite3.Connection, dataset_id: str, rules: Rules) -> QueueSummary:
        visible = "dataset_id=? AND protected=0 AND (risk_score>=? OR json_extract(payload,'$.needs_data')=1)"
        rows = connection.execute(f'SELECT id,review_status FROM cases WHERE {visible} ORDER BY risk_score DESC,id',
                                  (dataset_id, rules.queue_threshold)).fetchall()
        pending = [row['id'] for row in rows if row['review_status'] == 'unreviewed']
        return QueueSummary(total_cases=len(rows), reviewed_cases=len(rows) - len(pending),
                            remaining_cases=len(pending), next_case_id=pending[0] if pending else None)

    def upload(self, filename: str, content: bytes, synthetic: bool, labels: bytes | None) -> UploadResponse:
        if not synthetic:
            raise Rejection(422, 'SYNTHETIC_DECLARATION', 'Prototype hanya menerima data sintetis. Nyatakan synthetic=true.')
        if len(content) > self.settings.max_upload_bytes or (labels is not None and len(labels) > self.settings.max_upload_bytes):
            raise Rejection(413, 'FILE_TOO_LARGE', 'Maksimal 5 MiB per file. Pecah dataset menjadi file lebih kecil.')
        batch = parse_claims(content, filename, self.settings.max_rows)
        eligible_pairs(batch.claims, self.rules.maximum_eligible_pairs)
        pairs = detect(batch.claims, self.rules)
        # No label reaches detect; separate parsing and storage are deliberate.
        truth = parse_truth(labels, batch.claims, self.rules) if labels is not None else []
        dataset_id = str(uuid4())
        created_at = timestamp()
        display_name = Path(filename.replace('\\', '/')).name[:150]
        with self.db.connect() as connection:
            connection.execute('INSERT INTO datasets VALUES (?,?,?,?,?,?,?,?,?)',
                               (dataset_id, display_name, len(content), created_at, len(batch.claims),
                                batch.summary.model_dump_json(), self.rules.snapshot, self.rules.fingerprint, int(labels is not None)))
            connection.executemany('INSERT INTO claims VALUES (?,?,?,?,?,?)',
                                   [(dataset_id, claim.claim_id, claim.participant_token, claim.facility_id,
                                     claim.service_date, claim.model_dump_json()) for claim in batch.claims])
            connection.executemany('INSERT INTO cases (id,dataset_id,claim_a,claim_b,payload,protected,risk_score) VALUES (?,?,?,?,?,?,?)',
                                   [(str(uuid4()), dataset_id, pair.claim_a, pair.claim_b, pair.model_dump_json(),
                                     int(pair.protected), pair.risk_score) for pair in pairs])
            connection.executemany('INSERT INTO truth_pairs VALUES (?,?,?,?)',
                                   [(dataset_id, pair.claim_a, pair.claim_b, int(pair.is_duplicate)) for pair in truth])
            queue = self._queue(connection, dataset_id, self.rules)
        return UploadResponse(dataset_id=dataset_id, filename=display_name, size_bytes=len(content), status='ready',
                              created_at=created_at, validation=batch.summary, case_count=queue.total_cases,
                              protected_pair_count=sum(pair.protected for pair in pairs), rules_version=self.rules.version,
                              rules_hash=self.rules.fingerprint, simulation=True)

    def _summary(self, connection: sqlite3.Connection, row: sqlite3.Row) -> CaseSummary:
        claims = {claim['claim_id']: Claim.model_validate_json(claim['payload']) for claim in connection.execute(
            'SELECT claim_id,payload FROM claims WHERE dataset_id=? AND claim_id IN (?,?)',
            (row['dataset_id'], row['claim_a'], row['claim_b']))}
        return CaseSummary(case_id=row['id'], dataset_id=row['dataset_id'], claim_a=claims[row['claim_a']],
                           claim_b=claims[row['claim_b']], assessment=PairAssessment.model_validate_json(row['payload']),
                           review_status=row['review_status'], version=row['version'])

    def cases(self, dataset_id: str, page: int, page_size: int, risk_level: str | None, review_status: str | None,
              facility_id: str | None, reason: str | None, order: str, include_protected: bool) -> CasesResponse:
        with self.db.connect() as connection:
            dataset = self._dataset(connection, dataset_id)
            rules = self._rules_for(dataset)
            clauses = ['c.dataset_id=?']
            parameters: list[str | float | int] = [dataset_id]
            if include_protected:
                clauses.append("(c.risk_score>=? OR json_extract(c.payload,'$.needs_data')=1 OR c.protected=1)")
            else:
                clauses.extend(['c.protected=0', "(c.risk_score>=? OR json_extract(c.payload,'$.needs_data')=1)"])
            parameters.append(rules.queue_threshold)
            for value, expression in [(risk_level, "json_extract(c.payload,'$.risk_level')=?"), (review_status, 'c.review_status=?'),
                                      (facility_id, '(a.facility_id=? OR b.facility_id=?)')]:
                if value is not None:
                    clauses.append(expression)
                    parameters.append(value)
                    if value == facility_id and expression.startswith('(a.'):
                        parameters.append(value)
            if reason is not None:
                clauses.append("(EXISTS (SELECT 1 FROM json_each(c.payload,'$.triggered_reasons') WHERE value=?) OR EXISTS (SELECT 1 FROM json_each(c.payload,'$.risk_reducers') WHERE json_extract(value,'$.code')=?))")
                parameters.extend([reason, reason])
            source = ' FROM cases c JOIN claims a ON a.dataset_id=c.dataset_id AND a.claim_id=c.claim_a JOIN claims b ON b.dataset_id=c.dataset_id AND b.claim_id=c.claim_b WHERE ' + ' AND '.join(clauses)
            orders = {'score_desc': 'c.risk_score DESC,c.id', 'score_asc': 'c.risk_score ASC,c.id', 'service_date': 'a.service_date,c.id'}
            total = connection.execute('SELECT COUNT(*)' + source, parameters).fetchone()[0]
            rows = connection.execute('SELECT c.*' + source + ' ORDER BY ' + orders[order] + ' LIMIT ? OFFSET ?',
                                      parameters + [page_size, (page - 1) * page_size]).fetchall()
            return CasesResponse(items=[self._summary(connection, row) for row in rows], total=total, page=page,
                                 page_size=page_size, queue=self._queue(connection, dataset_id, rules))

    def detail(self, case_id: str) -> CaseDetail:
        with self.db.connect() as connection:
            row = self._case_row(connection, case_id)
            dataset = self._dataset(connection, row['dataset_id'])
            summary = self._summary(connection, row)
            left, right = summary.claim_a, summary.claim_b
            compared = []
            for field in COLUMNS:
                a, b = str(getattr(left, field)), str(getattr(right, field))
                state: Literal['same', 'different', 'missing'] = 'missing' if field in ['diagnosis_group', 'procedure_group'] and (not a or not b) else 'same' if a == b else 'different'
                compared.append(ComparedField(field=field, claim_a=a, claim_b=b, state=state))
            timeline = [TimelineEvent(date=claim.service_date, event='service', claim_id=claim.claim_id) for claim in [left, right]]
            timeline += [TimelineEvent(date=claim.submission_date, event='submission', claim_id=claim.claim_id) for claim in [left, right]]
            reviews = [ReviewRecord.model_validate_json(review[0]) for review in connection.execute(
                'SELECT payload FROM reviews WHERE case_id=? ORDER BY version', (case_id,))]
            return CaseDetail(**summary.model_dump(), fields=compared, timeline=sorted(timeline, key=lambda event: (event.date, event.event, event.claim_id)),
                              reviews=reviews, queue=self._queue(connection, row['dataset_id'], self._rules_for(dataset)),
                              advisory='Skor adalah prioritas pemeriksaan, bukan vonis kecurangan. Valid bukan persetujuan pembayaran.')

    def review(self, case_id: str, request: ReviewRequest, actor: Actor) -> ReviewResponse:
        with self.db.connect() as connection:
            connection.execute('BEGIN IMMEDIATE')
            row = self._case_row(connection, case_id)
            canonical_request = request.model_dump_json()
            prior = connection.execute('SELECT request_json,response_json,payload FROM reviews WHERE case_id=? AND review_id=?',
                                       (case_id, request.review_id)).fetchone()
            if prior is not None:
                saved = ReviewRecord.model_validate_json(prior['payload'])
                if prior['request_json'] != canonical_request or saved.actor != actor.name:
                    raise Rejection(409, 'REVIEW_ID_REUSED', 'ID keputusan sudah dipakai untuk payload atau petugas berbeda.')
                return ReviewResponse.model_validate_json(prior['response_json'])
            if row['version'] != request.expected_version:
                raise Rejection(409, 'STALE_REVIEW', 'Keputusan telah berubah. Muat ulang detail kasus sebelum menyimpan.')
            dataset = self._dataset(connection, row['dataset_id'])
            rules = self._rules_for(dataset)
            version = row['version'] + 1
            record = ReviewRecord(review_id=request.review_id, actor=actor.name, decision=request.decision,
                                  note=request.note, reviewed_at=timestamp(), elapsed_seconds=request.elapsed_seconds,
                                  rules_version=rules.version, rules_hash=rules.fingerprint, version=version)
            updated = connection.execute('UPDATE cases SET review_status=?,version=? WHERE id=? AND version=?',
                                         (request.decision, version, case_id, request.expected_version)).rowcount
            if updated != 1:
                raise Rejection(409, 'STALE_REVIEW', 'Keputusan telah berubah. Muat ulang detail kasus.')
            response = ReviewResponse(case_id=case_id, review_status=request.decision, version=version, review=record,
                                      queue=self._queue(connection, row['dataset_id'], rules))
            connection.execute('INSERT INTO reviews VALUES (?,?,?,?,?,?)',
                               (case_id, request.review_id, canonical_request, response.model_dump_json(), record.model_dump_json(), version))
            return response

    def evaluation(self, dataset_id: str) -> EvaluationResponse:
        with self.db.connect() as connection:
            dataset = self._dataset(connection, dataset_id)
            rules = self._rules_for(dataset)
            truth = [TruthPair(claim_a=row['claim_a'], claim_b=row['claim_b'], is_duplicate=bool(row['is_duplicate']))
                     for row in connection.execute('SELECT * FROM truth_pairs WHERE dataset_id=?', (dataset_id,))]
            claims = [Claim.model_validate_json(row[0]) for row in connection.execute('SELECT payload FROM claims WHERE dataset_id=?', (dataset_id,))]
            pairs = [PairAssessment.model_validate_json(row[0]) for row in connection.execute('SELECT payload FROM cases WHERE dataset_id=?', (dataset_id,))]
            first_reviews = [ReviewRecord.model_validate_json(row[0]) for row in connection.execute(
                'SELECT r.payload FROM reviews r JOIN cases c ON c.id=r.case_id WHERE c.dataset_id=? AND r.version=1', (dataset_id,))]
            durations = [record.elapsed_seconds for record in first_reviews if record.elapsed_seconds is not None]
            queue = self._queue(connection, dataset_id, rules)
        report = None
        if self.settings.benchmark_path.exists():
            report = BenchmarkReport.model_validate_json(self.settings.benchmark_path.read_text())
            if report.rules_hash != rules.fingerprint:
                raise Rejection(409, 'BENCHMARK_VERSION_MISMATCH', 'Versi benchmark berbeda dari dataset. Gunakan benchmark dengan hash aturan yang sama.')
        return EvaluationResponse(dataset_id=dataset_id, simulation=True, label_status='available' if dataset['labels_available'] else 'not_provided',
                                  dataset_methods=evaluate(claims, truth, pairs, rules) if dataset['labels_available'] else None, benchmark=report,
                                  queue=queue, median_review_seconds=median(durations) if durations else None,
                                  review_time_source='Laporan elapsed_seconds klien pada keputusan pertama, bukan hasil usability test.',
                                  rules_version=rules.version, rules_hash=rules.fingerprint, metric_definitions=DEFINITIONS)
