from __future__ import annotations

from collections.abc import Iterator

from .config import GmailRule
from .database import ProcessedStore
from .models import ActionResult


class GmailArchiver:
    def __init__(self, service, store: ProcessedStore, user_id: str = "me") -> None:
        self.service = service
        self.store = store
        self.user_id = user_id
        self._label_cache: dict[str, str] = {}

    def process_rule(self, rule: GmailRule, dry_run: bool = False) -> list[ActionResult]:
        results: list[ActionResult] = []
        label_id = None if dry_run or not rule.label else self._ensure_label(rule.label)

        for message in self._iter_messages(rule.query, rule.max_items):
            message_id = message["id"]
            if self.store.is_processed("gmail", message_id, rule.name):
                results.append(
                    ActionResult(
                        service="gmail",
                        item_id=message_id,
                        rule_name=rule.name,
                        action="archive",
                        dry_run=dry_run,
                        skipped=True,
                        detail="gia processato",
                    )
                )
                continue

            if not dry_run:
                body = {"removeLabelIds": ["INBOX"], "addLabelIds": []}
                if rule.mark_read:
                    body["removeLabelIds"].append("UNREAD")
                if label_id:
                    body["addLabelIds"].append(label_id)
                self.service.users().messages().modify(
                    userId=self.user_id,
                    id=message_id,
                    body=body,
                ).execute()
                self.store.mark_processed("gmail", message_id, rule.name, "archive")

            detail = f"query={rule.query}"
            if rule.label:
                detail = f"{detail}, label={rule.label}"
            results.append(
                ActionResult(
                    service="gmail",
                    item_id=message_id,
                    rule_name=rule.name,
                    action="archive",
                    dry_run=dry_run,
                    detail=detail,
                )
            )

        return results

    def _iter_messages(self, query: str, max_items: int | None) -> Iterator[dict]:
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

    def _ensure_label(self, label_name: str) -> str:
        if label_name in self._label_cache:
            return self._label_cache[label_name]

        labels_response = self.service.users().labels().list(userId=self.user_id).execute()
        for label in labels_response.get("labels", []):
            if label.get("name") == label_name:
                self._label_cache[label_name] = label["id"]
                return label["id"]

        created = (
            self.service.users()
            .labels()
            .create(
                userId=self.user_id,
                body={
                    "name": label_name,
                    "labelListVisibility": "labelShow",
                    "messageListVisibility": "show",
                },
            )
            .execute()
        )
        self._label_cache[label_name] = created["id"]
        return created["id"]
