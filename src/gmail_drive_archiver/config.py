from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


class ConfigError(ValueError):
    """Raised when the YAML rule file is invalid."""


@dataclass(frozen=True)
class GmailRule:
    name: str
    query: str
    label: str | None = None
    mark_read: bool = False
    max_items: int | None = None


@dataclass(frozen=True)
class DriveRule:
    name: str
    query: str
    target_folder_id: str
    remove_from_current_parents: bool = True
    max_items: int | None = None


@dataclass(frozen=True)
class ArchiveConfig:
    gmail: list[GmailRule] = field(default_factory=list)
    drive: list[DriveRule] = field(default_factory=list)


def load_config(path: Path) -> ArchiveConfig:
    """Load and validate archiving rules from a YAML file."""

    with path.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}

    if not isinstance(raw, dict):
        raise ConfigError("Il file YAML deve contenere una mappa al livello principale.")

    return ArchiveConfig(
        gmail=[_gmail_rule(item) for item in _sequence(raw.get("gmail", []), "gmail")],
        drive=[_drive_rule(item) for item in _sequence(raw.get("drive", []), "drive")],
    )


def _sequence(value: Any, key: str) -> list[dict[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ConfigError(f"'{key}' deve essere una lista di regole.")
    for index, item in enumerate(value, start=1):
        if not isinstance(item, dict):
            raise ConfigError(f"'{key}[{index}]' deve essere una mappa.")
    return value


def _gmail_rule(raw: dict[str, Any]) -> GmailRule:
    name = _required_str(raw, "name", "gmail")
    query = _required_str(raw, "query", name)
    return GmailRule(
        name=name,
        query=query,
        label=_optional_str(raw, "label", name),
        mark_read=bool(raw.get("mark_read", False)),
        max_items=_optional_positive_int(raw, "max_items", name),
    )


def _drive_rule(raw: dict[str, Any]) -> DriveRule:
    name = _required_str(raw, "name", "drive")
    query = _required_str(raw, "query", name)
    return DriveRule(
        name=name,
        query=query,
        target_folder_id=_required_str(raw, "target_folder_id", name),
        remove_from_current_parents=bool(raw.get("remove_from_current_parents", True)),
        max_items=_optional_positive_int(raw, "max_items", name),
    )


def _required_str(raw: dict[str, Any], key: str, rule_name: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"La regola '{rule_name}' richiede un valore stringa per '{key}'.")
    return value.strip()


def _optional_str(raw: dict[str, Any], key: str, rule_name: str) -> str | None:
    value = raw.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"La regola '{rule_name}' richiede una stringa non vuota per '{key}'.")
    return value.strip()


def _optional_positive_int(raw: dict[str, Any], key: str, rule_name: str) -> int | None:
    value = raw.get(key)
    if value is None:
        return None
    if not isinstance(value, int) or value <= 0:
        raise ConfigError(f"La regola '{rule_name}' richiede un intero positivo per '{key}'.")
    return value
