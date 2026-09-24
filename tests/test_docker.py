"""Docker / bind-mount persistence tests for Samjon Memory.

Verifies the Compose + Portainer stack declare host bind mounts (not a named
volume), the external category-cover root is honoured with the packaged-dir
default preserved, the startup writeability check behaves, and the PowerShell
helper scripts create host dirs and never remove volumes.
"""
import pathlib

import pytest
import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _compose():
    with open(ROOT / "compose.yaml", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _stack():
    with open(ROOT / "samjon_stack.yaml", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


# ---- Compose: bind mounts, no named volume --------------------------------

def test_compose_has_no_named_data_volume():
    c = _compose()
    assert "volumes" not in c        # no top-level named-volume declaration
    assert "samjon_memory_data" not in str(c)
    mounts = c["services"]["samjon-memory"]["volumes"]
    assert all(m.get("type") == "bind" for m in mounts)


def test_compose_data_binds_host_data_to_app_data():
    mounts = list(_compose()["services"]["samjon-memory"]["volumes"])
    assert {"type": "bind", "source": "./data", "target": "/app/data"} in mounts


def test_compose_category_covers_bind_read_only():
    mounts = list(_compose()["services"]["samjon-memory"]["volumes"])
    assert {"type": "bind", "source": "./category-covers",
            "target": "/app/category-covers", "read_only": True} in mounts


def test_compose_environment_uses_app_category_covers():
    env = _compose()["services"]["samjon-memory"]["environment"]
    assert env["SAMJON_CATEGORY_COVERS_ROOT"] == "/app/category-covers"


def test_stack_is_valid_and_uses_absolute_example_paths():
    s = _stack()
    mounts = [dict(m) for m in s["services"]["samjon-memory"]["volumes"]]
    assert mounts[0]["source"].startswith("/absolute/path/to/")
    assert mounts[0]["target"] == "/app/data"
    assert mounts[1]["source"].startswith("/absolute/path/to/")
    assert mounts[1]["target"] == "/app/category-covers" and mounts[1]["read_only"] is True
    text = (ROOT / "samjon_stack.yaml").read_text(encoding="utf-8")
    # The developer example is clearly marked (documented, not hard-coded).
    assert "D:/HomeAssistant/samjon-memory/data:/app/data" in text
    assert "example" in text.lower()


# ---- Category-cover root ---------------------------------------------------

def test_category_covers_root_config_exists():
    import samjon_memory.config as cfg
    assert hasattr(cfg.config, "category_covers_root")


def test_default_category_covers_is_packaged_dir(monkeypatch):
    import samjon_memory.portal.pages as pages
    monkeypatch.delenv("SAMJON_CATEGORY_COVERS_ROOT", raising=False)
    assert str(pages._category_covers_dir()).endswith("category-covers")


def test_external_category_covers_root(monkeypatch, tmp_path):
    import samjon_memory.portal.pages as pages
    monkeypatch.setenv("SAMJON_CATEGORY_COVERS_ROOT", str(tmp_path))
    assert pages._category_covers_dir() == tmp_path


def test_external_configured_cover_wins(monkeypatch, tmp_path):
    import samjon_memory.portal.pages as pages
    monkeypatch.setenv("SAMJON_CATEGORY_COVERS_ROOT", str(tmp_path))
    (tmp_path / "pets.webp").write_bytes(b"x")
    cat = {**pages.category_by_key("pets"),
           "entity_cover": {"media_id": "m1", "alt_text": "alt"}}
    conf = pages._configured_category_cover(cat)
    assert conf and conf["url"] == "/portal/static/category-covers/pets.webp"
    html = pages._category_card(cat)                      # configured beats entity
    assert "/portal/static/category-covers/pets.webp" in html
    assert "/portal/media/m1/thumb" not in html


def test_missing_external_cover_falls_back(monkeypatch, tmp_path):
    import samjon_memory.portal.pages as pages
    from samjon_memory.portal import viewmodels
    monkeypatch.setenv("SAMJON_CATEGORY_COVERS_ROOT", str(tmp_path))  # empty dir
    cat = {**pages.category_by_key("pets"),
           "entity_cover": {"media_id": "m9", "alt_text": "a"}}
    assert pages._configured_category_cover(cat) == {}
    vm = viewmodels.category_cover_vm(cat)                # falls back to entity cover
    assert "/portal/media/m9/thumb" in vm["src"]


# ---- Startup writeability check -------------------------------------------

def test_ensure_data_writeable_creates_dirs(tmp_path):
    from samjon_memory.core.startup import ensure_data_writeable
    db = str(tmp_path / "app" / "data" / "samjon_core.sqlite")
    media = str(tmp_path / "app" / "data" / "media")
    assert ensure_data_writeable(db, media) is True
    assert (tmp_path / "app" / "data").is_dir()
    assert (tmp_path / "app" / "data" / "media").is_dir()


def test_ensure_data_writeable_raises_when_not_writable(tmp_path, monkeypatch):
    from samjon_memory.core.startup import ensure_data_writeable
    monkeypatch.setattr("os.access", lambda _p, _m: False)
    with pytest.raises(RuntimeError):
        ensure_data_writeable(str(tmp_path / "db" / "x.sqlite"),
                              str(tmp_path / "media"))


def test_main_registers_startup_writeability_check():
    src = (ROOT / "src" / "samjon_memory" / "core" / "main.py").read_text(encoding="utf-8")
    assert "ensure_data_writeable" in src
    assert "is_development" in src


# ---- PowerShell helper scripts ----------------------------------------------

def test_docker_up_creates_required_host_dirs():
    text = (ROOT / "scripts" / "docker-up.ps1").read_text(encoding="utf-8")
    for d in ("data\\media\\originals", "data\\media\\thumbnails",
              "data\\media\\archived", "data\\backups", "category-covers"):
        assert d in text
    # Resolves the repository root independently of the caller's CWD.
    assert "$PSScriptRoot" in text
    assert "New-Item -ItemType Directory" in text


def test_docker_down_never_removes_volumes():
    text = (ROOT / "scripts" / "docker-down.ps1").read_text(encoding="utf-8")
    assert "docker compose down" in text
    assert "down -v" not in text
    assert "--volumes" not in text
    assert "-v" not in text