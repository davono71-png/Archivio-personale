from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

from .config import ConfigError, load_config, load_split_config
from .database import ProcessedStore
from .drive import DriveArchiver, DriveInventory
from .gmail import GmailArchiver
from .google_auth import authenticate, build_google_service
from .inventory_analysis import InventoryAnalysis, analyze_inventory, load_inventory_csv
from .models import ActionResult


DEFAULT_CONFIG_DIR = Path.home() / ".config" / "gmail-drive-archiver"
DEFAULT_TOKEN = DEFAULT_CONFIG_DIR / "token.json"
DEFAULT_DB = DEFAULT_CONFIG_DIR / "processed.sqlite3"
DEFAULT_REPO_CONFIG_DIR = Path("config")
DEFAULT_GMAIL_RULES = DEFAULT_REPO_CONFIG_DIR / "gmail-rules.yml"
DEFAULT_DRIVE_CONFIG = DEFAULT_REPO_CONFIG_DIR / "drive-folders.yml"
DEFAULT_CATEGORIES = DEFAULT_REPO_CONFIG_DIR / "categories.yml"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gmail-drive-archiver",
        description="Archivia email Gmail e documenti Google Drive personali usando regole YAML.",
    )
    subcommands = parser.add_subparsers(dest="command", required=True)

    init_db = subcommands.add_parser("init-db", help="inizializza il database SQLite")
    init_db.add_argument("--db", type=Path, default=DEFAULT_DB, help=f"percorso DB SQLite (default: {DEFAULT_DB})")
    init_db.set_defaults(func=run_init_db)

    inventory = subcommands.add_parser("inventory", help="elenca i file Drive da classificare senza spostarli")
    inventory.add_argument(
        "--drive-config",
        type=Path,
        default=DEFAULT_DRIVE_CONFIG,
        help=f"config Drive YAML (default: {DEFAULT_DRIVE_CONFIG})",
    )
    inventory.add_argument(
        "--folder-id",
        help="ID cartella Drive da inventariare; default: drive.inbox_folder_id",
    )
    inventory.add_argument(
        "--credentials",
        type=Path,
        required=True,
        help="client OAuth JSON scaricato da Google Cloud",
    )
    inventory.add_argument(
        "--token",
        type=Path,
        default=DEFAULT_TOKEN,
        help=f"token OAuth locale (default: {DEFAULT_TOKEN})",
    )
    inventory.add_argument("--max-items", type=int, default=100, help="numero massimo di file da elencare")
    inventory.add_argument("--output", type=Path, help="percorso file di output CSV/JSON")
    inventory.add_argument(
        "--format",
        choices=("table", "csv", "json"),
        default="table",
        help="formato output (default: table)",
    )
    inventory.set_defaults(func=run_inventory)

    analyze_inventory_command = subcommands.add_parser(
        "analyze-inventory",
        help="analizza un CSV inventory e propone categorie probabili",
    )
    analyze_inventory_command.add_argument(
        "--input",
        type=Path,
        default=Path("database") / "inventory-da-classificare.csv",
        help="CSV generato da inventory",
    )
    analyze_inventory_command.add_argument(
        "--categories",
        type=Path,
        default=DEFAULT_CATEGORIES,
        help=f"categorie YAML (default: {DEFAULT_CATEGORIES})",
    )
    analyze_inventory_command.add_argument("--output", type=Path, help="percorso file JSON di output")
    analyze_inventory_command.add_argument(
        "--format",
        choices=("table", "json"),
        default="table",
        help="formato output (default: table)",
    )
    analyze_inventory_command.set_defaults(func=run_analyze_inventory)

    sync = subcommands.add_parser("sync", help="esegue le regole di archiviazione")
    sync.add_argument(
        "--rules",
        type=Path,
        help="file YAML unico con regole Gmail/Drive; se presente sostituisce i file config separati",
    )
    sync.add_argument(
        "--gmail-rules",
        type=Path,
        default=DEFAULT_GMAIL_RULES,
        help=f"regole Gmail YAML (default: {DEFAULT_GMAIL_RULES})",
    )
    sync.add_argument(
        "--drive-config",
        type=Path,
        default=DEFAULT_DRIVE_CONFIG,
        help=f"config Drive YAML (default: {DEFAULT_DRIVE_CONFIG})",
    )
    sync.add_argument(
        "--categories",
        type=Path,
        default=DEFAULT_CATEGORIES,
        help=f"categorie YAML (default: {DEFAULT_CATEGORIES})",
    )
    sync.add_argument(
        "--credentials",
        type=Path,
        required=True,
        help="client OAuth JSON scaricato da Google Cloud",
    )
    sync.add_argument("--token", type=Path, default=DEFAULT_TOKEN, help=f"token OAuth locale (default: {DEFAULT_TOKEN})")
    sync.add_argument("--db", type=Path, default=DEFAULT_DB, help=f"percorso DB SQLite (default: {DEFAULT_DB})")
    sync.add_argument("--dry-run", action="store_true", help="mostra cosa verrebbe archiviato senza modifiche")
    sync.add_argument(
        "--service",
        choices=("all", "gmail", "drive"),
        default="all",
        help="limita l'esecuzione a Gmail o Drive",
    )
    sync.set_defaults(func=run_sync)

    return parser


