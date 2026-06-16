from pathlib import Path

from context_harness.collectors.claude_code import sync_claude_code


def test_sync_claude_code_writes_markdown_archive(tmp_path):
    projects_dir = tmp_path / "projects"
    project_dir = projects_dir / "-tmp-project"
    project_dir.mkdir(parents=True)
    fixture = Path("tests/fixtures/claude-code-session.jsonl").read_text(encoding="utf-8")
    (project_dir / "claude-session-1.jsonl").write_text(fixture, encoding="utf-8")

    output_dir = tmp_path / "out"
    state_path = tmp_path / "state.json"
    result = sync_claude_code(projects_dir, output_dir, state_path, latest=1)

    archives = list(output_dir.glob("*.md"))
    assert result.created == 1
    assert len(archives) == 1
    content = archives[0].read_text(encoding="utf-8")
    assert "- **Source**: claude-code" in content
    assert "- **Messages**: 2" in content
    assert "### **User** 08:01" in content
    assert "### **Assistant** 08:02" in content
    assert "tool_result" not in content


def test_sync_claude_code_missing_source_dir_returns_empty_result(tmp_path):
    result = sync_claude_code(tmp_path / "missing", tmp_path / "out", tmp_path / "state.json", latest=1)

    assert result.checked == 0
    assert result.created == 0
    assert result.updated == 0
    assert result.skipped == 0
