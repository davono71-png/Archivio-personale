from __future__ import annotations

import argparse
import json
import os
import re
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .config import load_split_config
from .database import ProcessedStore
from .drive import DriveInventory
from .drive_download import download_inventory_files, write_download_report
from .google_auth import authenticate, build_google_service
from .inventory_analysis import InventoryItem, load_inventory_csv
from .review_moves import apply_review_move, build_review_moves
from .text_analysis import analyze_text_directory
from .text_extraction import extract_inventory_text, write_extraction_report


DEFAULT_DB = Path("database") / "personal-archive.sqlite3"
DEFAULT_INVENTORY = Path("database") / "inventory-da-classificare.csv"
DEFAULT_DRIVE_CONFIG = Path("config") / "drive-folders.yml"
DEFAULT_CATEGORIES = Path("config") / "categories.yml"
DEFAULT_CREDENTIALS = Path("config") / "credentials.json"
DEFAULT_TOKEN = Path("database") / "token.json"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="API locale per dashboard archivio personale.")
    parser.add_argument("--host", default=os.getenv("DASHBOARD_API_HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.getenv("DASHBOARD_API_PORT", "8090")))
    parser.add_argument("--db", type=Path, default=Path(os.getenv("DASHBOARD_DB", str(DEFAULT_DB))))
    parser.add_argument(
        "--inventory",
        type=Path,
        default=Path(os.getenv("DASHBOARD_INVENTORY", str(DEFAULT_INVENTORY))),
        help="CSV inventory per associare review ai link Drive",
    )
    parser.add_argument("--drive-config", type=Path, default=Path(os.getenv("DASHBOARD_DRIVE_CONFIG", str(DEFAULT_DRIVE_CONFIG))))
    parser.add_argument("--categories", type=Path, default=Path(os.getenv("DASHBOARD_CATEGORIES", str(DEFAULT_CATEGORIES))))
    parser.add_argument("--credentials", type=Path, default=Path(os.getenv("DASHBOARD_CREDENTIALS", str(DEFAULT_CREDENTIALS))))
    parser.add_argument("--token", type=Path, default=Path(os.getenv("DASHBOARD_TOKEN", str(DEFAULT_TOKEN))))
    parser.add_argument("--anythingllm-base-url", default=os.getenv("ANYTHINGLLM_API_BASE", "http://anythingllm:3001"))
    parser.add_argument("--anythingllm-api-key", default=os.getenv("ANYTHINGLLM_API_KEY", ""))
    parser.add_argument("--anythingllm-workspace", default=os.getenv("ANYTHINGLLM_WORKSPACE", ""))
    return parser


def run_server(
    host: str,
    port: int,
    db_path: Path,
    inventory_path: Path,
    drive_config_path: Path,
    categories_path: Path,
    credentials_path: Path,
    token_path: Path,
    anythingllm_base_url: str,
    anythingllm_api_key: str,
    anythingllm_workspace: str,
) -> None:
    handler = _handler_factory(
        db_path,
        inventory_path,
        drive_config_path,
        categories_path,
        credentials_path,
        token_path,
        anythingllm_base_url,
        anythingllm_api_key,
        anythingllm_workspace,
    )
    server = ThreadingHTTPServer((host, port), handler)
    print(f"Dashboard API listening on http://{host}:{port} db={db_path} inventory={inventory_path}", flush=True)
    server.serve_forever()


def _handler_factory(
    db_path: Path,
    inventory_path: Path,
    drive_config_path: Path,
    categories_path: Path,
    credentials_path: Path,
    token_path: Path,
    anythingllm_base_url: str,
    anythingllm_api_key: str,
    anythingllm_workspace: str,
):
    class DashboardApiHandler(BaseHTTPRequestHandler):
        server_version = "PersonalArchiveDashboardAPI/0.1"

        def do_OPTIONS(self) -> None:  # noqa: N802
            self._send_empty(204)

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path == "/api/health":
                self._send_json({"ok": True})
                return
            if parsed.path == "/api/reviews":
                query = parse_qs(parsed.query)
                status = _first(query, "status")
                category = _first(query, "category")
                limit = int(_first(query, "limit") or "200")
                inventory_index = _load_inventory_index(inventory_path)
                with ProcessedStore(db_path) as store:
                    items = [_review_payload(item, inventory_index) for item in store.ai_review_items(status, category, limit)]
                self._send_json({"items": items})
                return
            if parsed.path == "/api/summary":
                with ProcessedStore(db_path) as store:
                    category_counts = dict(store.ai_review_counts_by_category())
                    action_counts = dict(store.ai_review_counts_by_action())
                    status_counts = dict(store.ai_review_status_counts())
                    total = sum(status_counts.values())
                self._send_json(
                    {
                        "total": total,
                        "category_counts": category_counts,
                        "action_counts": action_counts,
                        "status_counts": status_counts,
                    }
                )
                return
            if parsed.path == "/api/folders":
                config = load_split_config(None, drive_config_path, None)
                folders = {
                    category: {
                        "id": folder_id,
                        "url": _drive_folder_link(folder_id),
                    }
                    for category, folder_id in config.drive_settings.category_folders.items()
                }
                self._send_json({"folders": folders})
                return
            self._send_json({"error": "not_found"}, status=404)

        def do_POST(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path == "/api/reviews/status":
                try:
                    payload = self._read_json()
                    ids = [int(item) for item in payload.get("ids", [])]
                    status = str(payload.get("status", ""))
                    if status not in {"pending", "approved", "rejected"}:
                        self._send_json({"error": "invalid_status"}, status=400)
                        return
                    with ProcessedStore(db_path) as store:
                        updated = store.set_ai_review_status_by_ids(ids, status)
                    self._send_json({"updated": updated})
                except (ValueError, json.JSONDecodeError) as exc:
                    self._send_json({"error": str(exc)}, status=400)
                return
            if parsed.path == "/api/reviews/update":
                try:
                    payload = self._read_json()
                    review_id = int(payload.get("id"))
                    with ProcessedStore(db_path) as store:
                        updated = store.update_ai_review_fields(
                            review_id,
                            category=_optional_payload_value(payload, "category"),
                            owner=_optional_payload_value(payload, "owner"),
                            suggested_visibility=_optional_payload_value(payload, "visibility"),
                            recommended_action=_optional_payload_value(payload, "action"),
                        )
                    self._send_json({"updated": updated})
                except (TypeError, ValueError, json.JSONDecodeError) as exc:
                    self._send_json({"error": str(exc)}, status=400)
                return
            if parsed.path == "/api/reviews/apply":
                try:
                    payload = self._read_json()
                    review_id = int(payload.get("id"))
                    result = _apply_single_review_move(
                        review_id,
                        db_path,
                        inventory_path,
                        drive_config_path,
                        credentials_path,
                        token_path,
                    )
                    status = 200 if result.get("ok") else 400
                    self._send_json(result, status=status)
                except (TypeError, ValueError, json.JSONDecodeError) as exc:
                    self._send_json({"ok": False, "error": str(exc)}, status=400)
                return
            if parsed.path == "/api/search/ai":
                try:
                    payload = self._read_json()
                    query = str(payload.get("query", "")).strip()
                    if not query:
                        self._send_json({"ok": False, "error": "query_required"}, status=400)
                        return
                    result = _anythingllm_search(anythingllm_base_url, anythingllm_api_key, anythingllm_workspace, query)
                    status = 200 if result.get("ok") else 400
                    self._send_json(result, status=status)
                except (TypeError, ValueError, json.JSONDecodeError) as exc:
                    self._send_json({"ok": False, "error": str(exc)}, status=400)
                return
            if parsed.path == "/api/scan/drive":
                try:
                    result = _scan_drive(
                        inventory_path,
                        drive_config_path,
                        categories_path,
                        credentials_path,
                        token_path,
                    )
                    status = 200 if result.get("ok") else 400
                    self._send_json(result, status=status)
                except (OSError, json.JSONDecodeError) as exc:
                    self._send_json({"ok": False, "error": str(exc)}, status=400)
                return
            self._send_json({"error": "not_found"}, status=404)

        def log_message(self, format: str, *args) -> None:  # noqa: A002
            print(f"{self.address_string()} - {format % args}", flush=True)

        def _read_json(self) -> dict:
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length).decode("utf-8")
            return json.loads(body or "{}")

        def _send_json(self, payload: dict, status: int = 200) -> None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self._send_common_headers()
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _send_empty(self, status: int) -> None:
            self.send_response(status)
            self._send_common_headers()
            self.end_headers()

        def _send_common_headers(self) -> None:
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Cache-Control", "no-store")

    return DashboardApiHandler


def _review_payload(item: dict[str, str], inventory_index: dict[str, InventoryItem] | None = None) -> dict[str, object]:
    confidence = item.get("confidence", "")
    try:
        confidence_value: object = int(float(confidence)) if confidence else None
    except ValueError:
        confidence_value = confidence

    inventory_item = _find_inventory_item(item.get("document_name", ""), inventory_index or {})
    drive_file_id = item.get("drive_file_id", "") or (inventory_item.id if inventory_item else "")
    drive_link = inventory_item.web_view_link if inventory_item and inventory_item.web_view_link else _drive_link(drive_file_id)

    return {
        "id": item.get("id", ""),
        "title": item.get("document_name", ""),
        "category": item.get("category", ""),
        "subcategory": item.get("subcategory", ""),
        "owner": item.get("owner", "") or "Non chiaro",
        "visibility": item.get("suggested_visibility", "") or "privato",
        "deadline": item.get("deadline", ""),
        "confidence": confidence_value,
        "status": item.get("review_status", "pending"),
        "action": item.get("recommended_action", ""),
        "reason": item.get("reason", ""),
        "driveFileId": drive_file_id,
        "targetFolderId": item.get("target_folder_id", ""),
        "driveLink": drive_link,
        "source": "SQLite review AI",
    }


def _first(query: dict[str, list[str]], key: str) -> str | None:
    values = query.get(key)
    if not values:
        return None
    value = values[0]
    return value if value and value != "Tutti" and value != "Tutte" else None


def _optional_payload_value(payload: dict, key: str) -> str | None:
    if key not in payload:
        return None
    value = payload.get(key)
    return "" if value is None else str(value)


def _load_inventory_index(path: Path) -> dict[str, InventoryItem]:
    if not path.exists():
        return {}
    try:
        items = load_inventory_csv(path)
    except OSError:
        return {}
    index: dict[str, InventoryItem] = {}
    for item in items:
        for key in {item.id, _normalize_name(item.id), _normalize_name(item.name), _normalize_name(Path(item.name).stem)}:
            if key:
                index.setdefault(key, item)
    return index


def _find_inventory_item(document_name: str, inventory_index: dict[str, InventoryItem]) -> InventoryItem | None:
    for key in (document_name, _normalize_name(document_name), _normalize_name(Path(document_name).stem), *_possible_drive_ids(document_name)):
        if key in inventory_index:
            return inventory_index[key]
    for key, item in inventory_index.items():
        if len(key) >= 20 and key in document_name:
            return item
    return None


def _normalize_name(value: str) -> str:
    normalized = value.casefold()
    normalized = re.sub(r"\.[a-z0-9]{1,8}$", "", normalized)
    normalized = re.sub(r"[^0-9a-zà-öø-ÿ]+", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def _possible_drive_ids(value: str) -> list[str]:
    stem = Path(value).stem
    matches = re.findall(r"([A-Za-z0-9_-]{20,})", stem)
    keys: list[str] = []
    for match in matches:
        keys.append(match)
        keys.append(_normalize_name(match))
    return keys


def _drive_link(file_id: str) -> str:
    if not file_id:
        return ""
    return f"https://drive.google.com/file/d/{file_id}/view"


def _drive_folder_link(folder_id: str) -> str:
    if not folder_id:
        return ""
    return f"https://drive.google.com/drive/folders/{folder_id}"


def _scan_drive(
    inventory_path: Path,
    drive_config_path: Path,
    categories_path: Path,
    credentials_path: Path,
    token_path: Path,
) -> dict[str, object]:
    if not credentials_path.exists() or not token_path.exists():
        return {"ok": False, "error": "missing_google_credentials"}

    config = load_split_config(None, drive_config_path, categories_path)
    folder_id = config.drive_settings.inbox_folder_id
    if not folder_id:
        return {"ok": False, "error": "missing_inbox_folder"}

    credentials = authenticate(credentials_path, token_path)
    drive_service = build_google_service("drive", "v3", credentials)
    files = DriveInventory(drive_service).list_folder(folder_id, None)
    inventory_path.parent.mkdir(parents=True, exist_ok=True)
    _write_inventory_csv(files, inventory_path)

    inventory_items = load_inventory_csv(inventory_path)
    downloads_dir = Path("database") / "downloads"
    extracted_dir = Path("database") / "extracted-text"
    download_report = Path("database") / "download-report.csv"
    extract_report = Path("database") / "extract-text-report.csv"

    download_results = download_inventory_files(drive_service, inventory_items, downloads_dir)
    write_download_report(download_results, download_report)
    extraction_results = extract_inventory_text(inventory_items, downloads_dir, extracted_dir)
    write_extraction_report(extraction_results, extract_report)
    analysis = analyze_text_directory(extracted_dir, config.categories)

    return {
        "ok": True,
        "inventory_count": len(files),
        "download_counts": _count_statuses([result.status for result in download_results]),
        "extract_counts": _count_statuses([result.status for result in extraction_results]),
        "category_counts": analysis.category_counts,
        "unclassified_count": analysis.unclassified_count,
    }


def _write_inventory_csv(files: list[dict], path: Path) -> None:
    import csv

    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["id", "name", "mime_type", "size", "created_time", "modified_time", "web_view_link"],
        )
        writer.writeheader()
        for file in files:
            writer.writerow(
                {
                    "id": file.get("id", ""),
                    "name": file.get("name", ""),
                    "mime_type": file.get("mimeType", ""),
                    "size": file.get("size", ""),
                    "created_time": file.get("createdTime", ""),
                    "modified_time": file.get("modifiedTime", ""),
                    "web_view_link": file.get("webViewLink", ""),
                }
            )


def _count_statuses(statuses: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for status in statuses:
        counts[status] = counts.get(status, 0) + 1
    return counts


def _apply_single_review_move(
    review_id: int,
    db_path: Path,
    inventory_path: Path,
    drive_config_path: Path,
    credentials_path: Path,
    token_path: Path,
) -> dict[str, object]:
    if not credentials_path.exists() or not token_path.exists():
        return {"ok": False, "error": "missing_google_credentials"}

    inventory_items = load_inventory_csv(inventory_path)
    config = load_split_config(None, drive_config_path, None)
    with ProcessedStore(db_path) as store:
        review = store.ai_review_item_by_id(review_id)
        if not review:
            return {"ok": False, "error": "review_not_found"}
        store.set_ai_review_status_by_ids([review_id], "approved")
        review["review_status"] = "approved"
        moves = build_review_moves([review], inventory_items, config.drive_settings.category_folders)
        move = moves[0] if moves else None
        if not move or move.status != "planned":
            return {
                "ok": False,
                "error": move.status if move else "no_move",
                "detail": move.detail if move else "",
            }
        credentials = authenticate(credentials_path, token_path)
        drive_service = build_google_service("drive", "v3", credentials)
        apply_review_move(drive_service, move)
        store.mark_ai_review_applied(move.review_id, move.drive_file_id, move.target_folder_id)
        return {
            "ok": True,
            "move": {
                "review_id": move.review_id,
                "document_name": move.document_name,
                "drive_file_id": move.drive_file_id,
                "drive_name": move.drive_name,
                "category": move.category,
                "target_folder_id": move.target_folder_id,
            },
        }


def _anythingllm_search(base_url: str, api_key: str, workspace: str, query: str) -> dict[str, object]:
    if not api_key or not workspace:
        return {
            "ok": False,
            "error": "anythingllm_not_configured",
            "answer": "Configura ANYTHINGLLM_API_KEY e ANYTHINGLLM_WORKSPACE per usare la ricerca AI dalla dashboard.",
        }
    url = f"{base_url.rstrip('/')}/api/v1/workspace/{workspace}/chat"
    payload = json.dumps({"message": query, "mode": "query"}).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return {"ok": False, "error": "anythingllm_request_failed", "detail": str(exc)}

    answer = data.get("textResponse") or data.get("response") or data.get("answer") or json.dumps(data, ensure_ascii=False)
    return {"ok": True, "answer": answer, "raw": data}


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    run_server(
        args.host,
        args.port,
        args.db,
        args.inventory,
        args.drive_config,
        args.categories,
        args.credentials,
        args.token,
        args.anythingllm_base_url,
        args.anythingllm_api_key,
        args.anythingllm_workspace,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
