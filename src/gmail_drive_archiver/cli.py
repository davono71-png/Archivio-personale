from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

from .ai_review import AiReviewItem, parse_ai_review_markdown, write_ai_review
from .anythingllm_export import AnythingLlmExportResult, export_anythingllm_package
from .config import ConfigError, load_config, load_split_config
from .database import ProcessedStore
from .drive import DriveArchiver, DriveInventory
from .drive_download import DownloadResult, download_inventory_files, write_download_report
from .gmail import GmailArchiver
from .gmail_export import GmailExportResult, GmailTextExporter, write_gmail_export_report
from .google_auth import authenticate, build_google_service
from .inventory_analysis import InventoryAnalysis, analyze_inventory, load_inventory_csv
from .models import ActionResult
from .ocr_plan import OcrPlan, build_ocr_plan
from .review_moves import ReviewMove, apply_review_move, build_review_moves
from .text_analysis import TextAnalysis, analyze_text_directory, text_analysis_to_json
from .text_extraction import ExtractedText, extract_inventory_text, write_extraction_report


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

    download_inventory = subcommands.add_parser(
        "download-inventory",
        help="scarica localmente file Drive elencati in un CSV inventory",
    )
    download_inventory.add_argument(
        "--input",
        type=Path,
        default=Path("database") / "inventory-da-classificare.csv",
        help="CSV generato da inventory",
    )
    download_inventory.add_argument(
        "--credentials",
        type=Path,
        required=True,
        help="client OAuth JSON scaricato da Google Cloud",
    )
    download_inventory.add_argument(
        "--token",
        type=Path,
        default=DEFAULT_TOKEN,
        help=f"token OAuth locale (default: {DEFAULT_TOKEN})",
    )
    download_inventory.add_argument(
        "--output-dir",
        type=Path,
        default=Path("database") / "downloads",
        help="cartella locale dove salvare i file",
    )
    download_inventory.add_argument(
        "--report",
        type=Path,
        default=Path("database") / "download-report.csv",
        help="CSV con esito download per file",
    )
    download_inventory.add_argument("--limit", type=int, help="limita il numero di righe inventory da scaricare")
    download_inventory.add_argument(
        "--overwrite",
        action="store_true",
        help="riscarica anche i file gia presenti localmente",
    )
    download_inventory.set_defaults(func=run_download_inventory)

    export_gmail_text = subcommands.add_parser(
        "export-gmail-text",
        help="esporta email Gmail come file Markdown testuali",
    )
    export_gmail_text.add_argument(
        "--gmail-rules",
        type=Path,
        default=DEFAULT_GMAIL_RULES,
        help=f"regole Gmail YAML (default: {DEFAULT_GMAIL_RULES})",
    )
    export_gmail_text.add_argument("--credentials", type=Path, required=True, help="client OAuth JSON scaricato da Google Cloud")
    export_gmail_text.add_argument("--token", type=Path, default=DEFAULT_TOKEN, help=f"token OAuth locale (default: {DEFAULT_TOKEN})")
    export_gmail_text.add_argument("--db", type=Path, default=DEFAULT_DB, help=f"database SQLite (default: {DEFAULT_DB})")
    export_gmail_text.add_argument(
        "--output-dir",
        type=Path,
        default=Path("database") / "email-text",
        help="cartella dove salvare le email esportate",
    )
    export_gmail_text.add_argument(
        "--report",
        type=Path,
        default=Path("database") / "gmail-text-export-report.csv",
        help="CSV con esito export email",
    )
    export_gmail_text.add_argument("--owner", choices=("Davide", "Ralitza", "Non chiaro"), default="Davide")
    export_gmail_text.add_argument("--visibility", choices=("privato", "condiviso"), default="privato")
    export_gmail_text.add_argument("--rule", help="esporta solo una regola Gmail per nome")
    export_gmail_text.add_argument("--force", action="store_true", help="riesporta anche email gia processate")
    export_gmail_text.set_defaults(func=run_export_gmail_text)

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

    ocr_plan_command = subcommands.add_parser(
        "ocr-plan",
        help="pianifica quali file dell'inventario richiedono OCR o estrazione testo",
    )
    ocr_plan_command.add_argument(
        "--input",
        type=Path,
        default=Path("database") / "inventory-da-classificare.csv",
        help="CSV generato da inventory",
    )
    ocr_plan_command.add_argument("--output", type=Path, help="percorso file JSON di output")
    ocr_plan_command.add_argument(
        "--format",
        choices=("table", "json"),
        default="table",
        help="formato output (default: table)",
    )
    ocr_plan_command.set_defaults(func=run_ocr_plan)

    extract_text_command = subcommands.add_parser(
        "extract-text",
        help="estrae testo da file locali scaricati usando l'inventario",
    )
    extract_text_command.add_argument(
        "--input",
        type=Path,
        default=Path("database") / "inventory-da-classificare.csv",
        help="CSV generato da inventory",
    )
    extract_text_command.add_argument(
        "--files-dir",
        type=Path,
        default=Path("database") / "downloads",
        help="cartella locale che contiene i file da processare",
    )
    extract_text_command.add_argument(
        "--output-dir",
        type=Path,
        default=Path("database") / "extracted-text",
        help="cartella dove salvare i .txt estratti",
    )
    extract_text_command.add_argument(
        "--report",
        type=Path,
        default=Path("database") / "extract-text-report.csv",
        help="CSV con esito estrazione per file",
    )
    extract_text_command.add_argument("--limit", type=int, help="limita il numero di righe inventario da processare")
    extract_text_command.set_defaults(func=run_extract_text)

    analyze_text_command = subcommands.add_parser(
        "analyze-text",
        help="analizza i testi estratti e propone categorie dal contenuto",
    )
    analyze_text_command.add_argument(
        "--text-dir",
        type=Path,
        default=Path("database") / "extracted-text",
        help="cartella contenente file .txt estratti",
    )
    analyze_text_command.add_argument(
        "--categories",
        type=Path,
        default=DEFAULT_CATEGORIES,
        help=f"categorie YAML (default: {DEFAULT_CATEGORIES})",
    )
    analyze_text_command.add_argument("--output", type=Path, help="percorso file JSON di output")
    analyze_text_command.add_argument(
        "--format",
        choices=("table", "json"),
        default="table",
        help="formato output (default: table)",
    )
    analyze_text_command.set_defaults(func=run_analyze_text)

    anythingllm_command = subcommands.add_parser(
        "prepare-anythingllm",
        help="prepara testi e metadati per import in AnythingLLM",
    )
    anythingllm_command.add_argument(
        "--inventory",
        type=Path,
        default=Path("database") / "inventory-da-classificare.csv",
        help="CSV generato da inventory",
    )
    anythingllm_command.add_argument(
        "--text-dir",
        type=Path,
        default=Path("database") / "extracted-text",
        help="cartella contenente file .txt estratti",
    )
    anythingllm_command.add_argument(
        "--categories",
        type=Path,
        default=DEFAULT_CATEGORIES,
        help=f"categorie YAML (default: {DEFAULT_CATEGORIES})",
    )
    anythingllm_command.add_argument(
        "--output-dir",
        type=Path,
        default=Path("database") / "anythingllm-import",
        help="cartella dove creare il pacchetto import",
    )
    anythingllm_command.add_argument(
        "--min-words",
        type=int,
        default=0,
        help="esporta solo testi con almeno questo numero di parole",
    )
    anythingllm_command.add_argument(
        "--category",
        action="append",
        help="esporta solo una categoria; ripeti l'opzione per piu categorie",
    )
    anythingllm_command.add_argument("--limit", type=int, help="numero massimo di documenti da esportare")
    anythingllm_command.add_argument(
        "--skip-ignored",
        action="store_true",
        help="salta testi vuoti o non classificabili dalle euristiche locali",
    )
    anythingllm_command.add_argument(
        "--clean-output",
        action="store_true",
        help="rimuove vecchi .txt e manifest dalla cartella output prima di esportare",
    )
    anythingllm_command.set_defaults(func=run_prepare_anythingllm)

    ai_review_command = subcommands.add_parser(
        "import-ai-review",
        help="importa una tabella Markdown di classificazione AI in CSV/JSON o SQLite",
    )
    ai_review_command.add_argument("--input", type=Path, required=True, help="file Markdown con tabella AI")
    ai_review_command.add_argument("--output", type=Path, help="file output CSV/JSON")
    ai_review_command.add_argument(
        "--format",
        choices=("json", "csv"),
        default="json",
        help="formato output quando --output e presente",
    )
    ai_review_command.add_argument("--db", type=Path, help="database SQLite dove salvare la review")
    ai_review_command.set_defaults(func=run_import_ai_review)

    review_summary = subcommands.add_parser(
        "review-summary",
        help="mostra riepilogo delle classificazioni AI importate nel database",
    )
    review_summary.add_argument("--db", type=Path, default=DEFAULT_DB, help=f"database SQLite (default: {DEFAULT_DB})")
    review_summary.add_argument("--limit", type=int, default=20, help="numero massimo di righe recenti da mostrare")
    review_summary.set_defaults(func=run_review_summary)

    set_review_status = subcommands.add_parser(
        "set-review-status",
        help="approva o rifiuta righe AI importate, senza spostare file",
    )
    set_review_status.add_argument("--db", type=Path, default=DEFAULT_DB, help=f"database SQLite (default: {DEFAULT_DB})")
    set_review_status.add_argument("--status", choices=("approved", "rejected", "pending"), required=True)
    set_review_status.add_argument("--category", help="filtra per categoria")
    set_review_status.add_argument("--action", help="filtra per azione consigliata")
    set_review_status.add_argument("--min-confidence", type=float, help="filtra per confidenza minima")
    set_review_status.add_argument("--limit", type=int, help="numero massimo di righe da aggiornare")
    set_review_status.set_defaults(func=run_set_review_status)

    review_moves = subcommands.add_parser(
        "apply-review-moves",
        help="pianifica o applica spostamenti Drive per review approvate",
    )
    review_moves.add_argument("--db", type=Path, default=DEFAULT_DB, help=f"database SQLite (default: {DEFAULT_DB})")
    review_moves.add_argument(
        "--inventory",
        type=Path,
        default=Path("database") / "inventory-da-classificare.csv",
        help="CSV generato da inventory",
    )
    review_moves.add_argument(
        "--drive-config",
        type=Path,
        default=DEFAULT_DRIVE_CONFIG,
        help=f"config Drive YAML (default: {DEFAULT_DRIVE_CONFIG})",
    )
    review_moves.add_argument("--status", default="approved", help="stato review da pianificare/applicare")
    review_moves.add_argument("--apply", action="store_true", help="esegue davvero gli spostamenti su Drive")
    review_moves.add_argument("--credentials", type=Path, help="client OAuth JSON, richiesto con --apply")
    review_moves.add_argument("--token", type=Path, default=DEFAULT_TOKEN, help=f"token OAuth locale (default: {DEFAULT_TOKEN})")
    review_moves.set_defaults(func=run_apply_review_moves)

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


