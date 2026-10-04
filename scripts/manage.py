import argparse
import csv
import hashlib
import json
import os
import secrets
from pathlib import Path

from klaimkembar.database import Database
from klaimkembar.evaluation import benchmark
from klaimkembar.settings import ROOT, Rules
from klaimkembar.synthetic import generate
from klaimkembar.validation import COLUMNS, OPTIONAL


def init_environment():
    path = Path('.env')
    if path.exists():
        raise SystemExit('.env already exists; keep the existing local credentials.')
    values = f'DATABASE_PATH=var/klaimkembar.sqlite\nREVIEWER_TOKEN={secrets.token_urlsafe(32)}\nAUDITOR_TOKEN={secrets.token_urlsafe(32)}\nCORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173\nRULES_PATH=rules.json\nBENCHMARK_PATH=examples/benchmark.json\n'
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'w') as stream:
        stream.write(values)
    print('Created local .env mode 0600; credential values are not printed.')


def create_seed(seed, count):
    claims, truth = generate(seed, count)
    directory = ROOT / 'examples'
    directory.mkdir(exist_ok=True)
    with (directory / 'claims.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=COLUMNS + OPTIONAL)
        writer.writeheader()
        for claim in claims:
            fields = claim.model_dump()
            fields['scheduled_service'] = str(claim.scheduled_service).lower()
            writer.writerow(fields)
    with (directory / 'labels.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=['claim_a', 'claim_b', 'is_duplicate'])
        writer.writeheader()
        for pair in truth:
            fields = pair.model_dump()
            fields['is_duplicate'] = str(pair.is_duplicate).lower()
            writer.writerow(fields)
    print(f'Synthetic CSV written: {len(claims)} claims, {len(truth)} labelled pairs, seed {seed}.')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['init-env', 'migrate', 'seed', 'benchmark'])
    parser.add_argument('--seed', type=int, default=104)
    parser.add_argument('--count', type=int, default=5000)
    args = parser.parse_args()
    if not 1 <= args.count <= 10000:
        parser.error('--count must be 1..10000')
    if args.command == 'init-env':
        init_environment()
    elif args.command == 'migrate':
        database = Database(Path(os.environ.get('DATABASE_PATH', 'var/klaimkembar.sqlite')))
        database.migrate()
        database.verify_schema()
        print('Migration 001 verified on SQLite.')
    elif args.command == 'seed':
        create_seed(args.seed, args.count)
    elif args.command == 'benchmark':
        rules = Rules.load(Path(os.environ.get('RULES_PATH', ROOT / 'rules.json')))
        before = hashlib.sha256((ROOT / 'klaimkembar/engine.py').read_bytes()).hexdigest()
        report = benchmark(rules, [104, 211, 307, 409, 503], args.count)
        after = hashlib.sha256((ROOT / 'klaimkembar/engine.py').read_bytes()).hexdigest()
        assert before == after
        target = Path(os.environ.get('BENCHMARK_PATH', ROOT / 'examples/benchmark.json'))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(report.model_dump_json(indent=2) + '\n')
        freeze = {'engine_sha256': before, 'rules_sha256': rules.fingerprint, 'seeds': [104, 211, 307, 409, 503],
                  'claims_per_seed': args.count, 'created_at': report.generated_at}
        (target.parent / 'benchmark_provenance.json').write_text(json.dumps(freeze, indent=2) + '\n')
        print(f'Benchmark persisted: 5 seeds, {args.count} claims each; detector hash unchanged.')


if __name__ == '__main__':
    main()
