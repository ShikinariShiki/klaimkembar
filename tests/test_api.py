import json
import secrets
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator
from openapi_spec_validator import validate

from klaimkembar.app import create_app
from klaimkembar.database import Database
from klaimkembar.settings import ROOT, Settings
from klaimkembar.validation import COLUMNS, OPTIONAL
from tests.test_validation import claim_row, csv_bytes

CONTRACT = json.loads((ROOT / 'openapi.json').read_text())


def assert_contract(response, method, path):
    schema = CONTRACT['paths'][path][method]['responses'][str(response.status_code)]['content']['application/json']['schema']
    Draft202012Validator({**schema, 'components': CONTRACT['components']}).validate(response.json())
    assert response.headers['x-request-id']
    if response.status_code >= 400:
        assert response.json()['error']['request_id'] == response.headers['x-request-id']


def demo_csv():
    rows = [claim_row(), claim_row(claim_id='SYN-C-B'),
            claim_row(claim_id='SYN-C-C', participant_token='SYN-P-B'),
            claim_row(claim_id='SYN-C-D', participant_token='SYN-P-B', service_date='2026-05-11', claim_amount='355000'),
            claim_row(claim_id='SYN-C-E', participant_token='SYN-P-C', scheduled_service='true', scheduled_date='2026-05-10'),
            claim_row(claim_id='SYN-C-F', participant_token='SYN-P-C', service_date='2026-05-11', scheduled_service='true', scheduled_date='2026-05-11')]
    return csv_bytes(rows, COLUMNS + OPTIONAL)


@pytest.fixture
def api(tmp_path):
    db = Database(tmp_path / 'claims.sqlite')
    db.migrate()
    settings = Settings(db.path, secrets.token_urlsafe(32), secrets.token_urlsafe(32), benchmark_path=tmp_path / 'benchmark.json')
    client = TestClient(create_app(settings))
    reviewer = {'Authorization': f'Bearer {settings.reviewer_token}'}
    auditor = {'Authorization': f'Bearer {settings.auditor_token}'}
    yield client, reviewer, auditor, db, settings
    client.close()


def upload(client, headers, labels=None):
    files = {'file': ('synthetic.csv', demo_csv(), 'text/csv')}
    if labels is not None:
        files['labels'] = ('labels.csv', labels, 'text/csv')
    response = client.post('/api/v1/datasets/upload', headers=headers, data={'synthetic': 'true'}, files=files)
    assert_contract(response, 'post', '/api/v1/datasets/upload')
    assert response.status_code == 201, response.text
    return response.json()['dataset_id']


def first_case(client, headers, dataset):
    response = client.get('/api/v1/cases', params={'dataset_id': dataset}, headers=headers)
    assert_contract(response, 'get', '/api/v1/cases')
    return response.json()['items'][0]


def review_payload(version=0, decision='valid'):
    return {'review_id': str(uuid4()), 'expected_version': version, 'decision': decision, 'note': 'Pemeriksaan data sintetis.', 'elapsed_seconds': 42}


def test_health_happy_path_and_malformed_method(api):
    client, *_ = api
    response = client.get('/health')
    assert response.json()['status'] == 'ok'
    assert_contract(response, 'get', '/health')
    response = client.post('/health')
    assert response.status_code == 405
    assert_contract(response, 'get', '/health')
    response = client.get('/health/unknown')
    assert response.status_code == 404
    assert_contract(response, 'get', '/health')


def test_upload_persists_atomic_dataset_and_schema(api):
    client, reviewer, _, db, _ = api
    dataset = upload(client, reviewer)
    with db.connect() as connection:
        assert connection.execute('SELECT claim_count FROM datasets WHERE id=?', (dataset,)).fetchone()[0] == 6
        assert connection.execute('SELECT COUNT(*) FROM claims WHERE dataset_id=?', (dataset,)).fetchone()[0] == 6
        assert connection.execute('SELECT COUNT(*) FROM cases WHERE protected=1 AND dataset_id=?', (dataset,)).fetchone()[0] == 1


