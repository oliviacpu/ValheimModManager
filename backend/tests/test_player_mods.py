"""Mods players don't need are left out of exports (oliviacpu fork)."""

from __future__ import annotations

import io
import zipfile

import yaml

from app.models import ModProfile
from app.services import player_mods
from app.services import profiles as profile_service
from app.services.r2_profile import ProfileModSpec

from test_profiles import _patch_settings, _session, _settings

CATEGORIES = {
    "ArgusMagnus-ServersideQoL": ["Deep North Update", "Server-side"],
    "Neocor-ValheimAdmin": ["Utility", "Server-side", "Client-side"],
    "j1gA-LivingMap": ["Tweaks", "Client-side"],
    "Someone-Untagged": ["Tweaks"],
    "Hex-ServerThing": ["Server-only"],
}


class _Info:
    def __init__(self, cats: list[str]) -> None:
        self.categories = cats


def _use(monkeypatch, tmp_path):
    settings = _settings(tmp_path)
    settings.server_pack_manifest = None
    _patch_settings(monkeypatch, settings)
    monkeypatch.setattr("app.services.server_pack.get_settings", lambda: settings)
    monkeypatch.setattr("app.services.server_pack.get_package", lambda s, n: None)

    def fake_get_package(source: str, full_name: str):
        if full_name == "Hex-ServerThing":
            return _Info(CATEGORIES[full_name]) if source == "hexium" else None
        if source == "thunderstore" and full_name in CATEGORIES:
            return _Info(CATEGORIES[full_name])
        return None

    monkeypatch.setattr("app.services.player_mods.get_package", fake_get_package)
    return _session(tmp_path)


def test_defaults_from_tags(tmp_path, monkeypatch):
    db = _use(monkeypatch, tmp_path)
    got = {n: player_mods.players_need(db, n) for n in [*CATEGORIES, "Local-NotInStore"]}
    assert {n: (p.needed, p.origin) for n, p in got.items()} == {
        "ArgusMagnus-ServersideQoL": (False, "tags"),
        "Neocor-ValheimAdmin": (True, "tags"),
        "j1gA-LivingMap": (True, "tags"),
        "Someone-Untagged": (True, "default"),
        "Hex-ServerThing": (False, "tags"),
        "Local-NotInStore": (True, "default"),
    }


def test_override_and_reset(tmp_path, monkeypatch):
    db = _use(monkeypatch, tmp_path)
    assert player_mods.set_players_need(db, "Neocor-ValheimAdmin", False).origin == "you"
    assert player_mods.players_need(db, "Neocor-ValheimAdmin").needed is False
    assert player_mods.set_players_need(db, "ArgusMagnus-ServersideQoL", True).needed is True
    back = player_mods.set_players_need(db, "Neocor-ValheimAdmin", None)
    assert (back.needed, back.origin) == (True, "tags")


def test_export_leaves_out_server_only(tmp_path, monkeypatch):
    db = _use(monkeypatch, tmp_path)
    player_mods.set_players_need(db, "Neocor-ValheimAdmin", False)
    row = ModProfile(
        name="Friends",
        mods_json=profile_service._mods_to_json(
            [
                ProfileModSpec("ArgusMagnus-ServersideQoL", "2.5.1", True, "thunderstore"),
                ProfileModSpec("Neocor-ValheimAdmin", "1.0.0", True, "thunderstore"),
                ProfileModSpec("j1gA-LivingMap", "1.2.0", True, "thunderstore"),
                ProfileModSpec("Someone-Untagged", "0.1.0", True, "thunderstore"),
            ]
        ),
    )
    db.add(row)
    db.commit()
    data, _ = profile_service.build_export_zip(db, profile_id=row.id, mode="full", include_configs=False)
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        mods = yaml.safe_load(zf.read("export.r2x"))["mods"]
    assert [m["name"] for m in mods] == ["j1gA-LivingMap", "Someone-Untagged"]


def test_export_bundles_own_mods_players_need(tmp_path, monkeypatch):
    """Our own mods aren't on any store, so their files ride in the zip; server-only ones don't."""
    from app.models import InstalledPackage

    db = _use(monkeypatch, tmp_path)
    plugins = tmp_path / "bepinex" / "plugins"
    for folder, name in (("SmarterHoeUnlocks", "SmarterHoe Unlocks"), ("LivingWorld", "Living World")):
        d = plugins / folder
        d.mkdir()
        (d / f"{folder}.dll").write_bytes(b"MZ" + folder.encode())
        (d / "manifest.json").write_text("{}", encoding="utf-8")
        db.add(
            InstalledPackage(
                source="local",
                full_name=name,
                name=name,
                version="1.0.0",
                install_path=str(d),
                managed=True,
                enabled=True,
            )
        )
    db.commit()
    player_mods.set_players_need(db, "Living World", False)

    data, _ = profile_service.build_export_zip(db, mode="thunderstore", include_configs=False)
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        names = set(zf.namelist())
        assert zf.read("BepInEx/plugins/SmarterHoeUnlocks/SmarterHoeUnlocks.dll") == b"MZSmarterHoeUnlocks"
    assert "BepInEx/plugins/SmarterHoeUnlocks/manifest.json" in names
    assert not any(n.startswith("BepInEx/plugins/LivingWorld/") for n in names)
