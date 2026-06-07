from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .inventory_analysis import InventoryItem


@dataclass(frozen=True)
class ReviewMove:
    review_id: int
    document_name: str
    category: str
    drive_file_id: str = ""
    drive_name: str = ""
    target_folder_id: str = ""
    status: str = "planned"
    detail: str = ""


def build_review_moves(
    review_items: list[dict[str, str]],
    inventory_items: list[InventoryItem],
    category_folders: dict[str, str],
) -> list[ReviewMove]:
    index = _inventory_index(inventory_items)
    moves: list[ReviewMove] = []

    for review in review_items:
        review_id = int(review["id"])
        document_name = review["document_name"]
        category = review["category"]
        target_folder_id = category_folders.get(category, "")
        if not target_folder_id:
            moves.append(
                ReviewMove(
                    review_id=review_id,
                    document_name=document_name,
                    category=category,
                    status="missing_target_folder",
                    detail=f"nessuna cartella configurata per categoria {category}",
                )
            )
            continue

        matches = _match_inventory_items(document_name, index)
        if not matches:
            moves.append(
                ReviewMove(
                    review_id=review_id,
                    document_name=document_name,
                    category=category,
                    target_folder_id=target_folder_id,
                    status="not_found",
                    detail="documento non trovato nell'inventario",
                )
            )
            continue
        if len(matches) > 1:
            moves.append(
                ReviewMove(
                    review_id=review_id,
                    document_name=document_name,
                    category=category,
                    target_folder_id=target_folder_id,
                    status="ambiguous",
                    detail=f"{len(matches)} possibili corrispondenze",
                )
            )
            continue

        item = matches[0]
        moves.append(
            ReviewMove(
                review_id=review_id,
                document_name=document_name,
                category=category,
                drive_file_id=item.id,
                drive_name=item.name,
                target_folder_id=target_folder_id,
                status="planned",
            )
        )

    return moves


def apply_review_move(service, move: ReviewMove) -> None:  # type: ignore[no-untyped-def]
    file = service.files().get(fileId=move.drive_file_id, fields="id, name, parents").execute()
    parents = ",".join(file.get("parents", [])) or None
    service.files().update(
        fileId=move.drive_file_id,
        addParents=move.target_folder_id,
        removeParents=parents,
        fields="id, parents",
    ).execute()


def _inventory_index(inventory_items: list[InventoryItem]) -> dict[str, list[InventoryItem]]:
    index: dict[str, list[InventoryItem]] = {}
    for item in inventory_items:
        keys = {
            item.id,
            _normalize_name(item.id),
            _normalize_name(item.name),
            _normalize_name(Path(item.name).stem),
        }
        for key in keys:
            if key:
                index.setdefault(key, []).append(item)
    return index


def _match_inventory_items(document_name: str, index: dict[str, list[InventoryItem]]) -> list[InventoryItem]:
    keys = [
        document_name,
        _normalize_name(document_name),
        _normalize_name(Path(document_name).stem),
        *_possible_drive_ids(document_name),
    ]
    for key in keys:
        if key in index:
            return index[key]
    for key, matches in index.items():
        if len(key) >= 20 and key in document_name:
            return matches
    return []


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
