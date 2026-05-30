import unittest

from gmail_drive_archiver.inventory_analysis import InventoryItem
from gmail_drive_archiver.ocr_plan import build_ocr_plan


class OcrPlanTest(unittest.TestCase):
    def test_groups_inventory_items_by_processing_strategy(self) -> None:
        plan = build_ocr_plan(
            [
                InventoryItem(id="1", name="scansione.pdf", mime_type="application/pdf"),
                InventoryItem(id="2", name="foto.jpg", mime_type="image/jpeg"),
                InventoryItem(
                    id="3",
                    name="contratto.docx",
                    mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                ),
                InventoryItem(id="4", name="timbrature.csv", mime_type="text/csv"),
                InventoryItem(id="5", name="calendario.ics", mime_type="text/calendar"),
                InventoryItem(id="6", name="file-sconosciuto.bin", mime_type="application/octet-stream"),
            ]
        )

        counts = {bucket.key: bucket.count for bucket in plan.buckets}

        self.assertEqual(plan.total_items, 6)
        self.assertEqual(counts["ocr"], 2)
        self.assertEqual(counts["text_extract"], 1)
        self.assertEqual(counts["structured"], 1)
        self.assertEqual(counts["technical"], 1)
        self.assertEqual(counts["review"], 1)


if __name__ == "__main__":
    unittest.main()
