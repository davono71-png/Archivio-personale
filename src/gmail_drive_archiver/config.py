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
class DriveSettings:
    inbox_folder_id: str | None = None
    archive_root_folder_id: str | None = None
    category_folders: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ArchiveConfig:
    gmail: list[GmailRule] = field(default_factory=list)
    drive: list[DriveRule] = field(default_factory=list)
    categories: list[str] = field(default_factory=list)
    drive_settings: DriveSettings = field(default_factory=DriveSettings)


def load_config(path: Path) -> ArchiveConfig:
    """Load and validate archiving rules from a YAML file."""

    raw = _load_yaml_map(path)

    return ArchiveConfig(
        gmail=[_gmail_rule(item) for item in _sequence(raw.get("gmail", []), "gmail")],
        drive=[_drive_rule(item) for item in _drive_rules(raw.get("drive", []))],
        categories=_categories(raw.get("categories", [])),
        drive_settings=_drive_settings(raw.get("drive", {})),
    )


def load_split_config(
    gmail_rules_path: Path | None,
    drive_config_path: Path | None,
    categories_path: Path | None,
) -> ArchiveConfig:
    """Load the repository-style split YAML configuration."""

    gmail_rules: list[GmailRule] = []
    drive_rules: list[DriveRule] = []
    drive_settings = DriveSettings()
    categories: list[str] = []

    if gmail_rules_path:
        raw_gmail = _load_yaml_map(gmail_rules_path)
        gmail_rules = [_gmail_rule(item) for item in _sequence(raw_gmail.get("gmail", []), "gmail")]

    if drive_config_path:
        raw_drive = _load_yaml_map(drive_config_path)
        drive_config = raw_drive.get("drive", [])
        drive_rules = [_drive_rule(item) for item in _drive_rules(drive_config)]
        drive_settings = _drive_settings(drive_config)

    if categories_path:
        raw_categories = _load_yaml_map(categories_path)
        categories = _categories(raw_categories.get("categories", []))

    return ArchiveConfig(
        gmail=gmail_rules,
        drive=drive_rules,
        categories=categories,
        drive_settings=drive_settings,
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


def _drive_rules(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        return _sequence(value.get("rules", []), "drive.rules")
    return _sequence(value, "drive")


def _drive_settings(value: Any) -> DriveSettings:
    if not isinstance(value, dict):
        return DriveSettings()

    return DriveSettings(
        inbox_folder_id=_optional_str(value, "inbox_folder_id", "drive"),
        archive_root_folder_id=_optional_str(value, "archive_root_folder_id", "drive"),
        category_folders=_string_map(value.get("category_folders", {}), "drive.category_folders"),
    )


def _string_map(value: Any, key: str) -> dict[str, str]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ConfigError(f"'{key}' deve essere una mappa.")

    result: dict[str, str] = {}
    for item_key, item_value in value.items():
        if not isinstance(item_key, str) or not item_key.strip():
            raise ConfigError(f"'{key}' contiene una chiave non valida.")
        if not isinstance(item_value, str) or not item_value.strip():
            raise ConfigError(f"'{key}.{item_key}' deve essere una stringa non vuota.")
        result[item_key.strip()] = item_value.strip()
    return result


def _categories(value: Any) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ConfigError("'categories' deve essere una lista.")

    categories: list[str] = []
    for index, item in enumerate(value, start=1):
        if not isinstance(item, str) or not item.strip():
            raise ConfigError(f"'categories[{index}]' deve essere una stringa non vuota.")
        categories.append(item.strip())
    return categories


def _load_yaml_map(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}

    if not isinstance(raw, dict):
        raise ConfigError("Il file YAML deve contenere una mappa al livello principale.")
    return raw


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
