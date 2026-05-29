import tempfile
import unittest
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
