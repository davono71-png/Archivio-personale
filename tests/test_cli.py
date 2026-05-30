import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from gmail_drive_archiver.cli import _write_inventory, _write_inventory_analysis, _write_ocr_plan
from gmail_drive_archiver.inventory_analysis import analyze_inventory, InventoryItem
from gmail_drive_archiver.ocr_plan import build_ocr_plan


class InventoryOutputTest(unittest.TestCase):
    def test_writes_json_inventory(self) -> None:
        files = [
            {
                "id": "file-1",
                "name": "documento.pdf",
                "mimeType": "application/pdf",
                "modifiedTime": "2026-05-30T10:00:00Z",
            }
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "inventory.json"
            _write_inventory(files, "json", output)

            payload = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(payload[0]["id"], "file-1")
        self.assertEqual(payload[0]["name"], "documento.pdf")
        self.assertEqual(payload[0]["mime_type"], "application/pdf")

    def test_prints_table_inventory(self) -> None:
        files = [
            {
                "id": "file-1",
                "name": "documento.pdf",
                "mimeType": "application/pdf",
                "modifiedTime": "2026-05-30T10:00:00Z",
            }
        ]

        output = io.StringIO()
        with redirect_stdout(output):
            _write_inventory(files, "table", None)

        self.assertIn("file-1", output.getvalue())
        self.assertIn("documento.pdf", output.getvalue())

    def test_prints_inventory_analysis(self) -> None:
        analysis = analyze_inventory(
            [
                InventoryItem(id="file-1", name="bonifico.pdf", mime_type="application/pdf"),
                InventoryItem(id="file-2", name="ricetta.pdf", mime_type="application/pdf"),
            ],
            ["Banca", "Salute"],
        )

        output = io.StringIO()
        with redirect_stdout(output):
            _write_inventory_analysis(analysis, "table", None)

        self.assertIn("Totale file: 2", output.getvalue())
        self.assertIn("Banca", output.getvalue())
        self.assertIn("Salute", output.getvalue())

    def test_prints_ocr_plan(self) -> None:
        plan = build_ocr_plan(
            [
                InventoryItem(id="file-1", name="scansione.pdf", mime_type="application/pdf"),
                InventoryItem(id="file-2", name="contratto.docx", mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
            ]
        )

        output = io.StringIO()
        with redirect_stdout(output):
            _write_ocr_plan(plan, "table", None)

        self.assertIn("Candidati OCR: 1", output.getvalue())
        self.assertIn("Documenti testuali: 1", output.getvalue())


if __name__ == "__main__":
    unittest.main()
