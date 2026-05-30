import tempfile
import unittest
from pathlib import Path

from gmail_drive_archiver.text_analysis import analyze_text_directory, text_analysis_to_json


class TextAnalysisTest(unittest.TestCase):
    def test_analyzes_text_directory_by_content_keywords(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            text_dir = Path(tmpdir)
            (text_dir / "bonifico.txt").write_text(
                "Bonifico bancario pagamento conto corrente",
                encoding="utf-8",
            )
            (text_dir / "menu.txt").write_text(
                "Menu settimana spesa pasti gourmet",
                encoding="utf-8",
            )
            (text_dir / "unknown.txt").write_text(
                "contenuto senza parole utili",
                encoding="utf-8",
            )

            analysis = analyze_text_directory(text_dir, ["Banca", "Alimentazione", "Varie"])

        self.assertEqual(analysis.total_files, 3)
        self.assertEqual(analysis.category_counts["Banca"], 1)
        self.assertEqual(analysis.category_counts["Alimentazione"], 1)
        self.assertEqual(len(analysis.unclassified_files), 1)
        self.assertIn("bonifico.txt", text_analysis_to_json(analysis))


if __name__ == "__main__":
    unittest.main()