@pytest.mark.parametrize('path', ['/api/v1/cases', '/api/v1/cases/0c89f22a-25ec-4da4-b84f-98712c71db25', '/api/v1/evaluation'])
def test_read_endpoints_reject_anonymous_and_bad_token(api, path):
    client, *_ = api
    for headers in [{}, {'Authorization': 'Bearer invalid'}]:
        response = client.get(path, headers=headers)
        assert response.status_code == 401
        operation = '/api/v1/cases/{case_id}' if '/cases/' in path else path
        assert_contract(response, 'get', operation)


@pytest.mark.parametrize('path', ['/api/v1/cases', '/api/v1/cases/not-a-uuid', '/api/v1/evaluation'])
def test_read_endpoints_reject_malformed_parameters(api, path):
    client, reviewer, *_ = api
    response = client.get(path, headers=reviewer)
    assert response.status_code == 422
    operation = '/api/v1/cases/{case_id}' if '/cases/' in path else path
    assert_contract(response, 'get', operation)


def test_upload_authorization_and_invalid_file_do_not_write(api):
    client, reviewer, auditor, db, _ = api
    for headers, status in [({}, 401), (auditor, 403)]:
        response = client.post('/api/v1/datasets/upload', headers=headers, files={'file': ('claims.csv', demo_csv())}, data={'synthetic': 'true'})
        assert response.status_code == status
        assert_contract(response, 'post', '/api/v1/datasets/upload')
    for content, name, extra in [(b'', 'claims.csv', {}), (b'invalid', 'claims.txt', {}), (demo_csv(), 'claims.csv', {'synthetic': 'false'}),
                                 (demo_csv(), 'claims.csv', {'participant_name': 'not accepted'})]:
        response = client.post('/api/v1/datasets/upload', headers=reviewer, files={'file': (name, content)}, data={'synthetic': 'true'} | extra)
        assert response.status_code == 422
        assert_contract(response, 'post', '/api/v1/datasets/upload')
    with db.connect() as connection:
        assert connection.execute('SELECT COUNT(*) FROM datasets').fetchone()[0] == 0


def test_upload_returns_validation_summary_and_reupload_works(api):
    client, reviewer, *_ = api
    malformed = csv_bytes([claim_row(service_date='2026-02-30')])
    response = client.post('/api/v1/datasets/upload', headers=reviewer, files={'file': ('claims.csv', malformed)}, data={'synthetic': 'true'})
    assert response.json()['error']['validation']['invalid_rows'] == 1
    assert response.status_code == 422
    assert_contract(response, 'post', '/api/v1/datasets/upload')
    assert upload(client, reviewer)


def test_case_filters_pagination_and_protected_exclusion(api):
    client, reviewer, auditor, *_ = api
    dataset = upload(client, reviewer)
    response = client.get('/api/v1/cases', headers=auditor, params={'dataset_id': dataset, 'page_size': 1})
    assert_contract(response, 'get', '/api/v1/cases')
    assert response.json()['total'] == 2
    assert len(response.json()['items']) == 1
    assert response.json()['queue']['remaining_cases'] == 2
    filters = [('risk_level', 'high'), ('facility_id', 'SYN-F-A'), ('reason', 'SAME_PARTICIPANT'), ('review_status', 'unreviewed'), ('sort', 'service_date'), ('sort', 'score_asc')]
    for field, value in filters:
        response = client.get('/api/v1/cases', headers=reviewer, params={'dataset_id': dataset, field: value})
        assert response.status_code == 200
        assert_contract(response, 'get', '/api/v1/cases')
        assert response.json()['items']
    protected = client.get('/api/v1/cases', headers=reviewer, params={'dataset_id': dataset, 'include_protected': 'true', 'reason': 'SCHEDULED_RECURRING_SERVICE'})
    assert protected.json()['total'] == 1
    assert protected.json()['items'][0]['assessment']['protected']
    empty = client.get('/api/v1/cases', headers=reviewer, params={'dataset_id': dataset, 'facility_id': "SYN-F-A' OR 1=1--"})
    assert empty.json()['total'] == 0
    for params in [{'page': 0}, {'page_size': 101}, {'sort': 'unknown'}, {'risk_level': 'fraud'}]:
        response = client.get('/api/v1/cases', headers=reviewer, params={'dataset_id': dataset} | params)
        assert response.status_code == 422
        assert_contract(response, 'get', '/api/v1/cases')


