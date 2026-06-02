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
    suggested_visibility TEXT,
    relevant_date TEXT,
    deadline TEXT,
    recommended_action TEXT,
    duplicate_of TEXT,
    confidence TEXT,
    reason TEXT,
    source_path TEXT,
    review_status TEXT NOT NULL DEFAULT 'pending',
    drive_file_id TEXT,
    target_folder_id TEXT,
    applied_at TEXT,
    imported_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


def _dedupe_keep_item(items: list[dict[str, str]]) -> dict[str, str]:
    status_priority = {
        "applied": 0,
        "approved": 1,
        "pending": 2,
        "rejected": 3,
    }
    return sorted(
        items,
        key=lambda item: (
            status_priority.get(item.get("review_status", ""), 9),
            -int(item["id"]),
        ),
    )[0]


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
            self._ensure_ai_review_columns()

    def _ensure_ai_review_columns(self) -> None:
        columns = {
            row[1]
            for row in self._connection.execute("PRAGMA table_info(ai_review_items)").fetchall()
        }
        migrations = {
            "review_status": "ALTER TABLE ai_review_items ADD COLUMN review_status TEXT NOT NULL DEFAULT 'pending'",
            "drive_file_id": "ALTER TABLE ai_review_items ADD COLUMN drive_file_id TEXT",
            "target_folder_id": "ALTER TABLE ai_review_items ADD COLUMN target_folder_id TEXT",
            "applied_at": "ALTER TABLE ai_review_items ADD COLUMN applied_at TEXT",
            "suggested_visibility": "ALTER TABLE ai_review_items ADD COLUMN suggested_visibility TEXT",
        }
        for column, statement in migrations.items():
            if column not in columns:
                self._connection.execute(statement)

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
        suggested_visibility: str,
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
                    suggested_visibility,
                    relevant_date,
                    deadline,
                    recommended_action,
                    duplicate_of,
                    confidence,
                    reason,
                    source_path,
                    review_status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')
                """,
                (
                    document_name,
                    category,
                    subcategory,
                    owner,
                    suggested_visibility,
                    relevant_date,
                    deadline,
                    recommended_action,
                    duplicate_of,
                    confidence,
                    reason,
                    source_path,
                ),
            )

    def set_ai_review_status(
        self,
        status: str,
        category: str | None = None,
        min_confidence: float | None = None,
        action: str | None = None,
        limit: int | None = None,
    ) -> int:
        filters = ["review_status = 'pending'"]
        params: list[object] = []
        if category:
            filters.append("category = ?")
            params.append(category)
        if action:
            filters.append("recommended_action = ?")
            params.append(action)
        if min_confidence is not None:
            filters.append("CAST(NULLIF(confidence, '') AS REAL) >= ?")
            params.append(min_confidence)

        where_clause = " AND ".join(filters)
        limit_clause = " LIMIT ?" if limit is not None else ""
        if limit is not None:
            params.append(limit)

        with self._connection:
            cursor = self._connection.execute(
                f"""
                UPDATE ai_review_items
                SET review_status = ?
                WHERE id IN (
                    SELECT id
                    FROM ai_review_items
                    WHERE {where_clause}
                    ORDER BY id ASC
                    {limit_clause}
                )
                """,
                [status, *params],
            )
        return cursor.rowcount

    def set_ai_review_status_by_ids(self, ids: list[int], status: str) -> int:
        if not ids:
            return 0
        placeholders = ",".join("?" for _item in ids)
        with self._connection:
            cursor = self._connection.execute(
                f"""
                UPDATE ai_review_items
                SET review_status = ?
                WHERE id IN ({placeholders})
                """,
                [status, *ids],
            )
        return cursor.rowcount

    def update_ai_review_fields(
        self,
        review_id: int,
        category: str | None = None,
        owner: str | None = None,
        suggested_visibility: str | None = None,
        recommended_action: str | None = None,
    ) -> int:
        updates: list[str] = []
        params: list[object] = []
        for column, value in (
            ("category", category),
            ("owner", owner),
            ("suggested_visibility", suggested_visibility),
            ("recommended_action", recommended_action),
        ):
            if value is not None:
                updates.append(f"{column} = ?")
                params.append(value)

        if not updates:
            return 0

        params.append(review_id)
        with self._connection:
            cursor = self._connection.execute(
                f"""
                UPDATE ai_review_items
                SET {", ".join(updates)}
                WHERE id = ?
                """,
                params,
            )
        return cursor.rowcount

    def dedupe_ai_review_items(self, dry_run: bool = True) -> list[dict[str, str]]:
        rows = self._connection.execute(
            """
            SELECT
                id,
                document_name,
                category,
                recommended_action,
                review_status,
                imported_at
            FROM ai_review_items
            ORDER BY id ASC
            """
        ).fetchall()

        grouped: dict[tuple[str, str, str], list[dict[str, str]]] = {}
        for row in rows:
            item = {
                "id": str(row[0]),
                "document_name": "" if row[1] is None else str(row[1]),
                "category": "" if row[2] is None else str(row[2]),
                "recommended_action": "" if row[3] is None else str(row[3]),
                "review_status": "" if row[4] is None else str(row[4]),
                "imported_at": "" if row[5] is None else str(row[5]),
            }
            key = (
                item["document_name"].casefold().strip(),
                item["category"].casefold().strip(),
                item["recommended_action"].casefold().strip(),
            )
            grouped.setdefault(key, []).append(item)

        duplicates: list[dict[str, str]] = []
        delete_ids: list[int] = []
        for items in grouped.values():
            if len(items) <= 1:
                continue
            kept = _dedupe_keep_item(items)
            for item in items:
                if item["id"] == kept["id"]:
                    continue
                duplicate = dict(item)
                duplicate["kept_id"] = kept["id"]
                duplicates.append(duplicate)
                delete_ids.append(int(item["id"]))

        if delete_ids and not dry_run:
            placeholders = ",".join("?" for _item in delete_ids)
            with self._connection:
                self._connection.execute(
                    f"DELETE FROM ai_review_items WHERE id IN ({placeholders})",
                    delete_ids,
                )

        return duplicates

    def update_ai_review_normalized_fields(
        self,
        review_id: int,
        category: str,
        owner: str,
        suggested_visibility: str,
    ) -> None:
        with self._connection:
            self._connection.execute(
                """
                UPDATE ai_review_items
                SET
                    category = ?,
                    owner = ?,
                    suggested_visibility = ?
                WHERE id = ?
                """,
                (category, owner, suggested_visibility, review_id),
            )

    def ai_review_status_counts(self) -> list[tuple[str, int]]:
        with closing(
            self._connection.execute(
                """
                SELECT COALESCE(NULLIF(review_status, ''), 'Senza stato') AS status, COUNT(*) AS count
                FROM ai_review_items
                GROUP BY COALESCE(NULLIF(review_status, ''), 'Senza stato')
                ORDER BY count DESC, status ASC
                """
            )
        ) as cursor:
            return [(str(row[0]), int(row[1])) for row in cursor.fetchall()]

    def ai_review_items(
        self,
        status: str | None = None,
        category: str | None = None,
        limit: int = 200,
    ) -> list[dict[str, str]]:
        filters: list[str] = []
        params: list[object] = []
        if status:
            filters.append("review_status = ?")
            params.append(status)
        if category:
            filters.append("category = ?")
            params.append(category)
        where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""
        params.append(limit)

        with closing(
            self._connection.execute(
                f"""
                SELECT
                    id,
                    document_name,
                    category,
                    subcategory,
                    owner,
                    suggested_visibility,
                    relevant_date,
                    deadline,
                    recommended_action,
                    duplicate_of,
                    confidence,
                    reason,
                    review_status,
                    drive_file_id,
                    target_folder_id
                FROM ai_review_items
                {where_clause}
                ORDER BY id DESC
                LIMIT ?
                """,
                params,
            )
        ) as cursor:
            rows = cursor.fetchall()

        keys = [
            "id",
            "document_name",
            "category",
            "subcategory",
            "owner",
            "suggested_visibility",
            "relevant_date",
            "deadline",
            "recommended_action",
            "duplicate_of",
            "confidence",
            "reason",
            "review_status",
            "drive_file_id",
            "target_folder_id",
        ]
        return [{key: "" if value is None else str(value) for key, value in zip(keys, row)} for row in rows]

    def ai_review_items_for_status(self, status: str = "approved") -> list[dict[str, str]]:
        with closing(
            self._connection.execute(
                """
                SELECT
                    id,
                    document_name,
                    category,
                    subcategory,
                    owner,
                    suggested_visibility,
                    recommended_action,
                    confidence,
                    reason,
                    review_status,
                    drive_file_id,
                    target_folder_id
                FROM ai_review_items
                WHERE review_status = ?
                ORDER BY id ASC
                """,
                (status,),
            )
        ) as cursor:
            rows = cursor.fetchall()

        keys = [
            "id",
            "document_name",
            "category",
            "subcategory",
            "owner",
            "suggested_visibility",
            "recommended_action",
            "confidence",
            "reason",
            "review_status",
            "drive_file_id",
            "target_folder_id",
        ]
        return [{key: "" if value is None else str(value) for key, value in zip(keys, row)} for row in rows]

    def mark_ai_review_applied(self, review_id: int, drive_file_id: str, target_folder_id: str) -> None:
        with self._connection:
            self._connection.execute(
                """
                UPDATE ai_review_items
                SET
                    review_status = 'applied',
                    drive_file_id = ?,
                    target_folder_id = ?,
                    applied_at = datetime('now')
                WHERE id = ?
                """,
                (drive_file_id, target_folder_id, review_id),
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
                    suggested_visibility,
                    recommended_action,
                    confidence,
                    reason,
                    review_status
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
            "suggested_visibility",
            "recommended_action",
            "confidence",
            "reason",
            "review_status",
        ]
        return [{key: "" if value is None else str(value) for key, value in zip(keys, row)} for row in rows]

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> "ProcessedStore":
        self.initialize()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
        self.close()