def run_download_inventory(args: argparse.Namespace) -> int:
    try:
        items = load_inventory_csv(args.input)
        credentials = authenticate(args.credentials, args.token)
        drive_service = build_google_service("drive", "v3", credentials)
        results = download_inventory_files(
            drive_service,
            items,
            args.output_dir,
            limit=args.limit,
            skip_existing=not args.overwrite,
        )
        write_download_report(results, args.report)
    except OSError as exc:
        print(f"Errore download inventario: {exc}", file=sys.stderr)
        return 2

    _print_download_results(results, args.report)
    return 0


def run_export_gmail_text(args: argparse.Namespace) -> int:
    try:
        config = load_split_config(args.gmail_rules, None, None)
    except (OSError, ConfigError) as exc:
        print(f"Errore configurazione Gmail: {exc}", file=sys.stderr)
        return 2

    rules = [rule for rule in config.gmail if not args.rule or rule.name == args.rule]
    if not rules:
        print("Nessuna regola Gmail da esportare.", file=sys.stderr)
        return 2

    credentials = authenticate(args.credentials, args.token)
    gmail_service = build_google_service("gmail", "v1", credentials)
    results: list[GmailExportResult] = []
    with ProcessedStore(args.db) as store:
        exporter = GmailTextExporter(gmail_service, store)
        for rule in rules:
            results.extend(
                exporter.export_rule(
                    rule,
                    args.output_dir,
                    owner=args.owner,
                    visibility=args.visibility,
                    force=args.force,
                )
            )

    write_gmail_export_report(results, args.report)
    _print_gmail_export_results(results, args.output_dir, args.report)
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


