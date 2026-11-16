"""The BepInEx pack the Valheim server image provides.

The manager never installs or tracks BepInExPack itself (the server image ships it), but players
still need it. Exports and share codes include it at the server's version so Gale and r2modman
install it, and the Installed page lists it as provided by the server.

The version comes from the pack's Thunderstore manifest as the server unpacked it (CVT/lloesche:
/opt/valheim/dl/bepinex/extracted/manifest.json, mounted read-only at SERVER_PACK_MANIFEST). If that
isn't mounted, the newest version in the cached Thunderstore index is used instead.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from ..config import get_settings
from .packages import get_package
from .r2_profile import ProfileModSpec

logger = logging.getLogger(__name__)

BEPINEX_PACK = "denikson-BepInExPack_Valheim"


@dataclass
class ServerPack:
    full_name: str
    name: str
    version: str
    # "manifest": read from the server's unpacked pack; "thunderstore": newest in the index
    version_source: str


def _manifest_version() -> str | None:
    path = get_settings().server_pack_manifest
    if path is None:
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as exc:
        logger.warning("Could not read server BepInEx manifest %s: %s", path, exc)
        return None
    if data.get("name") != "BepInExPack_Valheim":
        logger.warning("%s is not the BepInExPack_Valheim manifest", path)
        return None
    version = str(data.get("version_number") or "").strip()
    return version or None


def server_pack() -> ServerPack | None:
    version = _manifest_version()
    if version:
        return ServerPack(BEPINEX_PACK, "BepInExPack Valheim", version, "manifest")
    try:
        info = get_package("thunderstore", BEPINEX_PACK)
    except Exception as exc:
        logger.info("Thunderstore index unavailable for %s: %s", BEPINEX_PACK, exc)
        info = None
    if info and info.latest:
        return ServerPack(BEPINEX_PACK, "BepInExPack Valheim", info.latest.version_number, "thunderstore")
    return None


def with_server_pack(mods: list[ProfileModSpec]) -> list[ProfileModSpec]:
    """Put the server's BepInExPack first in an export's mod list (replacing any listed one)."""
    pack = server_pack()
    rest = [m for m in mods if m.full_name != BEPINEX_PACK]
    if pack is None:
        return rest
    return [ProfileModSpec(pack.full_name, pack.version, True, "thunderstore"), *rest]
