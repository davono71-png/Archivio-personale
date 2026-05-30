from __future__ import annotations

import csv
import html
import re
import shutil
import subprocess
import zipfile
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree

from .drive_download import download_filename
from .inventory_analysis import InventoryItem
from .ocr_plan import OCR_EXTENSIONS, STRUCTURED_EXTENSIONS, TECHNICAL_EXTENSIONS, TEXT_EXTENSIONS


TEXT_SUFFIXES = TEXT_EXTENSIONS | STRUCTURED_EXTENSIONS | TECHNICAL_EXTENSIONS


@dataclass(frozen=True)
class ExtractedText:
    item_id: str
    name: str
    status: str
    output_path: str = ""
    detail: str = ""


def extract_inventory_text(
    items: list[InventoryItem],
    files_dir: Path,
    output_dir: Path,
    limit: int | None = None,
) -> list[ExtractedText]:
    output_dir.mkdir(parents=True, exist_ok=True)
    results: list[ExtractedText] = []

    for item in items[:limit]:
        source = _local_source_path(item, files_dir)
        if not source.exists():
            results.append(
                ExtractedText(
                    item_id=item.id,
                    name=item.name,
                    status="missing_local_file",
                    detail=f"file non trovato in {files_dir}",
                )
            )
            continue

        output_path = output_dir / f"{_safe_stem(item)}.txt"
        result = extract_text_file(item, source, output_path)
        results.append(result)

    return results


def _local_source_path(item: InventoryItem, files_dir: Path) -> Path:
    original = files_dir / item.name
    if original.exists():
        return original
    return files_dir / download_filename(item)


def extract_text_file(item: InventoryItem, source: Path, output_path: Path) -> ExtractedText:
    extension = source.suffix.lower().lstrip(".")

    try:
        if extension == "pdf":
            text = _extract_pdf_text(source)
            if text is None:
                return ExtractedText(item.id, item.name, "requires_ocr", detail="pdftotext non disponibile")
        elif extension in {"jpg", "jpeg", "png", "tif", "tiff", "webp", "bmp"}:
            return ExtractedText(item.id, item.name, "requires_ocr", detail="immagine")
        elif extension == "docx":
            text = _extract_docx_text(source)
        elif extension == "xlsx":
            text = _extract_xlsx_text(source)
        elif extension in {"html", "htm", "xml", "ics", "csv", "txt"}:
            text = _read_text_file(source)
        elif extension in TEXT_SUFFIXES:
            text = _read_text_file(source)
        elif extension in OCR_EXTENSIONS:
            return ExtractedText(item.id, item.name, "requires_ocr", detail=f"estensione {extension}")
        else:
            return ExtractedText(item.id, item.name, "unsupported", detail=f"estensione {extension or 'assente'}")
    except (OSError, UnicodeDecodeError, zipfile.BadZipFile, ElementTree.ParseError, subprocess.CalledProcessError) as exc:
        return ExtractedText(item.id, item.name, "error", detail=str(exc))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(text.strip() + "\n", encoding="utf-8")
    return ExtractedText(item.id, item.name, "extracted", output_path=str(output_path))


def write_extraction_report(results: list[ExtractedText], path: Path) -> None:
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


def _extract_pdf_text(source: Path) -> str | None:
    pdftotext = shutil.which("pdftotext")
    if not pdftotext:
        return None

    completed = subprocess.run(
        [pdftotext, "-layout", str(source), "-"],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return completed.stdout


def _extract_docx_text(source: Path) -> str:
    with zipfile.ZipFile(source) as archive:
        raw = archive.read("word/document.xml")
    root = ElementTree.fromstring(raw)
    paragraphs: list[str] = []
    current: list[str] = []

    for element in root.iter():
        tag = element.tag.rsplit("}", 1)[-1]
        if tag == "t" and element.text:
            current.append(element.text)
        elif tag == "p" and current:
            paragraphs.append("".join(current))
            current = []

    if current:
        paragraphs.append("".join(current))
    return "\n".join(paragraphs)


def _extract_xlsx_text(source: Path) -> str:
    with zipfile.ZipFile(source) as archive:
        shared_strings = _xlsx_shared_strings(archive)
        lines: list[str] = []
        for name in sorted(archive.namelist()):
            if not name.startswith("xl/worksheets/sheet") or not name.endswith(".xml"):
                continue
            root = ElementTree.fromstring(archive.read(name))
            lines.extend(_xlsx_sheet_rows(root, shared_strings))
    return "\n".join(lines)


def _xlsx_shared_strings(archive: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
    values: list[str] = []
    for item in root:
        texts = [node.text or "" for node in item.iter() if node.tag.rsplit("}", 1)[-1] == "t"]
        values.append("".join(texts))
    return values


def _xlsx_sheet_rows(root: ElementTree.Element, shared_strings: list[str]) -> list[str]:
    rows: list[str] = []
    for row in root.iter():
        if row.tag.rsplit("}", 1)[-1] != "row":
            continue
        values: list[str] = []
        for cell in row:
            if cell.tag.rsplit("}", 1)[-1] != "c":
                continue
            cell_type = cell.attrib.get("t")
            value_node = next((child for child in cell if child.tag.rsplit("}", 1)[-1] == "v"), None)
            if value_node is None or value_node.text is None:
                continue
            value = value_node.text
            if cell_type == "s" and value.isdigit() and int(value) < len(shared_strings):
                value = shared_strings[int(value)]
            values.append(value)
        if values:
            rows.append("\t".join(values))
    return rows


def _read_text_file(source: Path) -> str:
    raw = source.read_text(encoding="utf-8", errors="replace")
    if source.suffix.lower() in {".html", ".htm", ".xml"}:
        raw = re.sub(r"<[^>]+>", " ", raw)
        raw = html.unescape(raw)
        raw = re.sub(r"\s+", " ", raw)
    return raw


def _safe_stem(item: InventoryItem) -> str:
    stem = Path(item.name).stem or item.id
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", stem).strip("._")
    return f"{safe or item.id}-{item.id}"
