from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from .inventory_analysis import DEFAULT_CATEGORY_KEYWORDS


@dataclass(frozen=True)
class TextCategoryMatch:
    category: str
    score: int
    keywords: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class TextFileAnalysis:
    path: str
    categories: list[TextCategoryMatch]
    word_count: int
    preview: str

    @property
    def best_category(self) -> str | None:
        if not self.categories:
            return None
        return self.categories[0].category


@dataclass(frozen=True)
class TextAnalysis:
    total_files: int
    analyzed_files: list[TextFileAnalysis]
    category_counts: dict[str, int]
    unclassified_files: list[str]


def analyze_text_directory(text_dir: Path, categories: list[str]) -> TextAnalysis:
    files = sorted(text_dir.glob("*.txt"))
    analyzed: list[TextFileAnalysis] = []
    category_counts: dict[str, int] = {category: 0 for category in categories}
    unclassified: list[str] = []

    for path in files:
        content = path.read_text(encoding="utf-8", errors="replace")
        matches = _match_categories(content, categories)
        analysis = TextFileAnalysis(
            path=str(path),
            categories=matches,
            word_count=_word_count(content),
            preview=_preview(content),
        )
        analyzed.append(analysis)

        if analysis.best_category:
            category_counts[analysis.best_category] = category_counts.get(analysis.best_category, 0) + 1
        else:
            unclassified.append(str(path))

    category_counts = {category: count for category, count in category_counts.items() if count > 0}
    return TextAnalysis(
        total_files=len(files),
        analyzed_files=analyzed,
        category_counts=category_counts,
        unclassified_files=unclassified,
    )


def text_analysis_to_json(analysis: TextAnalysis) -> str:
    payload = {
        "total_files": analysis.total_files,
        "category_counts": analysis.category_counts,
        "unclassified_files": analysis.unclassified_files,
        "files": [
            {
                "path": item.path,
                "best_category": item.best_category,
                "word_count": item.word_count,
                "preview": item.preview,
                "categories": [
                    {
                        "category": match.category,
                        "score": match.score,
                        "keywords": match.keywords,
                    }
                    for match in item.categories
                ],
            }
            for item in analysis.analyzed_files
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _match_categories(content: str, categories: list[str]) -> list[TextCategoryMatch]:
    normalized = content.casefold()
    matches: list[TextCategoryMatch] = []

    for category in categories:
        keywords = DEFAULT_CATEGORY_KEYWORDS.get(category, ())
        found = [keyword for keyword in keywords if keyword.casefold() in normalized]
        if found:
            matches.append(TextCategoryMatch(category=category, score=len(found), keywords=found[:10]))

    matches.sort(key=lambda match: (-match.score, match.category))
    return matches


def _word_count(content: str) -> int:
    return len(re.findall(r"\w+", content, flags=re.UNICODE))


def _preview(content: str, limit: int = 180) -> str:
    compact = re.sub(r"\s+", " ", content).strip()
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3].rstrip() + "..."
