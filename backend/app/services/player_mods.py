"""Which mods players need (oliviacpu fork).

Exports and share codes are for players, so they leave out mods that only run on the server.
Thunderstore and Hexium tag packages with client/server categories, but authors choose those
tags, so they are only the default: a mod is server-only when it is tagged server-side and not
client-side. Anything else, including mods with no store entry, counts as needed. The admin can
override any mod on the Installed page; overrides are stored in PlayerRequirement.

Dropping a mod here never breaks a pack: if a kept mod depends on it, Gale and r2modman still
install it as a dependency.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from ..models import PlayerRequirement
from .packages import get_package
from .r2_profile import ProfileModSpec

SERVER_ONLY_CATEGORIES = frozenset({"Server-side", "Server-only"})
CLIENT_CATEGORIES = frozenset({"Client-side", "Client-only", "Client & Server", "Client (& Server)"})


@dataclass
class PlayersNeed:
    needed: bool
    # "you": set on the Installed page; "tags": from store categories; "default": no tags
    origin: str


def _categories(full_name: str, source: str | None) -> set[str] | None:
    sources = [source] if source in ("thunderstore", "hexium") else []
    sources += [s for s in ("thunderstore", "hexium") if s not in sources]
    for src in sources:
        try:
            info = get_package(src, full_name)
        except Exception:
            info = None
        if info is not None:
            return set(info.categories)
    return None


def from_tags(full_name: str, source: str | None = None) -> PlayersNeed:
    cats = _categories(full_name, source)
    if not cats or not (cats & (SERVER_ONLY_CATEGORIES | CLIENT_CATEGORIES)):
        return PlayersNeed(True, "default")
    server_only = bool(cats & SERVER_ONLY_CATEGORIES) and not (cats & CLIENT_CATEGORIES)
    return PlayersNeed(not server_only, "tags")


def overrides(db: Session) -> dict[str, bool]:
    return {r.full_name: bool(r.players_need) for r in db.query(PlayerRequirement).all()}


def players_need(
    db: Session,
    full_name: str,
    source: str | None = None,
    *,
    known: dict[str, bool] | None = None,
) -> PlayersNeed:
    known = overrides(db) if known is None else known
    if full_name in known:
        return PlayersNeed(known[full_name], "you")
    return from_tags(full_name, source)


def set_players_need(db: Session, full_name: str, needed: bool | None) -> PlayersNeed:
    """Set an override, or clear it (needed=None) to go back to the store tags."""
    row = db.get(PlayerRequirement, full_name)
    if needed is None:
        if row is not None:
            db.delete(row)
    elif row is None:
        db.add(PlayerRequirement(full_name=full_name, players_need=needed))
    else:
        row.players_need = needed
    db.commit()
    return players_need(db, full_name)


def for_players(db: Session, mods: list[ProfileModSpec]) -> list[ProfileModSpec]:
    """Drop mods players don't need from an export's mod list."""
    known = overrides(db)
    return [m for m in mods if players_need(db, m.full_name, m.source, known=known).needed]
