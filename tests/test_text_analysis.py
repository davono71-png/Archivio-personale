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
        self.assertFalse(hasattr(analysis, "unclassified_count"))
        self.assertIn("bonifico.txt", text_analysis_to_json(analysis))

    def test_uses_filename_when_content_has_no_category_keywords(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            text_dir = Path(tmpdir)
            (text_dir / "timbrature_Tutti_2026_05-file123.txt").write_text(
                "08:00 12:00 13:00 17:00",
                encoding="utf-8",
            )

            analysis = analyze_text_directory(text_dir, ["Lavoro", "Varie"])

        self.assertEqual(analysis.category_counts["Lavoro"], 1)
        self.assertEqual(analysis.analyzed_files[0].best_category, "Lavoro")

    def test_does_not_match_keyword_inside_longer_word(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            text_dir = Path(tmpdir)
            (text_dir / "AUTOCERTIFICAZIONE-TITOLO-DI-STUDIO.txt").write_text(
                "Dichiaro sotto la mia responsabilita",
                encoding="utf-8",
            )

            analysis = analyze_text_directory(text_dir, ["Auto", "Varie"])

        self.assertNotIn("Auto", analysis.category_counts)
        self.assertEqual(len(analysis.unclassified_files), 1)

    def test_filename_has_priority_over_weaker_content_keywords(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            text_dir = Path(tmpdir)
            (text_dir / "TABELLA_GIORNATE_DI_LAVORO-file123.txt").write_text(
                "lunedi martedi mercoledi giovedi venerdi sabato domenica",
                encoding="utf-8",
            )
            (text_dir / "Garanzia_genitori-file456.txt").write_text(
                "documento con aliquota iva",
                encoding="utf-8",
            )

            analysis = analyze_text_directory(text_dir, ["Lavoro", "Alimentazione", "Garanzie", "Fisco"])
            by_name = {Path(item.path).name: item.best_category for item in analysis.analyzed_files}

        self.assertEqual(by_name["TABELLA_GIORNATE_DI_LAVORO-file123.txt"], "Lavoro")
        self.assertEqual(by_name["Garanzia_genitori-file456.txt"], "Garanzie")


if __name__ == "__main__":
    unittest.main()
