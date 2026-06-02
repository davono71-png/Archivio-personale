import unittest

from gmail_drive_archiver.inventory_analysis import InventoryItem
from gmail_drive_archiver.review_moves import build_review_moves


class ReviewMovesTest(unittest.TestCase):
    def test_builds_planned_move_for_matching_inventory_item(self) -> None:
        moves = build_review_moves(
            [
                {
                    "id": "7",
                    "document_name": "POS_pagina_iniziale.docx",
                    "category": "Lavoro",
                }
            ],
            [
                InventoryItem(
                    id="drive-1",
                    name="POS_pagina_iniziale.docx",
                    mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            ],
            {"Lavoro": "folder-work"},
        )

        self.assertEqual(moves[0].status, "planned")
        self.assertEqual(moves[0].drive_file_id, "drive-1")
        self.assertEqual(moves[0].target_folder_id, "folder-work")

    def test_blocks_missing_target_folder(self) -> None:
        moves = build_review_moves(
            [{"id": "7", "document_name": "Bolletta.pdf", "category": "Casa"}],
            [InventoryItem(id="drive-1", name="Bolletta.pdf", mime_type="application/pdf")],
            {},
        )

        self.assertEqual(moves[0].status, "missing_target_folder")

    def test_blocks_unmatched_and_ambiguous_documents(self) -> None:
        unmatched = build_review_moves(
            [{"id": "1", "document_name": "Non esiste.pdf", "category": "Casa"}],
            [InventoryItem(id="drive-1", name="Bolletta.pdf", mime_type="application/pdf")],
            {"Casa": "folder-home"},
        )
        ambiguous = build_review_moves(
            [{"id": "2", "document_name": "Bolletta.pdf", "category": "Casa"}],
            [
                InventoryItem(id="drive-1", name="Bolletta.pdf", mime_type="application/pdf"),
                InventoryItem(id="drive-2", name="Bolletta.pdf", mime_type="application/pdf"),
            ],
            {"Casa": "folder-home"},
        )

        self.assertEqual(unmatched[0].status, "not_found")
        self.assertEqual(ambiguous[0].status, "ambiguous")

    def test_matches_exported_anythingllm_filename_by_drive_id(self) -> None:
        drive_id = "1xC1kTTSnm-NsQW5kk4I0U7BiS0rvEnl9"
        moves = build_review_moves(
            [
                {
                    "id": "9",
                    "document_name": f"Lavoro__Fornitura_e_posa_in_opera_di_cancello-{drive_id}.txt",
                    "category": "Lavoro",
                }
            ],
            [
                InventoryItem(
                    id=drive_id,
                    name="Fornitura e posa in opera di cancello scorrevole Dim.docx",
                    mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            ],
            {"Lavoro": "folder-work"},
        )

        self.assertEqual(moves[0].status, "planned")
        self.assertEqual(moves[0].drive_file_id, drive_id)


if __name__ == "__main__":
    unittest.main()
