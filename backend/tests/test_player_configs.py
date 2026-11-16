"""Profiles keep only settings; exports keep only settings players need (oliviacpu fork)."""

from __future__ import annotations

import io
import zipfile

from app.models import InstalledPackage, ModProfile
from app.services import profiles as profile_service
from app.services import r2_profile

from test_player_mods import _use


def _tree(root):
    """The Valheim stack's layout: settings at the root, and the same dir mounted again at config/."""
    files = {
        "BepInEx.cfg": "[Logging.Disk]\nLogLevels = Warning\n",
        "RustyMods.UsefulPaths.cfg": "[Paved]\nSpeed Modifier = 1.15\n",
        "ArgusMagnus.ServersideQoL.cfg": "[General]\nEnabled = true\n",
        "neocor.ValheimAdmin.cfg": "## Web admin password\nAdminPassword = hunter2\nPort = 8080\n",
        "GrundleLord.Inferno.cfg.bak-2026-11-16": "old",
        "BepInEx.cfg.default": "default",
        "notes.json": "{}",
        "Seasonality/Tweaks/Plants.yml": "plants: []\n",
        "Seasonality/seasonality.log": "log",
        "ArgusMagnus.ServersideQoL/templates/ArgusMagnus.ServersideQoL.Advanced.yml": "x: 1\n",
        "ArgusMagnus.ServersideQoL/rules.yml": "y: 2\n",
        "ValheimAdmin/players.json": '{"Olivia": {}}',
        "ValheimWebMap/Field Trip/history.json": "[]",
        "plugins/RustyMods-UsefulPaths/manifest.json": "{}",
        "config/plugins/GrundleLord-Inferno/sample-config.cfg": "[x]\n",
        "config/plugins/RustyMods-UsefulPaths/manifest.json": "{}",
        "config/RustyMods.UsefulPaths.cfg": "[Paved]\nSpeed Modifier = 1.15\n",
    }
    for rel, text in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


def test_profile_keeps_only_settings(tmp_path):
    root = tmp_path / "flat"
    _tree(root)
    assert sorted(r2_profile.collect_bepinex_configs(root)) == [
        "config/ArgusMagnus.ServersideQoL.cfg",
        "config/ArgusMagnus.ServersideQoL/rules.yml",
        "config/BepInEx.cfg",
        "config/RustyMods.UsefulPaths.cfg",
        "config/Seasonality/Tweaks/Plants.yml",
        "config/neocor.ValheimAdmin.cfg",
    ]


def test_export_keeps_only_settings_players_need(tmp_path, monkeypatch):
    db = _use(monkeypatch, tmp_path)
    for full_name, guid in (
        ("ArgusMagnus-ServersideQoL", "ArgusMagnus.ServersideQoL"),
        ("Neocor-ValheimAdmin", None),
        ("RustyMods-UsefulPaths", "RustyMods.UsefulPaths"),
    ):
        db.add(
            InstalledPackage(
                source="thunderstore",
                full_name=full_name,
                name=full_name.split("-", 1)[1],
                version="1.0.0",
                plugin_guid=guid,
                install_path=str(tmp_path / "bepinex" / "plugins" / full_name),
                managed=True,
                enabled=True,
            )
        )
    row = ModProfile(name="FieldTrip", mods_json="[]")
    db.add(row)
    db.commit()
    stored = tmp_path / "flat"
    _tree(stored)
    profile_service._store_configs(row.id, r2_profile.collect_bepinex_configs(stored))

    data, _ = profile_service.build_export_zip(db, profile_id=row.id, mode="full", include_configs=True)
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        configs = sorted(n.removeprefix("BepInEx/") for n in zf.namelist() if n.startswith("BepInEx/config/"))
    # ServersideQoL is server-only (tags), ValheimAdmin's file holds a password, BepInEx.cfg is the server's.
    assert configs == [
        "config/RustyMods.UsefulPaths.cfg",
        "config/Seasonality/Tweaks/Plants.yml",
    ]


def test_old_stored_profiles_are_filtered_on_export(tmp_path, monkeypatch):
    """Profiles saved before this change still hold data files; the export drops them."""
    db = _use(monkeypatch, tmp_path)
    row = ModProfile(name="Old", mods_json="[]")
    db.add(row)
    db.commit()
    profile_service._store_configs(
        row.id,
        {
            "config/j1ga.livingmap.cfg": b"[01 General]\nEnabled = true\n",
            "config/ValheimAdmin/sessions.json": b"[]",
            "config/plugins/j1gA-LivingMap/manifest.json": b"{}",
        },
    )
    data, _ = profile_service.build_export_zip(db, profile_id=row.id, mode="full", include_configs=True)
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        configs = [n.removeprefix("BepInEx/") for n in zf.namelist() if n.startswith("BepInEx/config/")]
    assert configs == ["config/j1ga.livingmap.cfg"]
