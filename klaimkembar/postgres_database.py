"""Experimental PostgreSQL adapter for the synthetic demo.

This module is not enabled by default. It must be validated against the target
PostgreSQL instance and migration before any deployment uses it.
"""

import re
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parent.parent


class HybridRow:
    """Rows retain the name and positional access used by the SQLite workflow."""

    def __init__(self, values: Sequence[Any], names: tuple[str, ...]):
        self.values = values
        self.names = names

    def __getitem__(self, key: int | slice | str) -> Any:
        if isinstance(key, str):
            try:
                idx = self.names.index(key)
            except ValueError:
                raise KeyError(key) from None
            return self.values[idx]
        return self.values[key]

    def __len__(self) -> int:
        return len(self.values)

    def __iter__(self) -> Iterator[Any]:
        return iter(self.values)

    def keys(self) -> tuple[str, ...]:
        return self.names

    def get(self, key: str, default: Any = None) -> Any:
        try:
            return self[key]
        except KeyError:
            return default

    def __repr__(self) -> str:
        pairs = ", ".join(f"{k}={v!r}" for k, v in zip(self.names, self.values))
        return f"HybridRow({pairs})"


def hybrid_row(cursor: Any) -> Any:
    names = tuple(column.name for column in cursor.description or ())

    def build(values: Sequence[Any]) -> HybridRow:
        return HybridRow(values, names)

    return build


def _replace_needs_data(m: re.Match[str]) -> str:
    prefix = m.group(1) or ""
    return f"COALESCE(({prefix}payload::jsonb->>'needs_data')::boolean, false)"


def _replace_ml_score(m: re.Match[str]) -> str:
    prefix = m.group(1) or ""
    return f"COALESCE(({prefix}payload::jsonb->>'ml_score')::double precision, 0.0)"


def _replace_risk_level(m: re.Match[str]) -> str:
    prefix = m.group(1) or ""
    return f"({prefix}payload::jsonb->>'risk_level')"


def _replace_reasons(m: re.Match[str]) -> str:
    prefix = m.group(1) or ""
    return f"EXISTS (SELECT 1 FROM jsonb_array_elements_text({prefix}payload::jsonb->'triggered_reasons') AS reasons(value) WHERE value=?)"


def _replace_reducers(m: re.Match[str]) -> str:
    prefix = m.group(1) or ""
    return f"EXISTS (SELECT 1 FROM jsonb_array_elements({prefix}payload::jsonb->'risk_reducers') AS reducers(value) WHERE value->>'code'=?)"


def _translate(sql: str) -> str:
    """Translate the fixed, internal SQLite query vocabulary used by this app."""
    sql = re.sub(
        r"json_extract\s*\(\s*(c\.)?payload\s*,\s*['\"]\$\.needs_data['\"]\s*\)\s*=\s*1",
        _replace_needs_data,
        sql,
    )
    sql = re.sub(
        r"json_extract\s*\(\s*(c\.)?payload\s*,\s*['\"]\$\.ml_score['\"]\s*\)",
        _replace_ml_score,
        sql,
    )
    sql = re.sub(
        r"json_extract\s*\(\s*(c\.)?payload\s*,\s*['\"]\$\.risk_level['\"]\s*\)",
        _replace_risk_level,
        sql,
    )
    sql = re.sub(
        r"SELECT\s+DISTINCT\s+value\s+FROM\s+cases\s*,\s*json_each\s*\(\s*cases\.payload\s*,\s*['\"]\$\.triggered_reasons['\"]\s*\)\s+WHERE\s+dataset_id\s*=\s*\?\s+ORDER\s+BY\s+value",
        "SELECT DISTINCT reasons.value FROM cases CROSS JOIN LATERAL jsonb_array_elements_text(cases.payload::jsonb->'triggered_reasons') AS reasons(value) WHERE dataset_id=? ORDER BY reasons.value",
        sql,
    )
    sql = re.sub(
        r"EXISTS\s*\(\s*SELECT\s+1\s+FROM\s+json_each\s*\(\s*(c\.)?payload\s*,\s*['\"]\$\.triggered_reasons['\"]\s*\)\s+WHERE\s+value\s*=\s*\?\s*\)",
        _replace_reasons,
        sql,
    )
    sql = re.sub(
        r"EXISTS\s*\(\s*SELECT\s+1\s+FROM\s+json_each\s*\(\s*(c\.)?payload\s*,\s*['\"]\$\.risk_reducers['\"]\s*\)\s+WHERE\s+json_extract\s*\(\s*value\s*,\s*['\"]\$\.code['\"]\s*\)\s*=\s*\?\s*\)",
        _replace_reducers,
        sql,
    )
    if "json_extract(" in sql or "json_each(" in sql:
        raise ValueError("unsupported SQLite JSON expression in PostgreSQL adapter")
    return sql.replace("?", "%s")


