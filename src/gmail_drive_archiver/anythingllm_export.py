from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from .inventory_analysis import InventoryItem
from .text_analysis import TextAnalysis


@dataclass(frozen=True)
class AnythingLlmExportResult:
    exported_count: int
    manifest_path: str
    output_dir: str


def export_anythingllm_package(
    inventory_items: list[InventoryItem],
    analysis: TextAnalysis,
    output_dir: Path,
) -> AnythingLlmExportResult:
    output_dir.mkdir(parents=True, exist_ok=True)
    by_id = {item.id: item for item in inventory_items}
    manifest_path = output_dir / "manifest.jsonl"
    exported = 0

    with manifest_path.open("w", encoding="utf-8") as manifest:
        for text_file in analysis.analyzed_files:
            text_path = Path(text_file.path)
            item_id = _item_id_from_text_path(text_path, by_id)
            item = by_id.get(item_id) if item_id else None
            content = text_path.read_text(encoding="utf-8", errors="replace").strip()
            category = text_file.best_category or "Da classificare"
            target_path = output_dir / _export_filename(text_path, item, category)
            enriched = _enriched_document(content, text_file.path, item, category)
            target_path.write_text(enriched, encoding="utf-8")
            manifest.write(
                json.dumps(
                    {
                        "source_text_path": text_file.path,
                        "export_path": str(target_path),
                        "drive_id": item.id if item else item_id,
                        "original_name": item.name if item else text_path.name,
                        "suggested_category": category,
                        "drive_link": item.web_view_link if item else "",
                        "word_count": text_file.word_count,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
            exported += 1

    return AnythingLlmExportResult(
        exported_count=exported,
        manifest_path=str(manifest_path),
        output_dir=str(output_dir),
    )


def _item_id_from_text_path(text_path: Path, by_id: dict[str, InventoryItem]) -> str | None:
    stem = text_path.stem
    for item_id in by_id:
        if stem.endswith(f"-{item_id}"):
            return item_id
    return None


def _export_filename(text_path: Path, item: InventoryItem | None, category: str) -> str:
    original_name = item.name if item else text_path.stem
    stem = Path(original_name).stem
    safe_category = _safe_name(category)
    safe_stem = _safe_name(stem)
    drive_id = f"-{item.id}" if item else ""
    return f"{safe_category}__{safe_stem}{drive_id}.txt"


def _enriched_document(
    content: str,
    source_text_path: str,
    item: InventoryItem | None,
    category: str,
) -> str:
    metadata = [
        "---",
        f"suggested_category: {category}",
        f"original_name: {item.name if item else Path(source_text_path).name}",
        f"drive_id: {item.id if item else ''}",
        f"drive_link: {item.web_view_link if item else ''}",
        f"mime_type: {item.mime_type if item else ''}",
        f"modified_time: {item.modified_time if item else ''}",
        f"source_text_path: {source_text_path}",
        "---",
        "",
    ]
    return "\n".join(metadata) + content + "\n"


def _safe_name(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._")
    return safe or "senza_nome"
