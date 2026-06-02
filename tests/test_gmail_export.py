import base64
import tempfile
import unittest
from pathlib import Path

from gmail_drive_archiver.gmail_export import export_gmail_message, extract_message_text, write_gmail_export_report


def encoded(value: str) -> str:
    return base64.urlsafe_b64encode(value.encode("utf-8")).decode("ascii").rstrip("=")


class GmailExportTest(unittest.TestCase):
    def test_extracts_plain_text_preferred_over_html(self) -> None:
        payload = {
            "mimeType": "multipart/alternative",
            "parts": [
                {"mimeType": "text/html", "body": {"data": encoded("<p>HTML</p>")}},
                {"mimeType": "text/plain", "body": {"data": encoded("Plain text")}},
            ],
        }

        self.assertEqual(extract_message_text(payload), "Plain text")

    def test_extracts_html_when_plain_text_is_missing(self) -> None:
        payload = {"mimeType": "text/html", "body": {"data": encoded("<p>Ciao<br>Davide</p>")}}

        self.assertIn("Ciao", extract_message_text(payload))
        self.assertIn("Davide", extract_message_text(payload))

    def test_exports_markdown_with_metadata(self) -> None:
        message = {
            "id": "msg-123",
            "payload": {
                "mimeType": "text/plain",
                "headers": [
                    {"name": "Subject", "value": "Bolletta giugno"},
                    {"name": "From", "value": "Enel <noreply@example.com>"},
                    {"name": "To", "value": "davide@example.com"},
                    {"name": "Date", "value": "Tue, 02 Jun 2026 10:00:00 +0000"},
                ],
                "body": {"data": encoded("Totale da pagare 42 euro")},
            },
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "email-text"
            result = export_gmail_message(message, "bollette", output_dir, "Davide", "privato")
            content = Path(result.output_path).read_text(encoding="utf-8")

        self.assertEqual(result.status, "exported")
        self.assertIn("source: gmail", content)
        self.assertIn("owner: Davide", content)
        self.assertIn("visibility: privato", content)
        self.assertIn("Totale da pagare", content)

    def test_writes_export_report(self) -> None:
        message = {
            "id": "msg-123",
            "payload": {
                "mimeType": "text/plain",
                "headers": [{"name": "Subject", "value": "Test"}],
                "body": {"data": encoded("Corpo")},
            },
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "email-text"
            report = Path(tmpdir) / "report.csv"
            result = export_gmail_message(message, "test", output_dir, "Davide", "privato")
            write_gmail_export_report([result], report)
            report_content = report.read_text(encoding="utf-8")

        self.assertIn("msg-123", report_content)
        self.assertIn("exported", report_content)


if __name__ == "__main__":
    unittest.main()