def run_ocr_plan(args: argparse.Namespace) -> int:
    try:
        items = load_inventory_csv(args.input)
    except OSError as exc:
        print(f"Errore piano OCR: {exc}", file=sys.stderr)
        return 2

    plan = build_ocr_plan(items)
    _write_ocr_plan(plan, args.format, args.output)
    return 0


def run_extract_text(args: argparse.Namespace) -> int:
    try:
        items = load_inventory_csv(args.input)
        results = extract_inventory_text(items, args.files_dir, args.output_dir, args.limit)
        write_extraction_report(results, args.report)
    except OSError as exc:
        print(f"Errore estrazione testo: {exc}", file=sys.stderr)
        return 2

    _print_extraction_results(results, args.report)
    return 0


def run_analyze_text(args: argparse.Namespace) -> int:
    try:
        config = load_split_config(None, None, args.categories)
        analysis = analyze_text_directory(args.text_dir, config.categories)
    except (OSError, ConfigError) as exc:
        print(f"Errore analisi testi: {exc}", file=sys.stderr)
        return 2

    _write_text_analysis(analysis, args.format, args.output)
    return 0


def run_prepare_anythingllm(args: argparse.Namespace) -> int:
    try:
        inventory_items = load_inventory_csv(args.inventory)
        config = load_split_config(None, None, args.categories)
        analysis = analyze_text_directory(args.text_dir, config.categories)
        result = export_anythingllm_package(
            inventory_items,
            analysis,
            args.output_dir,
            min_words=args.min_words,
            categories=set(args.category) if args.category else None,
            limit=args.limit,
            skip_ignored=args.skip_ignored,
            clean_output=args.clean_output,
        )
    except (OSError, ConfigError) as exc:
        print(f"Errore export AnythingLLM: {exc}", file=sys.stderr)
        return 2

    _print_anythingllm_export(result)
    return 0


