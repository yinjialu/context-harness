from __future__ import annotations

import stat
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_NAMES = ("init-context", "sync-conversations", "profile-dreamer")


def test_bootstrap_scripts_are_present_executable_and_identical() -> None:
    scripts = [ROOT / "skills" / name / "scripts" / "bootstrap.sh" for name in SKILL_NAMES]
    contents = [script.read_text(encoding="utf-8") for script in scripts]

    assert len(set(contents)) == 1
    for script in scripts:
        assert script.exists()
        assert script.stat().st_mode & stat.S_IXUSR


def test_bootstrap_default_ref_matches_project_version() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    version = pyproject["project"]["version"]
    script = (ROOT / "skills" / "init-context" / "scripts" / "bootstrap.sh").read_text(encoding="utf-8")

    assert f'runtime_ref="${{CONTEXT_HARNESS_REF:-v{version}}}"' in script


def test_skills_document_runtime_bootstrap() -> None:
    for name in SKILL_NAMES:
        skill_doc = (ROOT / "skills" / name / "SKILL.md").read_text(encoding="utf-8")
        assert "## Runtime Bootstrap" in skill_doc
        assert 'runtime_dir="$(bash scripts/bootstrap.sh)"' in skill_doc
