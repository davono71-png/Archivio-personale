import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from gmail_drive_archiver.ai_review import parse_ai_review_markdown, write_ai_review
from gmail_drive_archiver.database import ProcessedStore


class AiReviewTest(unittest.TestCase):
    def test_parses_markdown_table(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            review_path = Path(tmpdir) / "review.md"
            review_path.write_text(
                """
| Nome Documento | Categoria | Azione Consigliata | Motivo |
| --- | --- | --- | --- |
| POS_pagina_iniziale.docx | Lavoro | Inserire firma | Documento operativo |
| Bolletta Eni | Casa | Pagamento entro scadenza | Importo totale presente |
""",
                encoding="utf-8",
            )

            items = parse_ai_review_markdown(review_path)

        self.assertEqual(len(items), 2)
        self.assertEqual(items[0].document_name, "POS_pagina_iniziale.docx")
        self.assertEqual(items[0].category, "Lavoro")
        self.assertEqual(items[1].recommended_action, "Pagamento entro scadenza")

    def test_writes_json_and_csv_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            review_path = Path(tmpdir) / "review.md"
            json_path = Path(tmpdir) / "review.json"
            csv_path = Path(tmpdir) / "review.csv"
            review_path.write_text(
                """
| Nome documento | Categoria principale | Sottocategoria proposta | Proprietario probabile | Data rilevante | Scadenza | Azione consigliata | Duplicato di | Confidenza | Motivo sintetico |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| Garanzia Onofri & C.doc | Garanzie | Fideiussione Affitto | Famiglia | Non presente | Non presente | Archivia | | 100 | Atto di fideiussione |
""",
                encoding="utf-8",
            )
            items = parse_ai_review_markdown(review_path)

            write_ai_review(items, json_path, "json")
            write_ai_review(items, csv_path, "csv")

            payload = json.loads(json_path.read_text(encoding="utf-8"))
            csv_content = csv_path.read_text(encoding="utf-8")

        self.assertEqual(payload[0]["subcategory"], "Fideiussione Affitto")
        self.assertIn("Garanzia Onofri", csv_content)

    def test_records_ai_review_items_in_database(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "state.sqlite3"
            with ProcessedStore(db_path) as store:
                store.record_ai_review_item(
                    document_name="Bolletta Eni",
                    category="Casa",
                    subcategory="Bolletta Energia",
                    owner="Famiglia",
                    relevant_date="2026-04-23",
                    deadline="2026-04-24",
                    recommended_action="Archivia",
                    duplicate_of="",
                    confidence="100",
                    reason="Promemoria bolletta",
                    source_path="review.md",
                )

            connection = sqlite3.connect(db_path)
            try:
                row = connection.execute(
                    "SELECT category, recommended_action, review_status FROM ai_review_items WHERE document_name = ?",
                    ("Bolletta Eni",),
                ).fetchone()
            finally:
                connection.close()

        self.assertEqual(row, ("Casa", "Archivia", "pending"))

    def test_summarizes_ai_review_items(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "state.sqlite3"
            with ProcessedStore(db_path) as store:
                store.record_ai_review_item(
                    document_name="Bolletta Eni",
                    category="Casa",
                    subcategory="Bolletta Energia",
                    owner="Famiglia",
                    relevant_date="",
                    deadline="",
                    recommended_action="Archivia",
                    duplicate_of="",
                    confidence="100",
                    reason="Promemoria bolletta",
                    source_path="review.md",
                )
                store.record_ai_review_item(
                    document_name="POS.docx",
                    category="Lavoro",
                    subcategory="Sicurezza",
                    owner="Azienda/Lavoro",
                    relevant_date="",
                    deadline="",
                    recommended_action="Da verificare",
                    duplicate_of="",
                    confidence="90",
                    reason="Documento operativo",
                    source_path="review.md",
                )

                categories = store.ai_review_counts_by_category()
                actions = store.ai_review_counts_by_action()
                latest = store.latest_ai_review_items(limit=1)

        self.assertEqual(dict(categories), {"Casa": 1, "Lavoro": 1})
        self.assertEqual(dict(actions), {"Archivia": 1, "Da verificare": 1})
        self.assertEqual(len(latest), 1)
        self.assertEqual(latest[0]["document_name"], "POS.docx")
        self.assertEqual(latest[0]["review_status"], "pending")

    def test_sets_ai_review_status_and_lists_items_by_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "state.sqlite3"
            with ProcessedStore(db_path) as store:
                store.record_ai_review_item(
                    document_name="POS.docx",
                    category="Lavoro",
                    subcategory="Sicurezza",
                    owner="Azienda/Lavoro",
                    relevant_date="",
                    deadline="",
                    recommended_action="Archivia",
                    duplicate_of="",
                    confidence="99",
                    reason="Documento operativo",
                    source_path="review.md",
                )

                updated = store.set_ai_review_status(status="approved", category="Lavoro", min_confidence=95)
                approved = store.ai_review_items_for_status("approved")

        self.assertEqual(updated, 1)
        self.assertEqual(len(approved), 1)
        self.assertEqual(approved[0]["document_name"], "POS.docx")

    def test_marks_ai_review_as_applied(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "state.sqlite3"
            with ProcessedStore(db_path) as store:
                store.record_ai_review_item(
                    document_name="POS.docx",
                    category="Lavoro",
                    subcategory="Sicurezza",
                    owner="Azienda/Lavoro",
                    relevant_date="",
                    deadline="",
                    recommended_action="Archivia",
                    duplicate_of="",
                    confidence="99",
                    reason="Documento operativo",
                    source_path="review.md",
                )
                updated = store.set_ai_review_status(status="approved")
                approved = store.ai_review_items_for_status("approved")
                store.mark_ai_review_applied(int(approved[0]["id"]), "drive-1", "folder-1")
                applied = store.ai_review_items_for_status("applied")

        self.assertEqual(updated, 1)
        self.assertEqual(applied[0]["drive_file_id"], "drive-1")
        self.assertEqual(applied[0]["target_folder_id"], "folder-1")


if __name__ == "__main__":
    unittest.main()
