import tempfile
import unittest
from pathlib import Path
import sqlite3

from gmail_drive_archiver.database import ProcessedStore


class ProcessedStoreTest(unittest.TestCase):
    def test_tracks_processed_items_by_service_item_and_rule(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "processed.sqlite3"
            with ProcessedStore(db_path) as store:
                self.assertFalse(store.is_processed("gmail", "msg-1", "old-newsletters"))

                store.mark_processed("gmail", "msg-1", "old-newsletters", "archive")

                self.assertTrue(store.is_processed("gmail", "msg-1", "old-newsletters"))
                self.assertFalse(store.is_processed("gmail", "msg-1", "other-rule"))
                self.assertFalse(store.is_processed("drive", "msg-1", "old-newsletters"))

    def test_creates_parent_directories(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "state" / "processed.sqlite3"

            with ProcessedStore(db_path):
                pass

            self.assertTrue(db_path.exists())

    def test_records_email_drive_file_and_classification_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "processed.sqlite3"
            with ProcessedStore(db_path) as store:
                store.record_email("email-1", "attachments", "has:attachment", "archived")
                store.record_drive_file(
                    file_id="file-1",
                    source_email_id="email-1",
                    original_name="fattura.pdf",
                    current_name="2026-05-fattura.pdf",
                    category="Fisco",
                    status="classified",
                    drive_folder_id="folder-1",
                )
                store.record_classification(
                    file_id="file-1",
                    category="Fisco",
                    original_name="fattura.pdf",
                    new_name="2026-05-fattura.pdf",
                    status="accepted",
                    confidence=0.92,
                )

            connection = sqlite3.connect(db_path)
            try:
                email_status = connection.execute(
                    "SELECT status FROM email_messages WHERE email_id = ?",
                    ("email-1",),
                ).fetchone()
                file_status = connection.execute(
                    "SELECT category, status FROM drive_files WHERE file_id = ?",
                    ("file-1",),
                ).fetchone()
                classification_count = connection.execute(
                    "SELECT COUNT(*) FROM file_classifications WHERE file_id = ?",
                    ("file-1",),
                ).fetchone()
            finally:
                connection.close()

            self.assertEqual(email_status, ("archived",))
            self.assertEqual(file_status, ("Fisco", "classified"))
            self.assertEqual(classification_count, (1,))


if __name__ == "__main__":
    unittest.main()
