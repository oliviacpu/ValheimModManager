"""A rescan keeps the store version when a plugin folder has no manifest (oliviacpu fork)."""

from __future__ import annotations

from app.models import InstalledPackage

from test_install_update_regressions import _session, _settings


def _scan(tmp_path, monkeypatch, *, source: str):
    from app.services import packages as pkgmod
    from app.services import scanner as scanner_mod

    settings = _settings(tmp_path)
    folder = settings.plugins_dir / "SeasonedProfessionals-OdinEye"
    folder.mkdir()
    (folder / "OdinEye.dll").write_bytes(b"MZ")
    db = _session(tmp_path)
    db.add(
        InstalledPackage(
            source=source,
            full_name="SeasonedProfessionals-OdinEye",
            name="odineye",
            version="1.2.39",
            install_path=str(folder),
            managed=True,
            enabled=True,
        )
    )
    db.commit()

    monkeypatch.setattr(scanner_mod, "get_settings", lambda: settings)
    monkeypatch.setattr(scanner_mod, "set_setting", lambda *a, **k: None)
    monkeypatch.setattr(scanner_mod, "log_activity", lambda *a, **k: None)
    monkeypatch.setattr(
        scanner_mod,
        "read_bepinex_plugin_metadata",
        lambda *_a, **_k: type(
            "M", (), {"guid": "org.bepinex.plugins.odineye", "name": "odineye", "version": "1.0.0.0"}
        )(),
    )
    monkeypatch.setattr(pkgmod, "match_installed_to_remote", lambda *a, **k: None)
    scanner_mod.persist_scan(db, settings)
    return db.query(InstalledPackage).filter_by(full_name="SeasonedProfessionals-OdinEye").one()


def test_store_version_survives_dll_only_scan(tmp_path, monkeypatch):
    row = _scan(tmp_path, monkeypatch, source="thunderstore")
    assert row.version == "1.2.39"
    assert row.plugin_guid == "org.bepinex.plugins.odineye"


def test_local_mod_still_takes_dll_version(tmp_path, monkeypatch):
    row = _scan(tmp_path, monkeypatch, source="local")
    assert row.version == "1.0.0.0"
