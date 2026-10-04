import sqlite3

import pytest

from klaimkembar.database import Database
from klaimkembar.settings import ROOT, Rules, Settings


def test_empty_migration_is_repeatable_and_enforces_foreign_keys(tmp_path):
    db = Database(tmp_path / 'claims.sqlite')
    db.migrate()
    db.migrate()
    db.verify_schema()
    with db.connect() as connection:
        assert connection.execute('SELECT COUNT(*) FROM datasets').fetchone()[0] == 0
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("INSERT INTO claims VALUES ('missing','a','p','f','2026-01-01','{}')")


def test_settings_reject_missing_tokens_and_wildcard_origin(tmp_path):
    with pytest.raises(ValueError):
        Settings(tmp_path / 'db', '', '')
    with pytest.raises(ValueError):
        Settings(tmp_path / 'db', 'r' * 32, 'a' * 32, ('*',))
    with pytest.raises(ValueError):
        Settings(tmp_path / 'db', 'r' * 32, 'r' * 32)


def test_rules_are_frozen_with_explicit_weights():
    rules = Rules.load(ROOT / 'rules.json')
    assert sum(rules.weights.values()) == 100
    assert len(rules.fingerprint) == 64
    assert rules.blocking_days == 3


def test_invalid_rule_weights_rejected(tmp_path):
    import json
    raw = json.loads((ROOT / 'rules.json').read_text())
    raw['weights']['SAME_PARTICIPANT'] = 25
    path = tmp_path / 'rules.json'
    path.write_text(json.dumps(raw))
    with pytest.raises(ValueError):
        Rules.load(path)
