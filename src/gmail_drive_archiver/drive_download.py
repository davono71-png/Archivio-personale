from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass
from pathlib import Path

from .inventory_analysis import InventoryItem


GOOGLE_EXPORTS = {
    "application/vnd.google-apps.document": (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".docx",
    ),
    "application/vnd.google-apps.spreadsheet": (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".xlsx",
    ),
    "application/vnd.google-apps.presentation": (
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ".pptx",
    ),
    "application/vnd.google-apps.drawing": ("image/png", ".png"),
}


@dataclass(frozen=True)
class DownloadResult:
    item_id: str
    name: str
    status: str
    output_path: str = ""
    detail: str = ""


def download_inventory_files(
    service,
    items: list[InventoryItem],
    output_dir: Path,
    limit: int | None = None,
    skip_existing: bool = True,
) -> list[DownloadResult]:
    output_dir.mkdir(parents=True, exist_ok=True)
    results: list[DownloadResult] = []

    for item in items[:limit]:
        target = output_dir / download_filename(item)
        if skip_existing and target.exists():
            results.append(DownloadResult(item.id, item.name, "skipped_existing", str(target)))
            continue

        try:
            request = _download_request(service, item)
            if request is None:
                results.append(
                    DownloadResult(
                        item.id,
                        item.name,
                        "unsupported_google_file",
                        detail=item.mime_type,
                    )
                )
                continue

            _write_request_to_file(request, target)
        except Exception as exc:  # Google client raises transport-specific exceptions.
            results.append(DownloadResult(item.id, item.name, "error", detail=str(exc)))
            continue

        results.append(DownloadResult(item.id, item.name, "downloaded", str(target)))

    return results


def download_filename(item: InventoryItem) -> str:
    name = item.name.strip() or item.id
    suffix = _target_suffix(item)
    path = Path(name)
    stem = path.stem if path.suffix else name
    safe_stem = re.sub(r"[^A-Za-z0-9_.-]+", "_", stem).strip("._") or item.id
    return f"{safe_stem}-{item.id}{suffix}"


def write_download_report(results: list[DownloadResult], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["id", "name", "status", "output_path", "detail"])
        writer.writeheader()
        for result in results:
            writer.writerow(
                {
                    "id": result.item_id,
                    "name": result.name,
                    "status": result.status,
                    "output_path": result.output_path,
                    "detail": result.detail,
                }
            )


def _download_request(service, item: InventoryItem):  # type: ignore[no-untyped-def]
    if item.mime_type in GOOGLE_EXPORTS:
        export_mime_type, _extension = GOOGLE_EXPORTS[item.mime_type]
        return service.files().export_media(fileId=item.id, mimeType=export_mime_type)

    if item.mime_type.startswith("application/vnd.google-apps."):
        return None

    return service.files().get_media(fileId=item.id)


def _write_request_to_file(request, target: Path) -> None:  # type: ignore[no-untyped-def]
    from googleapiclient.http import MediaIoBaseDownload

    temp_target = target.with_suffix(target.suffix + ".part")
    with io.FileIO(temp_target, "wb") as handle:
        downloader = MediaIoBaseDownload(handle, request)
        done = False
        while not done:
            _status, done = downloader.next_chunk()
    temp_target.replace(target)


def _target_suffix(item: InventoryItem) -> str:
    if item.mime_type in GOOGLE_EXPORTS:
        return GOOGLE_EXPORTS[item.mime_type][1]

    suffix = Path(item.name).suffix
    if suffix:
        return suffix

    fallback = {
        "application/pdf": ".pdf",
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/tiff": ".tiff",
        "image/webp": ".webp",
        "text/csv": ".csv",
        "text/plain": ".txt",
        "text/html": ".html",
        "application/xml": ".xml",
        "text/xml": ".xml",
        "text/calendar": ".ics",
    }
    return fallback.get(item.mime_type, "")