def run_init_db(args: argparse.Namespace) -> int:
    with ProcessedStore(args.db):
        pass
    print(f"Database inizializzato: {args.db}")
    return 0


def run_sync(args: argparse.Namespace) -> int:
    try:
        config = (
            load_config(args.rules)
            if args.rules
            else load_split_config(args.gmail_rules, args.drive_config, args.categories)
        )
    except (OSError, ConfigError) as exc:
        print(f"Errore configurazione: {exc}", file=sys.stderr)
        return 2

    credentials = authenticate(args.credentials, args.token)
    results: list[ActionResult] = []

    with ProcessedStore(args.db) as store:
        if args.service in ("all", "gmail") and config.gmail:
            gmail_service = build_google_service("gmail", "v1", credentials)
            gmail = GmailArchiver(gmail_service, store)
            for rule in config.gmail:
                results.extend(gmail.process_rule(rule, dry_run=args.dry_run))

        if args.service in ("all", "drive") and config.drive:
            drive_service = build_google_service("drive", "v3", credentials)
            drive = DriveArchiver(drive_service, store)
            for rule in config.drive:
                results.extend(drive.process_rule(rule, dry_run=args.dry_run))

    _print_results(results, args.dry_run)
    return 0


def run_inventory(args: argparse.Namespace) -> int:
    try:
        config = load_split_config(None, args.drive_config, None)
    except (OSError, ConfigError) as exc:
        print(f"Errore configurazione: {exc}", file=sys.stderr)
        return 2

    folder_id = args.folder_id or config.drive_settings.inbox_folder_id
    if not folder_id:
        print(
            "Errore configurazione: specifica --folder-id oppure drive.inbox_folder_id.",
            file=sys.stderr,
        )
        return 2

    credentials = authenticate(args.credentials, args.token)
    drive_service = build_google_service("drive", "v3", credentials)
    files = DriveInventory(drive_service).list_folder(folder_id, args.max_items)
    _write_inventory(files, args.format, args.output)
    return 0


def run_analyze_inventory(args: argparse.Namespace) -> int:
    try:
        config = load_split_config(None, None, args.categories)
        items = load_inventory_csv(args.input)
    except (OSError, ConfigError) as exc:
        print(f"Errore analisi inventario: {exc}", file=sys.stderr)
        return 2

    analysis = analyze_inventory(items, config.categories)
    _write_inventory_analysis(analysis, args.format, args.output)
    return 0


def _print_results(results: list[ActionResult], dry_run: bool) -> None:
    prefix = "[DRY-RUN] " if dry_run else ""
    if not results:
        print(f"{prefix}Nessun elemento trovato.")
        return

    processed = 0
    skipped = 0
    for result in results:
        status = "SKIP" if result.skipped else result.action.upper()
        if result.skipped:
            skipped += 1
        else:
            processed += 1
        print(
            f"{prefix}{status} {result.service}:{result.item_id} "
            f"rule={result.rule_name} {result.detail}".rstrip()
        )

    print(f"{prefix}Totale: {processed} azioni, {skipped} gia processati.")


