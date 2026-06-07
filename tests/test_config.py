import tempfile
import unittest
from pathlib import Path

from gmail_drive_archiver.config import load_split_config


class ConfigTest(unittest.TestCase):
    def test_loads_drive_settings_from_split_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            drive_config = Path(tmpdir) / "drive-folders.yml"
            drive_config.write_text(
                """
drive:
  inbox_folder_id: "inbox-123"
  archive_root_folder_id: "archive-456"
  category_folders:
    Banca: "bank-789"
  rules:
    - name: pdf
      query: "mimeType='application/pdf'"
      target_folder_id: "inbox-123"
""",
                encoding="utf-8",
            )

            config = load_split_config(None, drive_config, None)

            self.assertEqual(config.drive_settings.inbox_folder_id, "inbox-123")
            self.assertEqual(config.drive_settings.archive_root_folder_id, "archive-456")
            self.assertEqual(config.drive_settings.category_folders["Banca"], "bank-789")
            self.assertEqual(config.drive[0].name, "pdf")


if __name__ == "__main__":
    unittest.main()
