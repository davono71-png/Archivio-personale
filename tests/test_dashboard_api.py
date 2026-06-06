import unittest
import tempfile
from pathlib import Path

from gmail_drive_archiver.dashboard_api import _anythingllm_search, _apply_single_review_move, _drive_folder_link, _review_payload, _scan_drive
from gmail_drive_archiver.inventory_analysis import InventoryItem


class DashboardApiTest(unittest.TestCase):
    def test_review_payload_maps_database_row_to_ui_shape(self) -> None:
        payload = _review_payload(
            {
                "id": "12",
                "document_name": "Bolletta Eni",
                "category": "Casa",
                "subcategory": "Utenze",
                "owner": "Davide",
                "suggested_visibility": "condiviso",
                "deadline": "2026-04-24",
                "confidence": "99",
                "review_status": "approved",
                "recommended_action": "Archivia",
                "reason": "Pagamento bolletta",
                "drive_file_id": "drive-1",
                "target_folder_id": "folder-1",
            }
        )

        self.assertEqual(payload["id"], "12")
        self.assertEqual(payload["title"], "Bolletta Eni")
        self.assertEqual(payload["visibility"], "condiviso")
        self.assertEqual(payload["confidence"], 99)
        self.assertEqual(payload["status"], "approved")
        self.assertEqual(payload["action"], "Archivia")

    def test_review_payload_adds_drive_link_from_inventory(self) -> None:
        payload = _review_payload(
            {
                "id": "12",
                "document_name": "Bolletta Eni.pdf",
                "category": "Casa",
                "confidence": "99",
                "review_status": "pending",
            },
            {
                "bolletta eni": InventoryItem(
                    id="drive-1",
                    name="Bolletta Eni.pdf",
                    mime_type="application/pdf",
                    web_view_link="https://drive.google.com/file/d/drive-1/view",
                )
            },
        )

        self.assertEqual(payload["driveFileId"], "drive-1")
        self.assertEqual(payload["driveLink"], "https://drive.google.com/file/d/drive-1/view")

    def test_review_payload_matches_exported_filename_by_drive_id(self) -> None:
        drive_id = "1xC1kTTSnm-NsQW5kk4I0U7BiS0rvEnl9"
        payload = _review_payload(
            {
                "id": "12",
                "document_name": f"Lavoro__Fornitura-{drive_id}.txt",
                "category": "Lavoro",
                "review_status": "pending",
            },
            {
                drive_id: InventoryItem(
                    id=drive_id,
                    name="Fornitura e posa in opera di cancello scorrevole Dim.docx",
                    mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    web_view_link=f"https://drive.google.com/file/d/{drive_id}/view",
                )
            },
        )

        self.assertEqual(payload["driveFileId"], drive_id)
        self.assertEqual(payload["driveLink"], f"https://drive.google.com/file/d/{drive_id}/view")

    def test_anythingllm_search_reports_missing_configuration(self) -> None:
        result = _anythingllm_search("http://anythingllm:3001", "", "", "test")

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "anythingllm_not_configured")

    def test_apply_single_review_requires_google_credentials(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            result = _apply_single_review_move(
                review_id=1,
                db_path=root / "state.sqlite3",
                inventory_path=root / "inventory.csv",
                drive_config_path=root / "drive.yml",
                credentials_path=root / "missing-credentials.json",
                token_path=root / "missing-token.json",
            )

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "missing_google_credentials")

    def test_scan_drive_requires_google_credentials(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            result = _scan_drive(
                inventory_path=root / "inventory.csv",
                drive_config_path=root / "drive.yml",
                categories_path=root / "categories.yml",
                credentials_path=root / "missing-credentials.json",
                token_path=root / "missing-token.json",
            )

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "missing_google_credentials")

    def test_drive_folder_link(self) -> None:
        self.assertEqual(
            _drive_folder_link("folder-123"),
            "https://drive.google.com/drive/folders/folder-123",
        )


if __name__ == "__main__":
    unittest.main()
