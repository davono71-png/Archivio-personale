import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from gmail_drive_archiver.ai_review import AiReviewItem, normalize_ai_review_item, parse_ai_review_markdown, write_ai_review
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
| Nome documento | Categoria principale | Sottocategoria proposta | Proprietario probabile | Visibilita suggerita | Data rilevante | Scadenza | Azione consigliata | Duplicato di | Confidenza | Motivo sintetico |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| Garanzia Onofri & C.doc | Garanzie | Fideiussione Affitto | Davide | condiviso | Non presente | Non presente | Archivia | | 100 | Atto di fideiussione |
""",
                encoding="utf-8",
            )
            items = parse_ai_review_markdown(review_path)

            write_ai_review(items, json_path, "json")
            write_ai_review(items, csv_path, "csv")

            payload = json.loads(json_path.read_text(encoding="utf-8"))
            csv_content = csv_path.read_text(encoding="utf-8")

        self.assertEqual(payload[0]["subcategory"], "Fideiussione Affitto")
        self.assertEqual(payload[0]["suggested_visibility"], "condiviso")
        self.assertIn("Garanzia Onofri", csv_content)

    def test_normalizes_ai_categories_and_owners(self) -> None:
        cases = [
            (
                AiReviewItem(
                    document_name="524508270106_2024_s.pdf",
                    category="Banca",
                    subcategory="Bolletta gas",
                    owner="Tommaso",
                    reason="Bolletta gas intestata a Davide Onofri",
                ),
                ("Casa", "Davide", "privato"),
            ),
            (
                AiReviewItem(
                    document_name="dichiarazione_iva.pdf",
                    category="Banca",
                    subcategory="Documento fiscale",
                    owner="Ester",
                    reason="Documento Agenzia Entrate con IVA",
                ),
                ("Fisco", "Davide", "privato"),
            ),
            (
                AiReviewItem(
                    document_name="appunti_game_design.pdf",
                    category="Game design",
                    owner="Non chiaro",
                    suggested_visibility="condiviso",
                    reason="Appunti didattici",
                ),
                ("Varie", "Non chiaro", "condiviso"),
            ),
            (
                AiReviewItem(
                    document_name="estratto_conto.pdf",
                    category="Casa",
                    owner="Ralitza",
                    reason="Estratto conto e saldo",
                ),
                ("Banca", "Ralitza", "privato"),
            ),
        ]

        for item, expected in cases:
            normalized = normalize_ai_review_item(item)
            self.assertEqual(
                (normalized.category, normalized.owner, normalized.suggested_visibility),
                expected,
            )

    def test_records_ai_review_items_in_database(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "state.sqlite3"
            with ProcessedStore(db_path) as store:
                store.record_ai_review_item(
                    document_name="Bolletta Eni",
                    category="Casa",
                    subcategory="Bolletta Energia",
                    owner="Davide",
                    suggested_visibility="condiviso",
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
                    owner="Davide",
                    suggested_visibility="condiviso",
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
                    owner="Davide",
                    suggested_visibility="condiviso",
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
                    owner="Davide",
                    suggested_visibility="condiviso",
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

    def test_sets_ai_review_status_by_ids_and_lists_all_reviews(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "state.sqlite3"
            with ProcessedStore(db_path) as store:
                store.record_ai_review_item(
                    document_name="POS.docx",
                    category="Lavoro",
                    subcategory="Sicurezza",
                    owner="Davide",
                    suggested_visibility="condiviso",
                    relevant_date="",
                    deadline="",
                    recommended_action="Archivia",
                    duplicate_of="",
                    confidence="99",
                    reason="Documento operativo",
                    source_path="review.md",
                )
                item = store.ai_review_items(limit=1)[0]
                updated = store.set_ai_review_status_by_ids([int(item["id"])], "approved")
                statuses = dict(store.ai_review_status_counts())
                approved = store.ai_review_items(status="approved", limit=10)

        self.assertEqual(updated, 1)
        self.assertEqual(statuses["approved"], 1)
        self.assertEqual(approved[0]["suggested_visibility"], "condiviso")

    def test_updates_ai_review_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "state.sqlite3"
            with ProcessedStore(db_path) as store:
                store.record_ai_review_item(
                    document_name="Documento.pdf",
                    category="Varie",
                    subcategory="",
                    owner="Non chiaro",
                    suggested_visibility="privato",
                    relevant_date="",
                    deadline="",
                    recommended_action="Da verificare",
                    duplicate_of="",
                    confidence="70",
                    reason="Test",
                    source_path="review.md",
                )
                item = store.ai_review_items(limit=1)[0]
                updated = store.update_ai_review_fields(
                    int(item["id"]),
                    category="Casa",
                    owner="Davide",
                    suggested_visibility="condiviso",
                    recommended_action="Archivia",
                )
                changed = store.ai_review_items(limit=1)[0]

        self.assertEqual(updated, 1)
        self.assertEqual(changed["category"], "Casa")
        self.assertEqual(changed["owner"], "Davide")
        self.assertEqual(changed["suggested_visibility"], "condiviso")
        self.assertEqual(changed["recommended_action"], "Archivia")

    def test_dedupes_ai_reviews_preserving_applied_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "state.sqlite3"
            with ProcessedStore(db_path) as store:
                for _ in range(2):
                    store.record_ai_review_item(
                        document_name="Documento.pdf",
                        category="Casa",
                        subcategory="",
                        owner="Davide",
                        suggested_visibility="privato",
                        relevant_date="",
                        deadline="",
                        recommended_action="Archivia",
                        duplicate_of="",
                        confidence="99",
                        reason="Test",
                        source_path="review.md",
                    )
                items = store.ai_review_items(limit=10)
                store.set_ai_review_status_by_ids([int(items[-1]["id"])], "applied")

                dry_run_duplicates = store.dedupe_ai_review_items(dry_run=True)
                all_before = store.ai_review_items(limit=10)
                applied_before = store.ai_review_items(status="applied", limit=10)
                duplicates = store.dedupe_ai_review_items(dry_run=False)
                all_after = store.ai_review_items(limit=10)
                applied_after = store.ai_review_items(status="applied", limit=10)

        self.assertEqual(len(dry_run_duplicates), 1)
        self.assertEqual(len(duplicates), 1)
        self.assertEqual(len(all_before), 2)
        self.assertEqual(len(all_after), 1)
        self.assertEqual(applied_before[0]["id"], applied_after[0]["id"])

    def test_updates_normalized_ai_review_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "state.sqlite3"
            with ProcessedStore(db_path) as store:
                store.record_ai_review_item(
                    document_name="bolletta gas.pdf",
                    category="Banca",
                    subcategory="Bolletta gas",
                    owner="Tommaso",
                    suggested_visibility="",
                    relevant_date="",
                    deadline="",
                    recommended_action="Archivia",
                    duplicate_of="",
                    confidence="99",
                    reason="Bolletta gas",
                    source_path="review.md",
                )
                item = store.ai_review_items(limit=1)[0]
                normalized = normalize_ai_review_item(
                    AiReviewItem(
                        document_name=item["document_name"],
                        category=item["category"],
                        subcategory=item["subcategory"],
                        owner=item["owner"],
                        suggested_visibility=item["suggested_visibility"],
                        reason=item["reason"],
                    )
                )
                store.update_ai_review_normalized_fields(
                    int(item["id"]),
                    normalized.category,
                    normalized.owner,
                    normalized.suggested_visibility,
                )
                updated = store.ai_review_items(limit=1)[0]

        self.assertEqual(updated["category"], "Casa")
        self.assertEqual(updated["owner"], "Davide")
        self.assertEqual(updated["suggested_visibility"], "privato")

    def test_marks_ai_review_as_applied(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "state.sqlite3"
            with ProcessedStore(db_path) as store:
                store.record_ai_review_item(
                    document_name="POS.docx",
                    category="Lavoro",
                    subcategory="Sicurezza",
                    owner="Davide",
                    suggested_visibility="condiviso",
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