def run_import_ai_review(args: argparse.Namespace) -> int:
    try:
        items = parse_ai_review_markdown(args.input)
        if args.output:
            write_ai_review(items, args.output, args.format)
        if args.db:
            with ProcessedStore(args.db) as store:
                for item in items:
                    store.record_ai_review_item(
                        document_name=item.document_name,
                        category=item.category,
                        subcategory=item.subcategory,
                        owner=item.owner,
                        suggested_visibility=item.suggested_visibility,
                        relevant_date=item.relevant_date,
                        deadline=item.deadline,
                        recommended_action=item.recommended_action,
                        duplicate_of=item.duplicate_of,
                        confidence=item.confidence,
                        reason=item.reason,
                        source_path=str(args.input),
                    )
    except OSError as exc:
        print(f"Errore import review AI: {exc}", file=sys.stderr)
        return 2

    _print_ai_review_import(items, args.output, args.db)
    return 0


def run_review_summary(args: argparse.Namespace) -> int:
    try:
        with ProcessedStore(args.db) as store:
            category_counts = store.ai_review_counts_by_category()
            action_counts = store.ai_review_counts_by_action()
            latest_items = store.latest_ai_review_items(args.limit)
    except OSError as exc:
        print(f"Errore riepilogo review AI: {exc}", file=sys.stderr)
        return 2

    _print_review_summary(category_counts, action_counts, latest_items)
    return 0


