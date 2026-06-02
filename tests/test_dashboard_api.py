import unittest

from gmail_drive_archiver.dashboard_api import _review_payload


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


if __name__ == "__main__":
    unittest.main()