def test_detail_contains_comparison_timeline_reasons_and_no_get_side_effect(api):
    client, reviewer, auditor, db, _ = api
    dataset = upload(client, reviewer)
    case = first_case(client, reviewer, dataset)
    response = client.get(f"/api/v1/cases/{case['case_id']}", headers=auditor)
    assert_contract(response, 'get', '/api/v1/cases/{case_id}')
    detail = response.json()
    assert detail['version'] == 0 and detail['review_status'] == 'unreviewed'
    assert len(detail['timeline']) == 4
    assert detail['assessment']['triggered_reasons']
    assert any(field['state'] == 'different' for field in detail['fields'])
    assert detail['reviews'] == []
    with db.connect() as connection:
        assert connection.execute('SELECT COUNT(*) FROM reviews').fetchone()[0] == 0


def test_review_is_append_only_revisable_and_retry_safe(api):
    client, reviewer, _, db, _ = api
    dataset = upload(client, reviewer)
    case = first_case(client, reviewer, dataset)
    path = f"/api/v1/cases/{case['case_id']}/review"
    payload = review_payload()
    response = client.post(path, headers=reviewer, json=payload)
    assert response.status_code == 200
    assert_contract(response, 'post', '/api/v1/cases/{case_id}/review')
    assert response.json()['version'] == 1
    retry = client.post(path, headers=reviewer, json=payload)
    assert retry.json() == response.json()
    mismatch = client.post(path, headers=reviewer, json=payload | {'decision': 'needs_documents'})
    assert mismatch.status_code == 409
    assert_contract(mismatch, 'post', '/api/v1/cases/{case_id}/review')
    stale = client.post(path, headers=reviewer, json=review_payload())
    assert stale.status_code == 409
    assert_contract(stale, 'post', '/api/v1/cases/{case_id}/review')
    revision = client.post(path, headers=reviewer, json=review_payload(1, 'needs_documents'))
    assert revision.json()['version'] == 2
    detail = client.get(path.removesuffix('/review'), headers=reviewer).json()
    assert [record['decision'] for record in detail['reviews']] == ['valid', 'needs_documents']
    with db.connect() as connection:
        assert connection.execute('SELECT COUNT(*) FROM reviews WHERE case_id=?', (case['case_id'],)).fetchone()[0] == 2
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute('DELETE FROM reviews WHERE case_id=?', (case['case_id'],))
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute('UPDATE reviews SET version=9 WHERE case_id=?', (case['case_id'],))


def test_review_role_and_request_failures_do_not_change_version(api):
    client, reviewer, auditor, db, _ = api
    dataset = upload(client, reviewer)
    case = first_case(client, reviewer, dataset)
    path = f"/api/v1/cases/{case['case_id']}/review"
    for headers, status in [({}, 401), (auditor, 403)]:
        response = client.post(path, headers=headers, json=review_payload())
        assert response.status_code == status
        assert_contract(response, 'post', '/api/v1/cases/{case_id}/review')
    for changes in [{'decision': 'reject_payment'}, {'expected_version': -1}, {'review_id': 'bad'}, {'note': 'x' * 2001}, {'elapsed_seconds': -1}, {'actor': 'untrusted'}]:
        response = client.post(path, headers=reviewer, json=review_payload() | changes)
        assert response.status_code == 422
        assert_contract(response, 'post', '/api/v1/cases/{case_id}/review')
    with db.connect() as connection:
        assert connection.execute('SELECT version FROM cases WHERE id=?', (case['case_id'],)).fetchone()[0] == 0


def test_concurrent_reviews_allow_one_version_update(api):
    client, reviewer, _, db, _ = api
    dataset = upload(client, reviewer)
    case = first_case(client, reviewer, dataset)
    path = f"/api/v1/cases/{case['case_id']}/review"
    with ThreadPoolExecutor(max_workers=2) as executor:
        replies = list(executor.map(lambda _: client.post(path, headers=reviewer, json=review_payload()), range(2)))
    assert sorted(reply.status_code for reply in replies) == [200, 409]
    with db.connect() as connection:
        assert connection.execute('SELECT COUNT(*) FROM reviews WHERE case_id=?', (case['case_id'],)).fetchone()[0] == 1