def run_set_review_status(args: argparse.Namespace) -> int:
    try:
        with ProcessedStore(args.db) as store:
            updated = store.set_ai_review_status(
                status=args.status,
                category=args.category,
                min_confidence=args.min_confidence,
                action=args.action,
                limit=args.limit,
            )
    except OSError as exc:
        print(f"Errore aggiornamento stato review AI: {exc}", file=sys.stderr)
        return 2

    print(f"Righe aggiornate: {updated}")
    return 0


def run_apply_review_moves(args: argparse.Namespace) -> int:
    try:
        inventory_items = load_inventory_csv(args.inventory)
        config = load_split_config(None, args.drive_config, None)
        with ProcessedStore(args.db) as store:
            review_items = store.ai_review_items_for_status(args.status)
            moves = build_review_moves(review_items, inventory_items, config.drive_settings.category_folders)

            applied = 0
            if args.apply:
                if not args.credentials:
                    print("Errore: --credentials e richiesto quando usi --apply.", file=sys.stderr)
                    return 2
                credentials = authenticate(args.credentials, args.token)
                drive_service = build_google_service("drive", "v3", credentials)
                for move in moves:
                    if move.status != "planned":
                        continue
                    apply_review_move(drive_service, move)
                    store.mark_ai_review_applied(move.review_id, move.drive_file_id, move.target_folder_id)
                    applied += 1
    except (OSError, ConfigError) as exc:
        print(f"Errore spostamenti review AI: {exc}", file=sys.stderr)
        return 2

    _print_review_moves(moves, applied=applied, apply=args.apply)
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


def _write_ocr_plan(plan: OcrPlan, output_format: str, output_path: Path | None) -> None:
    if output_format == "json":
        payload = json.dumps(_ocr_plan_payload(plan), ensure_ascii=False, indent=2)
        _write_or_print(payload, output_path)
    else:
        _print_ocr_plan(plan)


def _ocr_plan_payload(plan: OcrPlan) -> dict:
    return {
        "total_items": plan.total_items,
        "buckets": [
            {
                "key": bucket.key,
                "label": bucket.label,
                "count": bucket.count,
                "examples": bucket.examples,
            }
            for bucket in plan.buckets
        ],
    }


def _print_ocr_plan(plan: OcrPlan) -> None:
    print(f"Totale file: {plan.total_items}")
    print()

    if not plan.buckets:
        print("Nessun file nell'inventario.")
        return

    for bucket in plan.buckets:
        print(f"{bucket.label}: {bucket.count}")
        for example in bucket.examples:
            print(f"  - {example}")
        print()


def _print_extraction_results(results: list[ExtractedText], report_path: Path) -> None:
    counts: dict[str, int] = {}
    for result in results:
        counts[result.status] = counts.get(result.status, 0) + 1

    print(f"Report estrazione: {report_path}")
    for status, count in sorted(counts.items()):
        print(f"  {status}: {count}")

    missing_or_pending = [
        result
        for result in results
        if result.status in {"missing_local_file", "requires_ocr", "unsupported", "error"}
    ]
    if missing_or_pending:
        print("Esempi da completare:")
        for result in missing_or_pending[:10]:
            detail = f" ({result.detail})" if result.detail else ""
            print(f"  - {result.name}: {result.status}{detail}")


def _print_download_results(results: list[DownloadResult], report_path: Path) -> None:
    counts: dict[str, int] = {}
    for result in results:
        counts[result.status] = counts.get(result.status, 0) + 1

    print(f"Report download: {report_path}")
    for status, count in sorted(counts.items()):
        print(f"  {status}: {count}")

    incomplete = [
        result
        for result in results
        if result.status in {"error", "unsupported_google_file"}
    ]
    if incomplete:
        print("Esempi non scaricati:")
        for result in incomplete[:10]:
            detail = f" ({result.detail})" if result.detail else ""
            print(f"  - {result.name}: {result.status}{detail}")


