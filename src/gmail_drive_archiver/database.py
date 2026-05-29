from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path


SCHEMA = """
CREATE TABLE IF NOT EXISTS processed_items (
    service TEXT NOT NULL,
    item_id TEXT NOT NULL,
    rule_name TEXT NOT NULL,
    action TEXT NOT NULL,
    processed_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (service, item_id, rule_name)
);
CREATE INDEX IF NOT EXISTS idx_processed_service_item
    ON processed_items(service, item_id);
"""


class ProcessedStore:
    """SQLite-backed state used to avoid processing the same item twice."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(self.path)
        self._connection.execute("PRAGMA foreign_keys = ON")

    def initialize(self) -> None:
        with self._connection:
            self._connection.executescript(SCHEMA)

    def is_processed(self, service: str, item_id: str, rule_name: str) -> bool:
        with closing(
            self._connection.execute(
                """
                SELECT 1
                FROM processed_items
                WHERE service = ? AND item_id = ? AND rule_name = ?
                LIMIT 1
                """,
                (service, item_id, rule_name),
            )
        ) as cursor:
            return cursor.fetchone() is not None

    def mark_processed(self, service: str, item_id: str, rule_name: str, action: str) -> None:
        with self._connection:
            self._connection.execute(
                """
                INSERT OR IGNORE INTO processed_items(service, item_id, rule_name, action)
                VALUES (?, ?, ?, ?)
                """,
                (service, item_id, rule_name, action),
            )

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> "ProcessedStore":
        self.initialize()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
        self.close()
