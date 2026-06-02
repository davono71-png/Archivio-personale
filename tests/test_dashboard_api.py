import unittest

from gmail_drive_archiver.dashboard_api import _review_payload
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


if __name__ == "__main__":
    unittest.main()
