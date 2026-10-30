"""Experimental PostgreSQL adapter for the synthetic demo.

This module is not enabled by default. It must be validated against the target
PostgreSQL instance and migration before any deployment uses it.
"""
import re
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


class HybridRow:
    """Rows retain the name and positional access used by the SQLite workflow."""
    def __init__(self, values: Sequence[Any], names: tuple[str, ...]):
        self.values = values
        self.names = names

    def __getitem__(self, key: int | slice | str) -> Any:
        if isinstance(key, str):
            key = self.names.index(key)
        return self.values[key]


def hybrid_row(cursor: Any) -> Any:
    names = tuple(column.name for column in cursor.description or ())
    def build(values: Sequence[Any]) -> HybridRow:
        return HybridRow(values, names)
    return build


def _translate(sql: str) -> str:
    """Translate the fixed, internal SQLite query vocabulary used by this app."""
    sql = sql.replace("json_extract(payload,'$.needs_data')=1", "COALESCE((payload::jsonb->>'needs_data')::boolean, false)")
    sql = sql.replace("json_extract(c.payload,'$.needs_data')=1", "COALESCE((c.payload::jsonb->>'needs_data')::boolean, false)")
    sql = sql.replace("json_extract(c.payload,'$.risk_level')", "(c.payload::jsonb->>'risk_level')")
    sql = sql.replace("EXISTS (SELECT 1 FROM json_each(c.payload,'$.triggered_reasons') WHERE value=?)", "EXISTS (SELECT 1 FROM jsonb_array_elements_text(c.payload::jsonb->'triggered_reasons') AS reasons(value) WHERE value=?)")
    sql = sql.replace("EXISTS (SELECT 1 FROM json_each(c.payload,'$.risk_reducers') WHERE json_extract(value,'$.code')=?)", "EXISTS (SELECT 1 FROM jsonb_array_elements(c.payload::jsonb->'risk_reducers') AS reducers(value) WHERE value->>'code'=?)")
    sql = sql.replace("SELECT DISTINCT value FROM cases,json_each(cases.payload,'$.triggered_reasons') WHERE dataset_id=? ORDER BY value", "SELECT DISTINCT reasons.value FROM cases CROSS JOIN LATERAL jsonb_array_elements_text(cases.payload::jsonb->'triggered_reasons') AS reasons(value) WHERE dataset_id=? ORDER BY reasons.value")
    if 'json_extract(' in sql or 'json_each(' in sql:
        raise ValueError('unsupported SQLite JSON expression in PostgreSQL adapter')
    return sql.replace('?', '%s')


class PostgresConnection:
    def __init__(self, connection: Any):
        self.connection = connection
        self._lock_next_case = False

    def execute(self, sql: str, parameters: Sequence[Any] = ()) -> Any:
        if sql.strip().upper() == 'BEGIN IMMEDIATE':
            # The transaction already started with SET LOCAL. Lock the reviewed
            # case on the subsequent lookup so concurrent retries serialize.
            self._lock_next_case = True
            return self.connection.execute('SELECT 1')
        translated = _translate(sql)
        if self._lock_next_case and sql.strip() == 'SELECT * FROM cases WHERE id=?':
            translated += ' FOR UPDATE'
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
        if not url.startswith(('postgresql://', 'postgres://')):
            raise ValueError('PostgreSQL URL required')
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
            raw.execute(f'SET LOCAL search_path TO {self._schema}, pg_catalog')
            yield PostgresConnection(raw)

    def verify_schema(self) -> None:
        with self.connect() as connection:
            versions = [row[0] for row in connection.execute('SELECT version FROM schema_version')]
            if versions != [1]:
                raise ValueError('database migration version does not match this application')
