from __future__ import annotations

import csv
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path


ALLOWED_CATEGORIES = {
    "Banca",
    "Salute",
    "Assicurazioni",
    "Casa",
    "Auto",
    "Fisco",
    "Garanzie",
    "Sport",
    "Tecnologia",
    "Viaggi",
    "Lavoro",
    "Alimentazione",
    "Varie",
}


@dataclass(frozen=True)
class AiReviewItem:
    document_name: str
    category: str = ""
    subcategory: str = ""
    owner: str = ""
    suggested_visibility: str = ""
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
    "visibilita suggerita": "suggested_visibility",
    "visibilità suggerita": "suggested_visibility",
    "visibilita": "suggested_visibility",
    "visibilità": "suggested_visibility",
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
            normalize_ai_review_item(
                AiReviewItem(
                    document_name=values.get("document_name", ""),
                    category=values.get("category", ""),
                    subcategory=values.get("subcategory", ""),
                    owner=values.get("owner", ""),
                    suggested_visibility=values.get("suggested_visibility", ""),
                    relevant_date=values.get("relevant_date", ""),
                    deadline=values.get("deadline", ""),
                    recommended_action=values.get("recommended_action", ""),
                    duplicate_of=values.get("duplicate_of", ""),
                    confidence=values.get("confidence", ""),
                    reason=values.get("reason", ""),
                )
            )
        )
    return items


def normalize_ai_review_item(item: AiReviewItem) -> AiReviewItem:
    combined = " ".join(
        [
            item.document_name,
            item.category,
            item.subcategory,
            item.recommended_action,
            item.reason,
        ]
    )
    category = _normalize_category(item.category, combined)
    owner = _normalize_owner(item.owner)
    visibility = _normalize_visibility(item.suggested_visibility)

    return AiReviewItem(
        document_name=item.document_name,
        category=category,
        subcategory=item.subcategory,
        owner=owner,
        suggested_visibility=visibility,
        relevant_date=item.relevant_date,
        deadline=item.deadline,
        recommended_action=item.recommended_action,
        duplicate_of=item.duplicate_of,
        confidence=item.confidence,
        reason=item.reason,
    )


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


def _normalize_category(category: str, combined_text: str) -> str:
    text = _normalized_text(combined_text)

    # Specific rules override generic payment/bank wording.
    if _contains_any(text, ("bolletta", "energia", "gas", "acqua", "utenza", "utenze", "idrico", "eni", "enel")):
        return "Casa"
    if _contains_any(text, ("agenzia entrate", "agenzia delle entrate", "iva", "fiscale", "fisco", "dichiarazione", "fattura")):
        return "Fisco"
    if _contains_any(text, ("estratto conto", "conto corrente", "bonifico", "saldo", "giacenza", "banco bpm", "banca", "hype")):
        return "Banca"

    cleaned = _category_case(category)
    return cleaned if cleaned in ALLOWED_CATEGORIES else "Varie"


def _normalize_owner(owner: str) -> str:
    normalized = _normalized_text(owner)
    if normalized == "ralitza":
        return "Ralitza"
    if normalized in {"", "non chiaro", "non definito", "n d", "nd"}:
        return "Non chiaro"
    return "Davide"


def _normalize_visibility(visibility: str) -> str:
    normalized = _normalized_text(visibility)
    return "condiviso" if normalized == "condiviso" else "privato"


def _category_case(category: str) -> str:
    normalized = _normalized_text(category)
    for allowed in ALLOWED_CATEGORIES:
        if _normalized_text(allowed) == normalized:
            return allowed
    return category.strip()


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    return any(_keyword_present(text, keyword) for keyword in keywords)


def _keyword_present(text: str, keyword: str) -> bool:
    normalized_keyword = _normalized_text(keyword)
    return re.search(rf"(?<!\S){re.escape(normalized_keyword)}(?!\S)", text) is not None


def _normalized_text(value: str) -> str:
    normalized = value.casefold()
    normalized = re.sub(r"[^0-9a-zà-öø-ÿ]+", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()
