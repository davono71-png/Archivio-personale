from dataclasses import dataclass


@dataclass(frozen=True)
class ActionResult:
    """A single item considered by an archiving rule."""

    service: str
    item_id: str
    rule_name: str
    action: str
    dry_run: bool
    skipped: bool = False
    detail: str = ""
