import tempfile
import unittest
from pathlib import Path

from gmail_drive_archiver.drive_download import DownloadResult, download_filename, write_download_report
from gmail_drive_archiver.inventory_analysis import InventoryItem


class DriveDownloadTest(unittest.TestCase):
    def test_download_filename_sanitizes_names_and_keeps_extension(self) -> None:
        item = InventoryItem(id="file123", name="Preventivo 42.PDF", mime_type="application/pdf")

        self.assertEqual(download_filename(item), "Preventivo_42-file123.PDF")

    def test_download_filename_exports_google_docs_with_office_extension(self) -> None:
        item = InventoryItem(
            id="doc123",
            name="Documento Google",
            mime_type="application/vnd.google-apps.document",
        )

        self.assertEqual(download_filename(item), "Documento_Google-doc123.docx")

    def test_writes_download_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            report = Path(tmpdir) / "download-report.csv"
            write_download_report(
                [
                    DownloadResult(
                        item_id="file123",
                        name="Preventivo.pdf",
                        status="downloaded",
                        output_path="database/downloads/Preventivo-file123.pdf",
                    )
                ],
                report,
            )

            content = report.read_text(encoding="utf-8")

        self.assertIn("file123", content)
        self.assertIn("downloaded", content)


if __name__ == "__main__":
    unittest.main()