def _write_inventory(files: list[dict], output_format: str, output_path: Path | None) -> None:
    rows = [_inventory_row(file) for file in files]

    if output_format == "json":
        payload = json.dumps(rows, ensure_ascii=False, indent=2)
        _write_or_print(payload, output_path)
    elif output_format == "csv":
        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with output_path.open("w", newline="", encoding="utf-8") as handle:
                _write_csv(rows, handle)
            print(f"Inventario scritto: {output_path}")
        else:
            _write_csv(rows, sys.stdout)
    else:
        _print_inventory_table(rows)

    summary_stream = sys.stderr if output_path is None and output_format in ("csv", "json") else sys.stdout
    print(f"Totale file inventariati: {len(rows)}", file=summary_stream)


def _inventory_row(file: dict) -> dict[str, str]:
    return {
        "id": file.get("id", ""),
        "name": file.get("name", ""),
        "mime_type": file.get("mimeType", ""),
        "size": file.get("size", ""),
        "created_time": file.get("createdTime", ""),
        "modified_time": file.get("modifiedTime", ""),
        "web_view_link": file.get("webViewLink", ""),
    }


def _write_csv(rows: list[dict[str, str]], handle) -> None:  # type: ignore[no-untyped-def]
    fieldnames = ["id", "name", "mime_type", "size", "created_time", "modified_time", "web_view_link"]
    writer = csv.DictWriter(handle, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)


def _write_or_print(payload: str, output_path: Path | None) -> None:
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(payload + "\n", encoding="utf-8")
        print(f"Inventario scritto: {output_path}")
    else:
        print(payload)


def _print_inventory_table(rows: list[dict[str, str]]) -> None:
    if not rows:
        print("Nessun file trovato.")
        return

    for index, row in enumerate(rows, start=1):
        print(
            f"{index:04d} {row['id']} "
            f"name={row['name']} mime={row['mime_type']} modified={row['modified_time']}"
        )


def _write_inventory_analysis(
    analysis: InventoryAnalysis,
    output_format: str,
    output_path: Path | None,
) -> None:
    if output_format == "json":
        payload = json.dumps(_analysis_payload(analysis), ensure_ascii=False, indent=2)
        _write_or_print(payload, output_path)
    else:
        _print_inventory_analysis(analysis)


def _analysis_payload(analysis: InventoryAnalysis) -> dict:
    return {
        "total_items": analysis.total_items,
        "mime_types": dict(analysis.mime_types.most_common()),
        "extensions": dict(analysis.extensions.most_common()),
        "categories": [
            {
                "category": guess.category,
                "count": guess.count,
                "examples": guess.examples,
            }
            for guess in analysis.categories
        ],
        "unclassified_count": analysis.unclassified_count,
        "unclassified_examples": analysis.unclassified_examples,
    }


def _print_inventory_analysis(analysis: InventoryAnalysis) -> None:
    print(f"Totale file: {analysis.total_items}")
    print()

    print("Tipi MIME:")
    for mime_type, count in analysis.mime_types.most_common():
        print(f"  {count:4d}  {mime_type}")
    print()

    print("Estensioni:")
    for extension, count in analysis.extensions.most_common():
        print(f"  {count:4d}  {extension}")
    print()

    print("Categorie probabili:")
    if not analysis.categories:
        print("  Nessuna categoria riconosciuta dai nomi file.")
    for guess in analysis.categories:
        examples = "; ".join(guess.examples)
        print(f"  {guess.count:4d}  {guess.category}  esempi: {examples}")
    print()

    print(f"Non classificati dai nomi file: {analysis.unclassified_count}")
    if analysis.unclassified_examples:
        print("Esempi non classificati:")
        for example in analysis.unclassified_examples:
            print(f"  - {example}")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)