def test_evaluation_without_labels_is_null_not_fake_metrics(api):
    client, reviewer, auditor, *_ = api
    dataset = upload(client, reviewer)
    response = client.get('/api/v1/evaluation', headers=auditor, params={'dataset_id': dataset})
    assert_contract(response, 'get', '/api/v1/evaluation')
    assert response.json()['dataset_methods'] is None
    assert response.json()['median_review_seconds'] is None
    assert response.json()['label_status'] == 'not_provided'


def test_evaluation_with_separate_labels_and_first_review_time(api):
    client, reviewer, auditor, *_ = api
    labels = b'claim_a,claim_b,is_duplicate\nSYN-C-A,SYN-C-B,true\nSYN-C-C,SYN-C-D,true\nSYN-C-E,SYN-C-F,false\n'
    dataset = upload(client, reviewer, labels)
    case = first_case(client, reviewer, dataset)
    client.post(f"/api/v1/cases/{case['case_id']}/review", headers=reviewer, json=review_payload())
    response = client.get('/api/v1/evaluation', headers=auditor, params={'dataset_id': dataset})
    assert_contract(response, 'get', '/api/v1/evaluation')
    actual = response.json()
    assert actual['dataset_methods']['exact_match']['recall'] == 0.5
    assert actual['dataset_methods']['similarity_with_guardrails']['recall'] == 1
    assert actual['dataset_methods']['similarity_with_guardrails']['false_positives'] == 0
    assert actual['median_review_seconds'] == 42
    assert actual['simulation']


@pytest.mark.parametrize('path', ['/api/v1/cases', '/api/v1/cases/{uuid}', '/api/v1/cases/{uuid}/review', '/api/v1/evaluation'])
def test_missing_resources_have_contract_error(api, path):
    client, reviewer, *_ = api
    path = path.replace('{uuid}', str(uuid4()))
    if path.endswith('/review'):
        response = client.post(path, headers=reviewer, json=review_payload())
        method, operation = 'post', '/api/v1/cases/{case_id}/review'
    else:
        response = client.get(path, headers=reviewer, params={'dataset_id': str(uuid4())})
        method, operation = 'get', '/api/v1/cases/{case_id}' if '/cases/' in path else path
    assert response.status_code == 404
    assert_contract(response, method, operation)


def test_cors_preflight_and_logging_never_expose_tokens_or_claims(api, caplog):
    import logging
    client, reviewer, _, _, settings = api
    caplog.set_level(logging.INFO, logger='klaimkembar')
    response = client.options('/api/v1/cases', headers={'Origin': 'http://localhost:5173', 'Access-Control-Request-Method': 'GET', 'Access-Control-Request-Headers': 'authorization'})
    assert response.status_code == 200
    assert response.headers['access-control-allow-origin'] == 'http://localhost:5173'
    rejected = client.options('/api/v1/cases', headers={'Origin': 'https://untrusted.example', 'Access-Control-Request-Method': 'GET'})
    assert 'access-control-allow-origin' not in rejected.headers
    upload(client, reviewer)
    assert settings.reviewer_token not in caplog.text
    assert 'SYN-C-A' not in caplog.text
    assert 'request_id' in caplog.text


def test_contract_lints_matches_runtime_routes_and_response_models(api):
    from fastapi.routing import APIRoute
    client, *_ = api
    validate(CONTRACT)
    assert client.get('/openapi.json').json() == CONTRACT
    declared = {(method.lower(), route.path) for route in client.app.routes if isinstance(route, APIRoute) for method in route.methods}
    expected = {(method, path) for path, ops in CONTRACT['paths'].items() for method in ops}
    assert declared == expected
    for route in client.app.routes:
        if isinstance(route, APIRoute):
            model = route.response_model
            actual = model.model_json_schema(ref_template='#/components/schemas/{model}')
            actual.pop('$defs', None)
            assert CONTRACT['components']['schemas'][model.__name__] == actual


def test_storage_failure_uses_safe_503_envelope(api):
    client, reviewer, _, db, _ = api
    dataset = upload(client, reviewer)
    with db.connect() as connection:
        connection.execute('ALTER TABLE cases RENAME TO interrupted_cases')
    response = client.get('/api/v1/cases', headers=reviewer, params={'dataset_id': dataset})
    assert response.status_code == 503
    assert_contract(response, 'get', '/api/v1/cases')
    assert 'interrupted_cases' not in response.text


