from __future__ import annotations

from collections.abc import Iterator

from .config import DriveRule
from .database import ProcessedStore
from .models import ActionResult


class DriveArchiver:
    def __init__(self, service, store: ProcessedStore) -> None:
        self.service = service
        self.store = store

    def process_rule(self, rule: DriveRule, dry_run: bool = False) -> list[ActionResult]:
        results: list[ActionResult] = []

        for file in self._iter_files(rule.query, rule.max_items):
            file_id = file["id"]
            if self.store.is_processed("drive", file_id, rule.name):
                results.append(
                    ActionResult(
                        service="drive",
                        item_id=file_id,
                        rule_name=rule.name,
                        action="move",
                        dry_run=dry_run,
                        skipped=True,
                        detail="gia processato",
                    )
                )
                continue

            parents = file.get("parents", [])
            remove_parents = ",".join(parents) if rule.remove_from_current_parents else None

            if not dry_run:
                self.service.files().update(
                    fileId=file_id,
                    addParents=rule.target_folder_id,
                    removeParents=remove_parents,
                    fields="id, parents",
                ).execute()
                self.store.mark_processed("drive", file_id, rule.name, "move")
                self.store.record_drive_file(
                    file_id=file_id,
                    original_name=file.get("name"),
                    current_name=file.get("name"),
                    status="moved",
                    drive_folder_id=rule.target_folder_id,
                )

            detail = f"name={file.get('name', '')}, target_folder_id={rule.target_folder_id}"
            results.append(
                ActionResult(
                    service="drive",
                    item_id=file_id,
                    rule_name=rule.name,
                    action="move",
                    dry_run=dry_run,
                    detail=detail,
                )
            )

        return results

    def _iter_files(self, query: str, max_items: int | None) -> Iterator[dict]:
        emitted = 0
        page_token = None

        while True:
            page_size = min(1000, max_items - emitted) if max_items else 1000
            response = (
                self.service.files()
                .list(
                    q=query,
                    spaces="drive",
                    fields="nextPageToken, files(id, name, mimeType, parents, modifiedTime)",
                    pageSize=page_size,
                    pageToken=page_token,
                )
                .execute()
            )

            for file in response.get("files", []):
                yield file
                emitted += 1
                if max_items and emitted >= max_items:
                    return

            page_token = response.get("nextPageToken")
            if not page_token:
                return
