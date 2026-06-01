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

CREATE TABLE IF NOT EXISTS email_messages (
    email_id TEXT PRIMARY KEY,
    rule_name TEXT NOT NULL,
    gmail_query TEXT NOT NULL,
    status TEXT NOT NULL,
    processed_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS drive_files (
    file_id TEXT PRIMARY KEY,
    source_email_id TEXT,
    original_name TEXT,
    current_name TEXT,
    category TEXT,
    status TEXT NOT NULL,
    drive_folder_id TEXT,
    saved_at TEXT NOT NULL DEFAULT (datetime('now')),
    processed_at TEXT,
    FOREIGN KEY (source_email_id) REFERENCES email_messages(email_id)
);

CREATE TABLE IF NOT EXISTS file_classifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id TEXT NOT NULL,
    category TEXT NOT NULL,
    original_name TEXT,
    new_name TEXT,
    status TEXT NOT NULL,
    confidence REAL,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (file_id) REFERENCES drive_files(file_id)
);

CREATE TABLE IF NOT EXISTS ai_review_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_name TEXT NOT NULL,
    category TEXT,
    subcategory TEXT,
    owner TEXT,
    relevant_date TEXT,
    deadline TEXT,
    recommended_action TEXT,
    duplicate_of TEXT,
    confidence TEXT,
    reason TEXT,
    source_path TEXT,
    imported_at TEXT NOT NULL DEFAULT (datetime('now'))
);
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

    def record_email(self, email_id: str, rule_name: str, gmail_query: str, status: str) -> None:
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO email_messages(email_id, rule_name, gmail_query, status, processed_at)
                VALUES (?, ?, ?, ?, datetime('now'))
                ON CONFLICT(email_id) DO UPDATE SET
                    rule_name = excluded.rule_name,
                    gmail_query = excluded.gmail_query,
                    status = excluded.status,
                    processed_at = excluded.processed_at
                """,
                (email_id, rule_name, gmail_query, status),
            )

    def record_drive_file(
        self,
        file_id: str,
        original_name: str | None,
        current_name: str | None,
        status: str,
        drive_folder_id: str | None = None,
        source_email_id: str | None = None,
        category: str | None = None,
    ) -> None:
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO drive_files(
                    file_id,
                    source_email_id,
                    original_name,
                    current_name,
                    category,
                    status,
                    drive_folder_id,
                    processed_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
                ON CONFLICT(file_id) DO UPDATE SET
                    source_email_id = COALESCE(excluded.source_email_id, drive_files.source_email_id),
                    original_name = COALESCE(excluded.original_name, drive_files.original_name),
                    current_name = excluded.current_name,
                    category = COALESCE(excluded.category, drive_files.category),
                    status = excluded.status,
                    drive_folder_id = COALESCE(excluded.drive_folder_id, drive_files.drive_folder_id),
                    processed_at = excluded.processed_at
                """,
                (file_id, source_email_id, original_name, current_name, category, status, drive_folder_id),
            )

    def record_classification(
        self,
        file_id: str,
        category: str,
        status: str,
        original_name: str | None = None,
        new_name: str | None = None,
        confidence: float | None = None,
        notes: str | None = None,
    ) -> None:
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO file_classifications(
                    file_id,
                    category,
                    original_name,
                    new_name,
                    status,
                    confidence,
                    notes
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (file_id, category, original_name, new_name, status, confidence, notes),
            )

    def record_ai_review_item(
        self,
        document_name: str,
        category: str,
        subcategory: str,
        owner: str,
        relevant_date: str,
        deadline: str,
        recommended_action: str,
        duplicate_of: str,
        confidence: str,
        reason: str,
        source_path: str,
    ) -> None:
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO ai_review_items(
                    document_name,
                    category,
                    subcategory,
                    owner,
                    relevant_date,
                    deadline,
                    recommended_action,
                    duplicate_of,
                    confidence,
                    reason,
                    source_path
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    document_name,
                    category,
                    subcategory,
                    owner,
                    relevant_date,
                    deadline,
                    recommended_action,
                    duplicate_of,
                    confidence,
                    reason,
                    source_path,
                ),
            )

    def ai_review_counts_by_category(self) -> list[tuple[str, int]]:
        with closing(
            self._connection.execute(
                """
                SELECT COALESCE(NULLIF(category, ''), 'Senza categoria') AS category, COUNT(*) AS count
                FROM ai_review_items
                GROUP BY COALESCE(NULLIF(category, ''), 'Senza categoria')
                ORDER BY count DESC, category ASC
                """
            )
        ) as cursor:
            return [(str(row[0]), int(row[1])) for row in cursor.fetchall()]

    def ai_review_counts_by_action(self) -> list[tuple[str, int]]:
        with closing(
            self._connection.execute(
                """
                SELECT COALESCE(NULLIF(recommended_action, ''), 'Senza azione') AS action, COUNT(*) AS count
                FROM ai_review_items
                GROUP BY COALESCE(NULLIF(recommended_action, ''), 'Senza azione')
                ORDER BY count DESC, action ASC
                """
            )
        ) as cursor:
            return [(str(row[0]), int(row[1])) for row in cursor.fetchall()]

    def latest_ai_review_items(self, limit: int = 20) -> list[dict[str, str]]:
        with closing(
            self._connection.execute(
                """
                SELECT
                    document_name,
                    category,
                    subcategory,
                    owner,
                    recommended_action,
                    confidence,
                    reason
                FROM ai_review_items
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            )
        ) as cursor:
            rows = cursor.fetchall()

        keys = [
            "document_name",
            "category",
            "subcategory",
            "owner",
            "recommended_action",
            "confidence",
            "reason",
        ]
        return [{key: "" if value is None else str(value) for key, value in zip(keys, row)} for row in rows]

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> "ProcessedStore":
        self.initialize()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
        self.close()
