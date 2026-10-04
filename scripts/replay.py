import argparse
import json
import os
import sqlite3
from pathlib import Path
from uuid import uuid4

import httpx
from jsonschema import Draft202012Validator

from klaimkembar.settings import ROOT

CONTRACT = json.loads((ROOT / 'openapi.json').read_text())
WIRE = {}


def checked(client, method, path, operation=None, expected=200, **kwargs):
    response = client.request(method, path, **kwargs)
    assert response.status_code == expected, (method, path, response.status_code, response.text[:200])
    schema = CONTRACT['paths'][operation or path][method.lower()]['responses'][str(expected)]['content']['application/json']['schema']
    Draft202012Validator({**schema, 'components': CONTRACT['components']}).validate(response.json())
    key = f'{method} {operation or path} {expected}'
    if key not in WIRE:
        WIRE[key] = response.json()
    print(f'{method} {operation or path}: {expected}; response contract PASS')
    return response.json()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base-url', default='http://127.0.0.1:8000')
    args = parser.parse_args()
    token = os.environ.get('REVIEWER_TOKEN')
    if not token:
        raise SystemExit('Load .env before replay; token values must not be printed.')
    with httpx.Client(base_url=args.base_url, timeout=60) as client:
        checked(client, 'GET', '/health')
        client.headers['Authorization'] = f'Bearer {token}'
        invalid = checked(client, 'POST', '/api/v1/datasets/upload', expected=422,
                          data={'synthetic': 'true'}, files={'file': ('invalid.txt', b'not a CSV')})
        assert invalid['error']['code'] == 'FILE_FORMAT'
        with (ROOT / 'examples/claims.csv').open('rb') as claims, (ROOT / 'examples/labels.csv').open('rb') as labels:
            upload = checked(client, 'POST', '/api/v1/datasets/upload', expected=201, data={'synthetic': 'true'},
                             files={'file': ('claims.csv', claims, 'text/csv'), 'labels': ('labels.csv', labels, 'text/csv')})
        dataset_id = upload['dataset_id']
        db_path = Path(os.environ.get('DATABASE_PATH', 'var/klaimkembar.sqlite'))
        with sqlite3.connect(db_path) as database:
            assert database.execute('SELECT COUNT(*) FROM claims WHERE dataset_id=?', (dataset_id,)).fetchone()[0] == 5000
        exact = checked(client, 'GET', '/api/v1/cases', params={'dataset_id': dataset_id, 'reason': 'SAME_PARTICIPANT', 'page_size': 100})
        assert exact['items']
        case = next(case for case in exact['items'] if case['assessment']['baseline_match'])
        detail = checked(client, 'GET', f"/api/v1/cases/{case['case_id']}", '/api/v1/cases/{case_id}')
        assert detail['timeline'] and detail['assessment']['contributions']
        protected = checked(client, 'GET', '/api/v1/cases', params={'dataset_id': dataset_id, 'include_protected': 'true', 'reason': 'SCHEDULED_RECURRING_SERVICE'})
        assert protected['items'] and all(case['assessment']['protected'] for case in protected['items'])
        path = f"/api/v1/cases/{case['case_id']}/review"
        payload = {'review_id': str(uuid4()), 'expected_version': 0, 'decision': 'valid', 'note': 'Demo sintetis.', 'elapsed_seconds': 45}
        reviewed = checked(client, 'POST', path, '/api/v1/cases/{case_id}/review', json=payload)
        retry = checked(client, 'POST', path, '/api/v1/cases/{case_id}/review', json=payload)
        assert reviewed == retry
        stale = checked(client, 'POST', path, '/api/v1/cases/{case_id}/review', expected=409,
                        json=payload | {'review_id': str(uuid4())})
        assert stale['error']['code'] == 'STALE_REVIEW'
        changed = checked(client, 'POST', path, '/api/v1/cases/{case_id}/review', json=payload | {'review_id': str(uuid4()), 'expected_version': 1, 'decision': 'further_review'})
        assert changed['version'] == 2
        with sqlite3.connect(db_path) as database:
            assert database.execute('SELECT COUNT(*) FROM reviews WHERE case_id=?', (case['case_id'],)).fetchone()[0] == 2
        # Replay the completion loop with a small copy of real generated claim rows.
        import csv
        import io

        from klaimkembar.synthetic import generate
        from klaimkembar.validation import COLUMNS, OPTIONAL
        small_claims, small_truth = generate(211, 20)
        stream = io.StringIO()
        writer = csv.DictWriter(stream, fieldnames=COLUMNS + OPTIONAL)
        writer.writeheader()
        for claim in small_claims:
            row = claim.model_dump()
            row['scheduled_service'] = str(row['scheduled_service']).lower()
            writer.writerow(row)
        small = checked(client, 'POST', '/api/v1/datasets/upload', expected=201, data={'synthetic': 'true'},
                        files={'file': ('small.csv', stream.getvalue().encode())})
        small_id = small['dataset_id']
        queue = checked(client, 'GET', '/api/v1/cases', params={'dataset_id': small_id})
        for pending in queue['items']:
            checked(client, 'GET', f"/api/v1/cases/{pending['case_id']}", '/api/v1/cases/{case_id}')
            payload = {'review_id': str(uuid4()), 'expected_version': 0, 'decision': 'needs_documents', 'note': 'Lengkapi bukti sintetis.'}
            checked(client, 'POST', f"/api/v1/cases/{pending['case_id']}/review", '/api/v1/cases/{case_id}/review', json=payload)
        completed = checked(client, 'GET', '/api/v1/cases', params={'dataset_id': small_id})
        assert completed['queue']['remaining_cases'] == 0
        assert completed['queue']['next_case_id'] is None
        with sqlite3.connect(db_path) as database:
            assert database.execute('SELECT COUNT(*) FROM reviews r JOIN cases c ON c.id=r.case_id WHERE c.dataset_id=?', (small_id,)).fetchone()[0] == queue['queue']['total_cases']
        checked(client, 'GET', '/api/v1/evaluation', params={'dataset_id': small_id})
        evaluation = checked(client, 'GET', '/api/v1/evaluation', params={'dataset_id': dataset_id})
        assert evaluation['dataset_methods'] and len(evaluation['benchmark']['seeds']) == 5
        assert evaluation['median_review_seconds'] == 45
        assert evaluation['simulation']
        (ROOT / 'examples/api_responses.json').write_text(json.dumps(WIRE, ensure_ascii=False, indent=2) + '\n')
        print('F3 replay PASS: validation failure/reupload, queue/detail/decision, revision/retry, remaining loop, completion/evaluation; DB assertions PASS.')


if __name__ == '__main__':
    main()
