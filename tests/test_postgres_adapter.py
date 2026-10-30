from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from klaimkembar.postgres_database import (
    HybridRow,
    PostgresConnection,
    PostgresDatabase,
    _translate,
    hybrid_row,
)


def test_row_supports_named_and_positional_lookup():
    row = HybridRow(("demo", 7, 99.5), ("label", "version", "score"))
    # Index lookup
    assert row[0] == "demo"
    assert row[1] == 7
    assert row[2] == 99.5
    assert row[-1] == 99.5

    # Column name lookup
    assert row["label"] == "demo"
    assert row["version"] == 7
    assert row["score"] == 99.5

    # Slice lookup
    assert row[0:2] == ("demo", 7)
    assert row[1:] == (7, 99.5)

    # Dictionary-like methods and iteration
    assert len(row) == 3
    assert list(row) == ["demo", 7, 99.5]
    assert row.keys() == ("label", "version", "score")
    assert row.get("label") == "demo"
    assert row.get("unknown", "default_val") == "default_val"
    assert "label='demo'" in repr(row)

    # Missing key raises KeyError
    with pytest.raises(KeyError):
        _ = row["nonexistent_column"]


def test_hybrid_row_factory():
    cursor = SimpleNamespace(description=[SimpleNamespace(name="case_id"), SimpleNamespace(name="status")])
    builder = hybrid_row(cursor)
    row = builder(("case-123", "unreviewed"))
    assert isinstance(row, HybridRow)
    assert row["case_id"] == "case-123"
    assert row[1] == "unreviewed"


def test_sql_translation_covers_filters_and_facets():
    sql = "SELECT * FROM cases c WHERE json_extract(c.payload,'$.risk_level')=? AND json_extract(c.payload,'$.needs_data')=1"
    translated = _translate(sql)
    assert "json_extract" not in translated
    assert "(c.payload::jsonb->>'risk_level')" in translated
    assert "COALESCE((c.payload::jsonb->>'needs_data')::boolean, false)" in translated
    assert "%s" in translated

    facets = "SELECT DISTINCT value FROM cases,json_each(cases.payload,'$.triggered_reasons') WHERE dataset_id=? ORDER BY value"
    assert "jsonb_array_elements_text" in _translate(facets)


def test_sql_translation_ml_score():
    # Both with and without table prefix, with and without whitespace
    q1 = "SELECT * FROM cases c ORDER BY json_extract(c.payload, '$.ml_score') DESC"
    t1 = _translate(q1)
    assert "COALESCE((c.payload::jsonb->>'ml_score')::double precision, 0.0)" in t1

    q2 = "SELECT * FROM cases ORDER BY json_extract(payload,'$.ml_score') ASC"
    t2 = _translate(q2)
    assert "COALESCE((payload::jsonb->>'ml_score')::double precision, 0.0)" in t2

    q3 = "SELECT * FROM cases c WHERE json_extract(c.payload,'$.ml_score') >= ?"
    t3 = _translate(q3)
    assert "COALESCE((c.payload::jsonb->>'ml_score')::double precision, 0.0) >= %s" in t3


def test_sql_translation_all_case_filters():
    # Full compound filter mimicking workflow.cases
    sql = (
        "SELECT c.* FROM cases c JOIN claims a ON a.dataset_id=c.dataset_id AND a.claim_id=c.claim_a "
        "WHERE c.dataset_id=? AND c.protected=0 AND (c.risk_score>=? OR json_extract(c.payload, '$.needs_data')=1) "
        "AND json_extract(c.payload, '$.risk_level')=? AND c.review_status=? "
        "AND (EXISTS (SELECT 1 FROM json_each(c.payload, '$.triggered_reasons') WHERE value=?) "
        "OR EXISTS (SELECT 1 FROM json_each(c.payload, '$.risk_reducers') WHERE json_extract(value, '$.code')=?))"
    )
    translated = _translate(sql)
    assert "json_extract" not in translated
    assert "json_each" not in translated
    assert "COALESCE((c.payload::jsonb->>'needs_data')::boolean, false)" in translated
    assert "(c.payload::jsonb->>'risk_level')" in translated
    assert "jsonb_array_elements_text(c.payload::jsonb->'triggered_reasons')" in translated
    assert "jsonb_array_elements(c.payload::jsonb->'risk_reducers')" in translated
    assert "value->>'code'" in translated
    assert "?" not in translated


