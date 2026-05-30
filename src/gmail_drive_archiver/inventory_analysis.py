from __future__ import annotations

import csv
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path


DEFAULT_CATEGORY_KEYWORDS = {
    "Banca": ("bonifico", "banca", "estratto", "conto", "ricevuta", "pagamento"),
    "Salute": ("sanitario", "ricetta", "medico", "salute", "farmacia", "visita"),
    "Assicurazioni": ("assicurazione", "polizza", "ivass", "certificato internazionale"),
    "Casa": ("casa", "bolletta", "utenza", "cancello", "vasca", "vetro", "nicchia"),
    "Auto": ("auto", "motogp", "veicolo", "targa"),
    "Fisco": ("fisco", "fattura", "ricevutatelematica", "dichiarazione", "agenzia", "iva"),
    "Garanzie": ("garanzia", "liberatoria"),
    "Sport": ("ciclismo", "allenamento", "vo2max", "zona", "sport"),
    "Tecnologia": ("software", "tech", "html", "xml"),
    "Viaggi": ("viaggi", "biglietti", "elba", "shipping"),
}


@dataclass(frozen=True)
class InventoryItem:
    id: str
    name: str
    mime_type: str
    size: str = ""
    created_time: str = ""
    modified_time: str = ""
    web_view_link: str = ""

    @property
    def extension(self) -> str:
        suffix = Path(self.name).suffix.lower().lstrip(".")
        return suffix or "(senza estensione)"


@dataclass(frozen=True)
class CategoryGuess:
    category: str
    count: int
    examples: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class InventoryAnalysis:
    total_items: int
    mime_types: Counter[str]
    extensions: Counter[str]
    categories: list[CategoryGuess]
    unclassified_count: int
    unclassified_examples: list[str]


def load_inventory_csv(path: Path) -> list[InventoryItem]:
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        return [
            InventoryItem(
                id=row.get("id", ""),
                name=row.get("name", ""),
                mime_type=row.get("mime_type", ""),
                size=row.get("size", ""),
                created_time=row.get("created_time", ""),
                modified_time=row.get("modified_time", ""),
                web_view_link=row.get("web_view_link", ""),
            )
            for row in reader
        ]


def analyze_inventory(items: list[InventoryItem], categories: list[str] | None = None) -> InventoryAnalysis:
    category_names = categories or []
    mime_types: Counter[str] = Counter(item.mime_type or "(sconosciuto)" for item in items)
    extensions: Counter[str] = Counter(item.extension for item in items)
    category_matches: dict[str, list[str]] = {category: [] for category in category_names}
    unclassified: list[str] = []

    for item in items:
        matches = _guess_categories(item.name, category_names)
        if matches:
            for category in matches:
                category_matches.setdefault(category, []).append(item.name)
        else:
            unclassified.append(item.name)

    guesses = [
        CategoryGuess(category=category, count=len(names), examples=names[:5])
        for category, names in category_matches.items()
        if names
    ]
    guesses.sort(key=lambda guess: (-guess.count, guess.category))

    return InventoryAnalysis(
        total_items=len(items),
        mime_types=mime_types,
        extensions=extensions,
        categories=guesses,
        unclassified_count=len(unclassified),
        unclassified_examples=unclassified[:10],
    )


def _guess_categories(name: str, category_names: list[str]) -> list[str]:
    normalized = name.casefold()
    matches: list[str] = []

    for category in category_names:
        keywords = DEFAULT_CATEGORY_KEYWORDS.get(category, ())
        if any(keyword.casefold() in normalized for keyword in keywords):
            matches.append(category)

    if not matches and "Varie" in category_names:
        return []
    return matches
