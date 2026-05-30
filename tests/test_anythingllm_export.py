import json
import tempfile
import unittest
from pathlib import Path

from gmail_drive_archiver.anythingllm_export import export_anythingllm_package
from gmail_drive_archiver.inventory_analysis import InventoryItem
from gmail_drive_archiver.text_analysis import analyze_text_directory


class AnythingLlmExportTest(unittest.TestCase):
    def test_exports_enriched_text_files_and_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            text_dir = root / "extracted"
            output_dir = root / "anythingllm"
            text_dir.mkdir()
            text_path = text_dir / "Bonifico_2024-file123.txt"
            text_path.write_text("Bonifico bancario pagamento", encoding="utf-8")
            inventory = [
                InventoryItem(
                    id="file123",
                    name="Bonifico 2024.pdf",
                    mime_type="application/pdf",
                    modified_time="2026-05-30T10:00:00Z",
                    web_view_link="https://drive.google.com/file/d/file123/view",
                )
            ]
            analysis = analyze_text_directory(text_dir, ["Banca", "Varie"])

            result = export_anythingllm_package(inventory, analysis, output_dir)

            manifest_lines = Path(result.manifest_path).read_text(encoding="utf-8").splitlines()
            manifest = json.loads(manifest_lines[0])
            exported = Path(manifest["export_path"]).read_text(encoding="utf-8")

        self.assertEqual(result.exported_count, 1)
        self.assertEqual(manifest["drive_id"], "file123")
        self.assertEqual(manifest["suggested_category"], "Banca")
        self.assertIn("suggested_category: Banca", exported)
        self.assertIn("Bonifico bancario pagamento", exported)


if __name__ == "__main__":
    unittest.main()
