import tempfile
import unittest
from pathlib import Path

from gmail_drive_archiver.inventory_analysis import analyze_inventory, load_inventory_csv


class InventoryAnalysisTest(unittest.TestCase):
    def test_loads_inventory_csv_and_counts_file_types(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            inventory = Path(tmpdir) / "inventory.csv"
            inventory.write_text(
                "\n".join(
                    [
                        "id,name,mime_type,size,created_time,modified_time,web_view_link",
                        "1,Bonifico_2024.pdf,application/pdf,100,,,",
                        "2,Documento_sanitario.pdf,application/pdf,200,,,",
                        "3,allenamento_ciclismo.docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document,300,,,",
                        "4,timbrature_Tutti_2026_05.csv,text/csv,400,,,",
                        "5,Menu_Settimana2_Gourmet.pdf,application/pdf,500,,,",
                        "6,sconosciuto,,600,,,",
                    ]
                ),
                encoding="utf-8",
            )

            items = load_inventory_csv(inventory)
            analysis = analyze_inventory(
                items,
                ["Banca", "Salute", "Sport", "Lavoro", "Alimentazione", "Varie"],
            )

        self.assertEqual(analysis.total_items, 6)
        self.assertEqual(analysis.extensions["pdf"], 3)
        self.assertEqual(analysis.extensions["docx"], 1)
        self.assertEqual(analysis.mime_types["application/pdf"], 3)
        self.assertEqual(
            {guess.category for guess in analysis.categories},
            {"Banca", "Salute", "Sport", "Lavoro", "Alimentazione"},
        )
        self.assertEqual(analysis.unclassified_count, 1)


if __name__ == "__main__":
    unittest.main()