def _print_gmail_export_results(results: list[GmailExportResult], output_dir: Path, report_path: Path) -> None:
    counts: dict[str, int] = {}
    for result in results:
        counts[result.status] = counts.get(result.status, 0) + 1

    print(f"Email considerate: {len(results)}")
    print(f"Cartella export: {output_dir}")
    print(f"Report: {report_path}")
    for status, count in sorted(counts.items()):
        print(f"  {status}: {count}")

    for result in results[:10]:
        if result.status == "exported":
            print(f"  - {result.subject} -> {result.output_path}")


def _write_text_analysis(
    analysis: TextAnalysis,
    output_format: str,
    output_path: Path | None,
) -> None:
    if output_format == "json":
        payload = text_analysis_to_json(analysis)
        _write_or_print(payload, output_path)
    else:
        _print_text_analysis(analysis)


def _print_text_analysis(analysis: TextAnalysis) -> None:
    print(f"Totale testi analizzati: {analysis.total_files}")
    print()

    print("Categorie dal contenuto:")
    if not analysis.category_counts:
        print("  Nessuna categoria riconosciuta.")
    for category, count in sorted(analysis.category_counts.items(), key=lambda item: (-item[1], item[0])):
        print(f"  {count:4d}  {category}")
    print()

    print("File:")
    for item in analysis.analyzed_files[:20]:
        best = item.best_category or "Non classificato"
        detail = ""
        if item.categories:
            keywords = ", ".join(item.categories[0].keywords)
            detail = f" keywords={keywords}"
        print(f"  - {Path(item.path).name}: {best} parole={item.word_count}{detail}")

    if analysis.unclassified_files:
        print()
        print(f"Non classificati dal contenuto: {len(analysis.unclassified_files)}")
        for path in analysis.unclassified_files[:10]:
            print(f"  - {Path(path).name}")


def _print_anythingllm_export(result: AnythingLlmExportResult) -> None:
    print(f"Documenti esportati per AnythingLLM: {result.exported_count}")
    print(f"Cartella import: {result.output_dir}")
    print(f"Manifest: {result.manifest_path}")


def _print_ai_review_import(items: list[AiReviewItem], output_path: Path | None, db_path: Path | None) -> None:
    print(f"Righe review AI importate: {len(items)}")
    if output_path:
        print(f"Output: {output_path}")
    if db_path:
        print(f"Database aggiornato: {db_path}")


def _print_review_summary(
    category_counts: list[tuple[str, int]],
    action_counts: list[tuple[str, int]],
    latest_items: list[dict[str, str]],
) -> None:
    total = sum(count for _category, count in category_counts)
    print(f"Review AI nel database: {total}")
    print()

    print("Categorie:")
    if not category_counts:
        print("  Nessuna review importata.")
    for category, count in category_counts:
        print(f"  {count:4d}  {category}")
    print()

    print("Azioni consigliate:")
    if not action_counts:
        print("  Nessuna azione importata.")
    for action, count in action_counts:
        print(f"  {count:4d}  {action}")
    print()

    print("Ultime review:")
    if not latest_items:
        print("  Nessuna riga da mostrare.")
    for item in latest_items:
        print(
            f"  - {item['document_name']}: {item['category']} / "
            f"{item['recommended_action']} owner={item.get('owner', '')} "
            f"vis={item.get('suggested_visibility', '')} conf={item['confidence']}"
        )
        if item["reason"]:
            print(f"    {item['reason']}")


def _print_review_moves(moves: list[ReviewMove], applied: int, apply: bool) -> None:
    mode = "APPLY" if apply else "DRY-RUN"
    planned = sum(1 for move in moves if move.status == "planned")
    blocked = len(moves) - planned
    print(f"[{mode}] Spostamenti pianificati: {planned}")
    print(f"[{mode}] Spostamenti bloccati: {blocked}")
    if apply:
        print(f"[{mode}] Spostamenti eseguiti: {applied}")
    print()

    for move in moves:
        if move.status == "planned":
            print(
                f"[{mode}] MOVE {move.drive_name} ({move.drive_file_id}) "
                f"-> {move.category} folder={move.target_folder_id}"
            )
        else:
            print(f"[{mode}] SKIP {move.document_name} status={move.status} {move.detail}".rstrip())


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)
