from __future__ import annotations

import argparse
import json
import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .database import ProcessedStore
from .inventory_analysis import InventoryItem, load_inventory_csv


DEFAULT_DB = Path("database") / "personal-archive.sqlite3"
DEFAULT_INVENTORY = Path("database") / "inventory-da-classificare.csv"


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
    return parser


def run_server(host: str, port: int, db_path: Path, inventory_path: Path) -> None:
    handler = _handler_factory(db_path, inventory_path)
    server = ThreadingHTTPServer((host, port), handler)
    print(f"Dashboard API listening on http://{host}:{port} db={db_path} inventory={inventory_path}", flush=True)
    server.serve_forever()


def _handler_factory(db_path: Path, inventory_path: Path):
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


def _load_inventory_index(path: Path) -> dict[str, InventoryItem]:
    if not path.exists():
        return {}
    try:
        items = load_inventory_csv(path)
    except OSError:
        return {}
    index: dict[str, InventoryItem] = {}
    for item in items:
        for key in {_normalize_name(item.name), _normalize_name(Path(item.name).stem)}:
            if key:
                index.setdefault(key, item)
    return index


def _find_inventory_item(document_name: str, inventory_index: dict[str, InventoryItem]) -> InventoryItem | None:
    for key in (_normalize_name(document_name), _normalize_name(Path(document_name).stem)):
        if key in inventory_index:
            return inventory_index[key]
    return None


def _normalize_name(value: str) -> str:
    normalized = value.casefold()
    normalized = re.sub(r"\.[a-z0-9]{1,8}$", "", normalized)
    normalized = re.sub(r"[^0-9a-zà-öø-ÿ]+", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def _drive_link(file_id: str) -> str:
    if not file_id:
        return ""
    return f"https://drive.google.com/file/d/{file_id}/view"


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    run_server(args.host, args.port, args.db, args.inventory)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
