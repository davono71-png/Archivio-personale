from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from .inventory_analysis import InventoryItem


OCR_MIME_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/tiff",
    "image/webp",
    "image/bmp",
}

TEXT_MIME_TYPES = {
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
    "application/vnd.oasis.opendocument.text",
    "text/plain",
}

STRUCTURED_MIME_TYPES = {
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel",
    "text/csv",
}

TECHNICAL_MIME_TYPES = {
    "text/html",
    "application/xhtml+xml",
    "application/xml",
    "text/xml",
    "text/calendar",
}

OCR_EXTENSIONS = {"pdf", "jpg", "jpeg", "png", "tif", "tiff", "webp", "bmp"}
TEXT_EXTENSIONS = {"doc", "docx", "odt", "txt", "rtf"}
STRUCTURED_EXTENSIONS = {"xls", "xlsx", "csv", "ods"}
TECHNICAL_EXTENSIONS = {"xml", "html", "htm", "ics"}


@dataclass(frozen=True)
class OcrPlanBucket:
    key: str
    label: str
    count: int
    examples: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class OcrPlan:
    total_items: int
    buckets: list[OcrPlanBucket]


def build_ocr_plan(items: list[InventoryItem]) -> OcrPlan:
    grouped: dict[str, list[str]] = defaultdict(list)

    for item in items:
        grouped[_strategy_for(item)].append(item.name)

    buckets = [
        OcrPlanBucket(
            key=key,
            label=_strategy_label(key),
            count=len(names),
            examples=names[:8],
        )
        for key, names in grouped.items()
    ]
    buckets.sort(key=lambda bucket: _strategy_order(bucket.key))

    return OcrPlan(total_items=len(items), buckets=buckets)


def _strategy_for(item: InventoryItem) -> str:
    mime_type = item.mime_type.lower()
    extension = item.extension

    if mime_type in OCR_MIME_TYPES or extension in OCR_EXTENSIONS:
        return "ocr"
    if mime_type in TEXT_MIME_TYPES or extension in TEXT_EXTENSIONS:
        return "text_extract"
    if mime_type in STRUCTURED_MIME_TYPES or extension in STRUCTURED_EXTENSIONS:
        return "structured"
    if mime_type in TECHNICAL_MIME_TYPES or extension in TECHNICAL_EXTENSIONS:
        return "technical"
    return "review"


def _strategy_label(key: str) -> str:
    labels = {
        "ocr": "Candidati OCR",
        "text_extract": "Documenti testuali",
        "structured": "File strutturati",
        "technical": "File tecnici / calendario / web",
        "review": "Da valutare manualmente",
    }
    return labels[key]


def _strategy_order(key: str) -> tuple[int, str]:
    order = {
        "ocr": 0,
        "text_extract": 1,
        "structured": 2,
        "technical": 3,
        "review": 4,
    }
    return (order.get(key, 99), key)
