from __future__ import annotations

import csv
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class AiReviewItem:
    document_name: str
    category: str = ""
    subcategory: str = ""
    owner: str = ""
    relevant_date: str = ""
    deadline: str = ""
    recommended_action: str = ""
    duplicate_of: str = ""
    confidence: str = ""
    reason: str = ""


HEADER_ALIASES = {
    "nome documento": "document_name",
    "documento": "document_name",
    "nome": "document_name",
    "categoria principale": "category",
    "categoria": "category",
    "sottocategoria proposta": "subcategory",
    "sottocategoria": "subcategory",
    "proprietario probabile": "owner",
    "proprietario": "owner",
    "data rilevante": "relevant_date",
    "data": "relevant_date",
    "scadenza": "deadline",
    "azione consigliata": "recommended_action",
    "azione": "recommended_action",
    "duplicato di": "duplicate_of",
    "duplicato": "duplicate_of",
    "confidenza": "confidence",
    "motivo sintetico": "reason",
    "motivo": "reason",
}


def parse_ai_review_markdown(path: Path) -> list[AiReviewItem]:
    lines = path.read_text(encoding="utf-8").splitlines()
    rows = _extract_markdown_table(lines)
    if not rows:
        return []

    headers = [_map_header(cell) for cell in rows[0]]
    items: list[AiReviewItem] = []
    for row in rows[1:]:
        values = {headers[index]: _clean_cell(cell) for index, cell in enumerate(row) if index < len(headers)}
        if not values.get("document_name"):
            continue
        items.append(
            AiReviewItem(
                document_name=values.get("document_name", ""),
                category=values.get("category", ""),
                subcategory=values.get("subcategory", ""),
                owner=values.get("owner", ""),
                relevant_date=values.get("relevant_date", ""),
                deadline=values.get("deadline", ""),
                recommended_action=values.get("recommended_action", ""),
                duplicate_of=values.get("duplicate_of", ""),
                confidence=values.get("confidence", ""),
                reason=values.get("reason", ""),
            )
        )
    return items


def write_ai_review(items: list[AiReviewItem], path: Path, output_format: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if output_format == "json":
        path.write_text(
            json.dumps([asdict(item) for item in items], ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return

    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(AiReviewItem.__dataclass_fields__.keys()))
        writer.writeheader()
        for item in items:
            writer.writerow(asdict(item))


def _extract_markdown_table(lines: list[str]) -> list[list[str]]:
    for index, line in enumerate(lines):
        if "|" not in line:
            continue
        next_line = lines[index + 1] if index + 1 < len(lines) else ""
        if _is_separator_row(next_line):
            table_lines = [line]
            for table_line in lines[index + 2 :]:
                if "|" not in table_line:
                    break
                table_lines.append(table_line)
            return [_split_row(table_line) for table_line in table_lines]
    return []


def _split_row(line: str) -> list[str]:
    stripped = line.strip().strip("|")
    return [_clean_cell(cell) for cell in stripped.split("|")]


def _is_separator_row(line: str) -> bool:
    cells = _split_row(line)
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell.strip()) for cell in cells)


def _map_header(header: str) -> str:
    normalized = _normalize(header)
    return HEADER_ALIASES.get(normalized, normalized.replace(" ", "_"))


def _normalize(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"[*`]", "", value)
    value = value.casefold()
    value = re.sub(r"\s+", " ", value).strip()
    return value


def _clean_cell(value: str) -> str:
    value = value.strip()
    value = re.sub(r"<br\s*/?>", " ", value, flags=re.IGNORECASE)
    value = re.sub(r"[*`]", "", value)
    return re.sub(r"\s+", " ", value).strip()
