import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from klaimkembar.settings import ROOT


class Database:
    kind = "sqlite"

    def __init__(self, path: Path):
        self.path = path

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=15)
        connection.row_factory = sqlite3.Row
        connection.execute('PRAGMA foreign_keys=ON')
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def migrate(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.executescript((ROOT / 'migrations/001_initial.sql').read_text())
            connection.execute('PRAGMA journal_mode=WAL')

    def verify_schema(self) -> None:
        with self.connect() as connection:
            versions = [row[0] for row in connection.execute('SELECT version FROM schema_version')]
            if versions != [1]:
                raise ValueError('database migration version does not match this application')
