import tempfile
import unittest
from pathlib import Path

from gmail_drive_archiver.inventory_analysis import InventoryItem
from gmail_drive_archiver.text_extraction import extract_inventory_text, write_extraction_report


class TextExtractionTest(unittest.TestCase):
    def test_extracts_text_files_and_reports_missing_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            files_dir = root / "downloads"
            output_dir = root / "extracted"
            files_dir.mkdir()
            (files_dir / "note.txt").write_text("contenuto utile", encoding="utf-8")

            results = extract_inventory_text(
                [
                    InventoryItem(id="1", name="note.txt", mime_type="text/plain"),
                    InventoryItem(id="2", name="manca.pdf", mime_type="application/pdf"),
                ],
                files_dir,
                output_dir,
            )

            self.assertEqual(results[0].status, "extracted")
            self.assertEqual(results[1].status, "missing_local_file")
            self.assertIn("contenuto utile", Path(results[0].output_path).read_text(encoding="utf-8"))

    def test_marks_images_as_requiring_ocr(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            files_dir = root / "downloads"
            output_dir = root / "extracted"
            files_dir.mkdir()
            (files_dir / "foto.jpg").write_bytes(b"not really an image")

            results = extract_inventory_text(
                [InventoryItem(id="1", name="foto.jpg", mime_type="image/jpeg")],
                files_dir,
                output_dir,
            )

            self.assertEqual(results[0].status, "requires_ocr")

    def test_finds_files_saved_with_download_inventory_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            files_dir = root / "downloads"
            output_dir = root / "extracted"
            files_dir.mkdir()
            (files_dir / "timbrature_Tutti_2026_05-file123.csv").write_text("ore,8", encoding="utf-8")

            results = extract_inventory_text(
                [InventoryItem(id="file123", name="timbrature_Tutti_2026_05.csv", mime_type="text/csv")],
                files_dir,
                output_dir,
            )

            self.assertEqual(results[0].status, "extracted")
            self.assertIn("ore,8", Path(results[0].output_path).read_text(encoding="utf-8"))

    def test_writes_extraction_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            report = Path(tmpdir) / "report.csv"
            files_dir = Path(tmpdir) / "downloads"
            output_dir = Path(tmpdir) / "extracted"
            files_dir.mkdir()
            (files_dir / "note.txt").write_text("abc", encoding="utf-8")

            results = extract_inventory_text(
                [InventoryItem(id="1", name="note.txt", mime_type="text/plain")],
                files_dir,
                output_dir,
            )
            write_extraction_report(results, report)

            self.assertIn("note.txt", report.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
