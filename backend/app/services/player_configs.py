"""Which config files go to players in an export (oliviacpu fork).

A profile keeps the server's settings so it can be restored on the server. A pack is for
players, so it carries only settings files (see r2_profile.is_setting_file) of mods players
get, and never:

- BepInEx.cfg: the server's own loader settings, not the players'.
- Settings of server-only mods (player_mods): the top-level ``<plugin GUID>.cfg`` and the mod's
  own config folder.
- Any file with a password, secret, token or API key setting, whatever mod it belongs to.
"""

from __future__ import annotations

import re
from pathlib import PurePosixPath

from sqlalchemy.orm import Session

from ..models import InstalledPackage
from . import player_mods
from .r2_profile import _disk_rel_from_profile_config, is_setting_file

# "AdminPassword = x", "AgentSecretFile = x", "api_key: x"; matched on the setting name only.
_SECRET_SETTING = re.compile(
    r"^\s*[A-Za-z0-9_. -]*(password|passwd|secret|token|api[_ -]?key)[A-Za-z0-9_. -]*\s*[=:]",
    re.IGNORECASE | re.MULTILINE,
)


def server_only_names(db: Session) -> set[str]:
    """Lower-case names a server-only mod's settings go by: its plugin GUID (the .cfg name)
    and its package names (config folders)."""
    known = player_mods.overrides(db)
    names: set[str] = set()
    for pkg in db.query(InstalledPackage).all():
        if player_mods.players_need(db, pkg.full_name, pkg.source, known=known).needed:
            continue
        for name in (pkg.plugin_guid, pkg.name, pkg.full_name, pkg.full_name.split("-", 1)[-1]):
            if name:
                names.add(name.lower())
    return names


def has_secret(content: bytes) -> bool:
    return bool(_SECRET_SETTING.search(content.decode("utf-8", errors="replace")))


def for_players(db: Session, files: dict[str, bytes]) -> dict[str, bytes]:
    server_only = server_only_names(db)
    out: dict[str, bytes] = {}
    for rel, content in files.items():
        disk_rel = _disk_rel_from_profile_config(rel)
        if not is_setting_file(disk_rel) or disk_rel == "BepInEx.cfg":
            continue
        parts = PurePosixPath(disk_rel).parts
        owner = PurePosixPath(disk_rel).stem if len(parts) == 1 else parts[0]
        if owner.lower() in server_only or has_secret(content):
            continue
        out[rel] = content
    return out
