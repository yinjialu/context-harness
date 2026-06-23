from __future__ import annotations

import re
import stat
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_NAMES = ("init-context", "sync-conversations", "profile-dreamer")
PINNED_REF_RE = re.compile(r"CONTEXT_HARNESS_REF:-v\d")
LATEST_TAG_CMD = "git tag -l 'v*' --sort=-v:refname"


def test_bootstrap_scripts_are_present_executable_and_identical() -> None:
    scripts = [ROOT / "skills" / name / "scripts" / "bootstrap.sh" for name in SKILL_NAMES]
    contents = [script.read_text(encoding="utf-8") for script in scripts]

    assert len(set(contents)) == 1
    for script in scripts:
        assert script.exists()
        assert script.stat().st_mode & stat.S_IXUSR


def test_bootstrap_default_ref_follows_latest_release_tag() -> None:
    script = (ROOT / "skills" / "init-context" / "scripts" / "bootstrap.sh").read_text(encoding="utf-8")

    # Default ref is empty (no hardcoded version pin) and resolved to the
    # highest semver tag at runtime, so a release never touches this script.
    assert 'runtime_ref="${CONTEXT_HARNESS_REF:-}"' in script
    assert LATEST_TAG_CMD in script
    assert not PINNED_REF_RE.search(script)


def test_install_script_default_ref_follows_latest_release_tag() -> None:
    script = (ROOT / "scripts" / "install.sh").read_text(encoding="utf-8")

    assert 'runtime_ref="${CONTEXT_HARNESS_REF:-}"' in script
    assert LATEST_TAG_CMD in script
    assert not PINNED_REF_RE.search(script)


def test_pyproject_version_is_single_sourced_from_package() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    # The version lives only in context_harness/__init__.py; pyproject reads it
    # dynamically rather than duplicating the literal.
    assert "version" in pyproject["project"].get("dynamic", [])
    assert "version" not in pyproject["project"]


def test_install_script_is_executable() -> None:
    script = ROOT / "scripts" / "install.sh"

    assert script.exists()
    assert script.stat().st_mode & stat.S_IXUSR


def test_skills_document_runtime_bootstrap() -> None:
    for name in SKILL_NAMES:
        skill_doc = (ROOT / "skills" / name / "SKILL.md").read_text(encoding="utf-8")
        assert "## Runtime Bootstrap" in skill_doc
        assert 'runtime_dir="$(bash scripts/bootstrap.sh)"' in skill_doc