def test_sql_translation_unsupported_json_raises():
    with pytest.raises(ValueError, match="unsupported SQLite JSON expression"):
        _translate("SELECT json_extract(payload, '$.unsupported_field') FROM cases")

    with pytest.raises(ValueError, match="unsupported SQLite JSON expression"):
        _translate("SELECT * FROM json_each(payload, '$.unsupported_array')")


def test_review_lock_is_scoped_to_first_case_lookup():
    class FakeConnection:
        def __init__(self) -> None:
            self.queries: list[str] = []

        def execute(self, sql: str, params: tuple[object, ...] = ()) -> None:
            self.queries.append(sql)
            return None

    raw = FakeConnection()
    connection = PostgresConnection(raw)
    connection.execute("BEGIN IMMEDIATE")
    connection.execute("SELECT * FROM cases WHERE id=?", ("synthetic-id",))
    connection.execute("SELECT * FROM cases WHERE id=?", ("synthetic-id",))
    assert raw.queries[1].endswith("FOR UPDATE")
    assert not raw.queries[2].endswith("FOR UPDATE")


def test_postgres_connection_executemany():
    class FakeCursor:
        def __init__(self) -> None:
            self.called_with: tuple[str, list[tuple[object, ...]]] | None = None

        def executemany(self, sql: str, rows: list[tuple[object, ...]]) -> None:
            self.called_with = (sql, rows)

    class FakeConnection:
        def __init__(self) -> None:
            self.cursor_instance = FakeCursor()

        def cursor(self) -> FakeCursor:
            return self.cursor_instance

    raw = FakeConnection()
    connection = PostgresConnection(raw)
    rows = [("id1", "data1"), ("id2", "data2")]
    cursor = connection.executemany("INSERT INTO claims VALUES (?,?)", rows)
    assert cursor is raw.cursor_instance
    assert raw.cursor_instance.called_with is not None
    assert raw.cursor_instance.called_with[0] == "INSERT INTO claims VALUES (%s,%s)"
    assert raw.cursor_instance.called_with[1] == rows


def test_vercel_pooler_url_removes_only_supa_parameter():
    db = PostgresDatabase("postgresql://synthetic:synthetic@localhost/db?sslmode=require&supa=ignored")
    assert "supa=" not in db._url
    assert "sslmode=require" in db._url


def test_postgres_database_validation():
    with pytest.raises(ValueError, match="invalid schema identifier"):
        PostgresDatabase("postgresql://localhost/db", schema="invalid-schema-name!")

    with pytest.raises(ValueError, match="PostgreSQL URL required"):
        PostgresDatabase("sqlite:///some/path.db")


def test_postgres_database_verify_schema():
    db = PostgresDatabase("postgresql://user:pass@localhost/db")

    class FakeRow(tuple):
        pass

    class FakeCursor:
        def __init__(self, versions: list[int]) -> None:
            self.versions = versions

        def execute(self, sql: str, params: tuple[object, ...] = ()) -> list[tuple[int]]:
            return [(v,) for v in self.versions]

    # Valid schema version [1]
    with patch.object(db, "connect") as mock_connect:
        mock_connect.return_value.__enter__.return_value = FakeCursor([1])
        db.verify_schema()

    # Invalid schema version [2]
    with patch.object(db, "connect") as mock_connect:
        mock_connect.return_value.__enter__.return_value = FakeCursor([2])
        with pytest.raises(ValueError, match="database migration version does not match"):
            db.verify_schema()


def test_postgres_database_init_schema_and_migrate():
    db = PostgresDatabase("postgresql://user:pass@localhost/db")
    mock_conn = MagicMock()

    with patch("psycopg.connect") as mock_connect:
        mock_connect.return_value.__enter__.return_value = mock_conn

        # Custom DDL
        custom_ddl = "CREATE TABLE IF NOT EXISTS test_table (id INT);"
        db.init_schema(ddl=custom_ddl)
        mock_conn.execute.assert_called_with(custom_ddl)

        # Default DDL (reads draft-postgres-schema.sql)
        mock_conn.reset_mock()
        db.migrate()
        mock_conn.execute.assert_called_once()
        executed_ddl = mock_conn.execute.call_args[0][0]
        assert "CREATE SCHEMA IF NOT EXISTS klaimkembar" in executed_ddl
        assert "klaimkembar.schema_version" in executed_ddl
        assert "klaimkembar.users" in executed_ddl
        assert "cases_ml_score_idx" in executed_ddl
        assert "cases_payload_gin" in executed_ddl
