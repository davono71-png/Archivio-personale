from __future__ import annotations

import base64
import csv
import html
import re
from dataclasses import dataclass
from email.header import decode_header
from pathlib import Path

from .config import GmailRule
from .database import ProcessedStore


@dataclass(frozen=True)
class GmailExportResult:
    message_id: str
    rule_name: str
    status: str
    output_path: str = ""
    subject: str = ""
    sender: str = ""
    date: str = ""
    detail: str = ""


class GmailTextExporter:
    def __init__(self, service, store: ProcessedStore, user_id: str = "me") -> None:
        self.service = service
        self.store = store
        self.user_id = user_id

    def export_rule(
        self,
        rule: GmailRule,
        output_dir: Path,
        owner: str = "Davide",
        visibility: str = "privato",
        force: bool = False,
    ) -> list[GmailExportResult]:
        output_dir.mkdir(parents=True, exist_ok=True)
        results: list[GmailExportResult] = []

        for message in self._iter_messages(rule.query, rule.max_items):
            message_id = message["id"]
            if not force and self.store.is_processed("gmail_text", message_id, rule.name):
                results.append(GmailExportResult(message_id, rule.name, "skipped_existing"))
                continue

            full_message = (
                self.service.users()
                .messages()
                .get(userId=self.user_id, id=message_id, format="full")
                .execute()
            )
            exported = export_gmail_message(full_message, rule.name, output_dir, owner, visibility)
            self.store.mark_processed("gmail_text", message_id, rule.name, "export_text")
            self.store.record_email(message_id, rule.name, rule.query, "exported_text")
            results.append(exported)

        return results

    def _iter_messages(self, query: str, max_items: int | None):  # type: ignore[no-untyped-def]
        emitted = 0
        page_token = None

        while True:
            page_size = min(500, max_items - emitted) if max_items else 500
            response = (
                self.service.users()
                .messages()
                .list(
                    userId=self.user_id,
                    q=query,
                    maxResults=page_size,
                    pageToken=page_token,
                )
                .execute()
            )

            for message in response.get("messages", []):
                yield message
                emitted += 1
                if max_items and emitted >= max_items:
                    return

            page_token = response.get("nextPageToken")
            if not page_token:
                return


def export_gmail_message(
    message: dict,
    rule_name: str,
    output_dir: Path,
    owner: str,
    visibility: str,
) -> GmailExportResult:
    output_dir.mkdir(parents=True, exist_ok=True)
    message_id = message["id"]
    headers = _headers(message.get("payload", {}))
    subject = _decode_mime_header(headers.get("subject", "(senza oggetto)"))
    sender = _decode_mime_header(headers.get("from", ""))
    recipient = _decode_mime_header(headers.get("to", ""))
    date = headers.get("date", "")
    text = extract_message_text(message.get("payload", {})).strip()
    if not text:
        text = "(Nessun corpo testuale trovato.)"

    output_path = output_dir / f"{_safe_filename(date)}__{_safe_filename(subject)}__{message_id}.md"
    front_matter = [
        "---",
        "source: gmail",
        f"gmail_id: {message_id}",
        f"rule_name: {rule_name}",
        f"owner: {owner}",
        f"visibility: {visibility}",
        f"from: {sender}",
        f"to: {recipient}",
        f"date: {date}",
        f"subject: {subject}",
        "---",
        "",
        f"# {subject}",
        "",
        text,
        "",
    ]
    output_path.write_text("\n".join(front_matter), encoding="utf-8")
    return GmailExportResult(
        message_id=message_id,
        rule_name=rule_name,
        status="exported",
        output_path=str(output_path),
        subject=subject,
        sender=sender,
        date=date,
    )


def extract_message_text(payload: dict) -> str:
    plain_parts: list[str] = []
    html_parts: list[str] = []
    _collect_text_parts(payload, plain_parts, html_parts)
    if plain_parts:
        return "\n\n".join(part.strip() for part in plain_parts if part.strip())
    return "\n\n".join(_html_to_text(part).strip() for part in html_parts if part.strip())


def write_gmail_export_report(results: list[GmailExportResult], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["message_id", "rule_name", "status", "output_path", "subject", "sender", "date", "detail"],
        )
        writer.writeheader()
        for result in results:
            writer.writerow(result.__dict__)


def _collect_text_parts(payload: dict, plain_parts: list[str], html_parts: list[str]) -> None:
    mime_type = payload.get("mimeType", "")
    body = payload.get("body", {})
    data = body.get("data")
    if data and mime_type == "text/plain":
        plain_parts.append(_decode_body(data))
    elif data and mime_type == "text/html":
        html_parts.append(_decode_body(data))

    for part in payload.get("parts", []) or []:
        _collect_text_parts(part, plain_parts, html_parts)


def _decode_body(data: str) -> str:
    padded = data + "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8", errors="replace")


def _headers(payload: dict) -> dict[str, str]:
    return {item.get("name", "").casefold(): item.get("value", "") for item in payload.get("headers", [])}


def _decode_mime_header(value: str) -> str:
    decoded_parts: list[str] = []
    for part, encoding in decode_header(value):
        if isinstance(part, bytes):
            decoded_parts.append(part.decode(encoding or "utf-8", errors="replace"))
        else:
            decoded_parts.append(part)
    return "".join(decoded_parts)


def _html_to_text(value: str) -> str:
    value = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", value)
    value = re.sub(r"(?i)<br\s*/?>", "\n", value)
    value = re.sub(r"(?i)</p>", "\n\n", value)
    value = re.sub(r"<[^>]+>", " ", value)
    value = html.unescape(value)
    return re.sub(r"[ \t]+", " ", value)


def _safe_filename(value: str) -> str:
    value = value.strip() or "senza_nome"
    value = re.sub(r"[^A-Za-z0-9_.-]+", "_", value)
    return value.strip("._")[:90] or "senza_nome"