def test_corrupt_internal_record_returns_redacted_500_with_cors(api, caplog):
    client, reviewer, _, db, _ = api
    dataset = upload(client, reviewer)
    case = first_case(client, reviewer, dataset)
    with db.connect() as connection:
        connection.execute("UPDATE cases SET payload='{}' WHERE id=?", (case['case_id'],))
    response = client.get(f"/api/v1/cases/{case['case_id']}", headers=reviewer | {'Origin': 'http://localhost:5173'})
    assert response.status_code == 500
    assert_contract(response, 'get', '/api/v1/cases/{case_id}')
    assert response.headers['access-control-allow-origin'] == 'http://localhost:5173'
    assert 'ValidationError' not in response.text


def test_upload_size_limit_and_label_failure_are_atomic(api):
    client, reviewer, _, db, _ = api
    response = client.post('/api/v1/datasets/upload', headers=reviewer, data={'synthetic': 'true'}, files={'file': ('claims.csv', b'x' * (5 * 1024 * 1024 + 1))})
    assert response.status_code == 413
    assert_contract(response, 'post', '/api/v1/datasets/upload')
    response = client.post('/api/v1/datasets/upload', headers=reviewer, data={'synthetic': 'true'}, files={'file': ('claims.csv', demo_csv()), 'labels': ('labels.csv', b'claim_a,claim_b,is_duplicate\n')})
    assert response.status_code == 422
    assert_contract(response, 'post', '/api/v1/datasets/upload')
    with db.connect() as connection:
        assert connection.execute('SELECT COUNT(*) FROM datasets').fetchone()[0] == 0


def test_empty_queue_and_zero_pair_label_file_have_defined_evaluation(api):
    client, reviewer, _, _, _ = api
    response = client.post('/api/v1/datasets/upload', headers=reviewer, data={'synthetic': 'true'}, files={
        'file': ('claims.csv', csv_bytes([claim_row()])), 'labels': ('labels.csv', b'claim_a,claim_b,is_duplicate\n')})
    assert response.status_code == 201
    dataset = response.json()['dataset_id']
    queue = client.get('/api/v1/cases', headers=reviewer, params={'dataset_id': dataset})
    assert queue.json()['queue']['remaining_cases'] == 0
    assert queue.json()['queue']['next_case_id'] is None
    evaluation = client.get('/api/v1/evaluation', headers=reviewer, params={'dataset_id': dataset})
    assert evaluation.json()['label_status'] == 'available'
    assert evaluation.json()['dataset_methods']['exact_match']['recall'] is None
    assert_contract(evaluation, 'get', '/api/v1/evaluation')


def test_benchmark_hash_mismatch_is_not_silently_compared(api):
    from klaimkembar.evaluation import benchmark
    from klaimkembar.settings import Rules
    client, reviewer, _, _, settings = api
    dataset = upload(client, reviewer)
    report = benchmark(Rules.load(ROOT / 'rules.json'), [104], 50)
    settings.benchmark_path.write_text(report.model_dump_json())
    response = client.get('/api/v1/evaluation', headers=reviewer, params={'dataset_id': dataset})
    assert response.status_code == 200
    assert_contract(response, 'get', '/api/v1/evaluation')
    report.rules_hash = 'mismatching-version'
    settings.benchmark_path.write_text(report.model_dump_json())
    response = client.get('/api/v1/evaluation', headers=reviewer, params={'dataset_id': dataset})
    assert response.status_code == 409
    assert response.json()['error']['code'] == 'BENCHMARK_VERSION_MISMATCH'
    assert_contract(response, 'get', '/api/v1/evaluation')


def test_same_review_id_concurrent_retry_records_one_audit_event(api):
    client, reviewer, _, db, _ = api
    dataset = upload(client, reviewer)
    case = first_case(client, reviewer, dataset)
    path = f"/api/v1/cases/{case['case_id']}/review"
    payload = review_payload()
    with ThreadPoolExecutor(max_workers=2) as executor:
        replies = list(executor.map(lambda _: client.post(path, headers=reviewer, json=payload), range(2)))
    assert [reply.status_code for reply in replies] == [200, 200]
    assert replies[0].json() == replies[1].json()
    with db.connect() as connection:
        assert connection.execute('SELECT COUNT(*) FROM reviews').fetchone()[0] == 1
