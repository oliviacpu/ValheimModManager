"""BepInExPack from the server image: shown as installed and included in exports."""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import yaml

from app.config import Settings
from app.models import ModProfile
from app.services import profiles as profile_service
from app.services import server_pack
from app.services.r2_profile import ProfileModSpec

from test_profiles import _patch_settings, _session, _settings


class _Version:
    def __init__(self, number: str) -> None:
        self.version_number = number


class _Info:
    def __init__(self, latest: str) -> None:
        self.latest = _Version(latest)
        self.versions = [self.latest]


def _use(monkeypatch, settings: Settings, *, latest: str | None = "5.4.2399") -> None:
    _patch_settings(monkeypatch, settings)
    monkeypatch.setattr("app.services.server_pack.get_settings", lambda: settings)

    def fake_get_package(source: str, full_name: str):
        if latest and source == "thunderstore" and full_name == server_pack.BEPINEX_PACK:
            return _Info(latest)
        return None

    monkeypatch.setattr("app.services.server_pack.get_package", fake_get_package)


def _manifest(tmp_path: Path, **fields) -> Path:
    path = tmp_path / "server-pack" / "manifest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {"name": "BepInExPack_Valheim", "version_number": "5.4.2360", **fields}
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def _export_mods(zip_bytes: bytes) -> list[dict]:
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        return yaml.safe_load(zf.read("export.r2x"))["mods"]


def test_version_from_server_manifest(tmp_path, monkeypatch):
    settings = _settings(tmp_path)
    settings.server_pack_manifest = _manifest(tmp_path)
    _use(monkeypatch, settings)
    pack = server_pack.server_pack()
    assert pack is not None
    assert (pack.full_name, pack.version, pack.version_source) == (
        "denikson-BepInExPack_Valheim",
        "5.4.2360",
        "manifest",
    )


def test_falls_back_to_thunderstore_latest(tmp_path, monkeypatch):
    settings = _settings(tmp_path)
    settings.server_pack_manifest = tmp_path / "missing" / "manifest.json"
    _use(monkeypatch, settings)
    pack = server_pack.server_pack()
    assert pack is not None and (pack.version, pack.version_source) == ("5.4.2399", "thunderstore")


def test_ignores_other_manifests(tmp_path, monkeypatch):
    settings = _settings(tmp_path)
    settings.server_pack_manifest = _manifest(tmp_path, name="SomethingElse")
    _use(monkeypatch, settings, latest=None)
    assert server_pack.server_pack() is None


def test_export_lists_pack_first_and_once(tmp_path, monkeypatch):
    settings = _settings(tmp_path)
    settings.server_pack_manifest = _manifest(tmp_path)
    _use(monkeypatch, settings)
    db = _session(tmp_path)
    row = ModProfile(
        name="Friends",
        mods_json=profile_service._mods_to_json(
            [
                ProfileModSpec("denikson-BepInExPack_Valheim", "5.4.1000", True, "thunderstore"),
                ProfileModSpec("ValheimModding-Jotunn", "2.30.2", True, "thunderstore"),
            ]
        ),
    )
    db.add(row)
    db.commit()
    data, _ = profile_service.build_export_zip(db, profile_id=row.id, mode="full", include_configs=False)
    mods = _export_mods(data)
    assert [m["name"] for m in mods] == ["denikson-BepInExPack_Valheim", "ValheimModding-Jotunn"]
    assert mods[0]["version"] == {"major": 5, "minor": 4, "patch": 2360}
    assert mods[0]["enabled"] is True


def test_export_without_any_pack_source_is_unchanged(tmp_path, monkeypatch):
    settings = _settings(tmp_path)
    settings.server_pack_manifest = None
    _use(monkeypatch, settings, latest=None)
    mods = [ProfileModSpec("ValheimModding-Jotunn", "2.30.2", True, "thunderstore")]
    assert server_pack.with_server_pack(mods) == mods
