from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import ConfigError, load_config
from .database import ProcessedStore
from .drive import DriveArchiver
from .gmail import GmailArchiver
from .google_auth import authenticate, build_google_service
from .models import ActionResult


DEFAULT_CONFIG_DIR = Path.home() / ".config" / "gmail-drive-archiver"
DEFAULT_TOKEN = DEFAULT_CONFIG_DIR / "token.json"
DEFAULT_DB = DEFAULT_CONFIG_DIR / "processed.sqlite3"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gmail-drive-archiver",
        description="Archivia email Gmail e documenti Google Drive personali usando regole YAML.",
    )
    subcommands = parser.add_subparsers(dest="command", required=True)

    init_db = subcommands.add_parser("init-db", help="inizializza il database SQLite")
    init_db.add_argument("--db", type=Path, default=DEFAULT_DB, help=f"percorso DB SQLite (default: {DEFAULT_DB})")
    init_db.set_defaults(func=run_init_db)

    sync = subcommands.add_parser("sync", help="esegue le regole di archiviazione")
    sync.add_argument("--rules", type=Path, required=True, help="file YAML con le regole")
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
        config = load_config(args.rules)
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


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)