class PostgresConnection:
    def __init__(self, connection: Any):
        self.connection = connection
        self._lock_next_case = False

    def execute(self, sql: str, parameters: Sequence[Any] = ()) -> Any:
        if sql.strip().upper() == "BEGIN IMMEDIATE":
            # The transaction already started with SET LOCAL. Lock the reviewed
            # case on the subsequent lookup so concurrent retries serialize.
            self._lock_next_case = True
            return self.connection.execute("SELECT 1")
        translated = _translate(sql)
        if self._lock_next_case and re.match(r"^SELECT\s+\*\s+FROM\s+cases\s+WHERE\s+id\s*=\s*\?$", sql.strip(), re.IGNORECASE):
            translated += " FOR UPDATE"
            self._lock_next_case = False
        return self.connection.execute(translated, parameters)

    def executemany(self, sql: str, rows: Sequence[Sequence[Any]]) -> Any:
        cursor = self.connection.cursor()
        cursor.executemany(_translate(sql), rows)
        return cursor


class PostgresDatabase:
    kind = "postgres"

    def __init__(self, url: str, schema: str = "klaimkembar"):
        if not re.fullmatch(r"[a-z_][a-z0-9_]*", schema):
            raise ValueError("invalid schema identifier")
        self._schema = schema
        if not url.startswith(("postgresql://", "postgres://")):
            raise ValueError("PostgreSQL URL required")
        parsed = urlsplit(url)
        # Vercel integration adds a driver-specific `supa` parameter unsupported
        # by libpq. Keep all supported connection parameters including TLS.
        query = urlencode([(key, value) for key, value in parse_qsl(parsed.query, keep_blank_values=True) if key != "supa"])
        self._url = urlunsplit(parsed._replace(query=query))

    @contextmanager
    def connect(self) -> Iterator[PostgresConnection]:
        # Lazy import keeps the existing SQLite prototype usable without psycopg.
        import psycopg

        with psycopg.connect(self._url, row_factory=hybrid_row, prepare_threshold=None, connect_timeout=10) as raw:
            raw.execute(f"SET LOCAL search_path TO {self._schema}, pg_catalog")
            yield PostgresConnection(raw)

    def verify_schema(self) -> None:
        with self.connect() as connection:
            versions = [row[0] for row in connection.execute("SELECT version FROM schema_version")]
            if versions != [1]:
                raise ValueError("database migration version does not match this application")

    def init_schema(self, ddl: str | None = None) -> None:
        """Apply the PostgreSQL DDL idempotently."""
        import psycopg

        if ddl is None:
            schema_file = ROOT / "docs" / "draft-postgres-schema.sql"
            if not schema_file.exists():
                schema_file = ROOT / "supabase" / "migrations" / "20261030000001_klaimkembar_schema.sql"
            ddl = schema_file.read_text()

        with psycopg.connect(self._url, autocommit=True, prepare_threshold=None, connect_timeout=15) as raw:
            raw.execute(ddl)

    def migrate(self) -> None:
        """Alias for init_schema to match the Database interface."""
        self.init_schema()
