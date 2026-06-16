from pathlib import Path

from context_harness.collectors.codex import sync_codex


def test_sync_codex_writes_markdown_archive(tmp_path):
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    fixture = Path("tests/fixtures/codex-session.jsonl").read_text(encoding="utf-8")
    (sessions_dir / "codex-session-1.jsonl").write_text(fixture, encoding="utf-8")

    output_dir = tmp_path / "out"
    state_path = tmp_path / "state.json"
    result = sync_codex(sessions_dir, output_dir, state_path, latest=1)

    archives = list(output_dir.glob("*.md"))
    assert result.created == 1
    assert result.skipped == 0
    assert len(archives) == 1
    content = archives[0].read_text(encoding="utf-8")
    assert "- **Source**: codex" in content
    assert "- **Messages**: 2" in content
    assert "### **User** 08:01" in content
    assert "### **Assistant** 08:02" in content
    assert "tool_call" not in content


def test_sync_codex_skips_unchanged_archive(tmp_path):
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    fixture = Path("tests/fixtures/codex-session.jsonl").read_text(encoding="utf-8")
    (sessions_dir / "codex-session-1.jsonl").write_text(fixture, encoding="utf-8")

    output_dir = tmp_path / "out"
    state_path = tmp_path / "state.json"
    sync_codex(sessions_dir, output_dir, state_path, latest=1)
    second = sync_codex(sessions_dir, output_dir, state_path, latest=1)

    assert second.created == 0
    assert second.updated == 0
    assert second.skipped == 1


def test_sync_codex_missing_source_dir_returns_empty_result(tmp_path):
    result = sync_codex(tmp_path / "missing", tmp_path / "out", tmp_path / "state.json", latest=1)

    assert result.checked == 0
    assert result.created == 0
    assert result.updated == 0
    assert result.skipped == 0
