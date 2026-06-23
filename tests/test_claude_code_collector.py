from pathlib import Path

from context_harness import okf
from context_harness.collectors.claude_code import sync_claude_code


def _write_session(path: Path, session_id: str, title: str, message: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                (
                    f'{{"sessionId":"{session_id}","timestamp":"2026-06-16T08:00:00Z",'
                    f'"type":"summary","summary":"{title}"}}'
                ),
                (
                    f'{{"sessionId":"{session_id}","timestamp":"2026-06-16T08:01:00Z",'
                    f'"type":"user","message":{{"role":"user","content":"{message}"}}}}'
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_sync_claude_code_captures_cwd_for_project_description(tmp_path):
    projects_dir = tmp_path / "projects"
    project_dir = projects_dir / "-Users-jialu-Documents-AuraCare"
    project_dir.mkdir(parents=True)
    (project_dir / "with-cwd.jsonl").write_text(
        "\n".join(
            [
                '{"sessionId":"cwd-session","timestamp":"2026-06-16T08:00:00Z","type":"summary","summary":"标题"}',
                (
                    '{"sessionId":"cwd-session","timestamp":"2026-06-16T08:01:00Z","cwd":"/Users/jialu/Documents/AuraCare",'
                    '"type":"user","message":{"role":"user","content":"你好"}}'
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    output_dir = tmp_path / "out"
    sync_claude_code(projects_dir, output_dir, tmp_path / "state.json", latest=1)

    content = next(output_dir.glob("*.md")).read_text(encoding="utf-8")
    fields, _ = okf.parse_frontmatter(content)
    assert fields["description"] == "claude-code · 1 messages · project AuraCare"
    assert fields["Cwd"] == "/Users/jialu/Documents/AuraCare"


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


def test_sync_claude_code_skips_unchanged_archive(tmp_path):
    projects_dir = tmp_path / "projects"
    _write_session(projects_dir / "-tmp-project" / "claude-session-1.jsonl", "claude-session-1", "Context Harness", "继续")

    output_dir = tmp_path / "out"
    state_path = tmp_path / "state.json"
    sync_claude_code(projects_dir, output_dir, state_path, latest=1)
    second = sync_claude_code(projects_dir, output_dir, state_path, latest=1)

    assert second.created == 0
    assert second.updated == 0
    assert second.skipped == 1


def test_sync_claude_code_keeps_subagent_files_with_shared_session_id_separate(tmp_path):
    projects_dir = tmp_path / "projects"
    _write_session(projects_dir / "-tmp-project" / "parent.jsonl", "shared-session", "Shared Session", "parent")
    _write_session(projects_dir / "-tmp-project" / "subagent.jsonl", "shared-session", "Shared Session", "subagent")

    output_dir = tmp_path / "out"
    state_path = tmp_path / "state.json"
    first = sync_claude_code(projects_dir, output_dir, state_path)
    second = sync_claude_code(projects_dir, output_dir, state_path)

    archives = sorted(output_dir.glob("*.md"))
    assert first.created == 2
    assert first.updated == 0
    assert len(archives) == 2
    assert archives[0].name == "20260616_shared-s.md"
    assert archives[1].name.startswith("20260616_shared-s_")
    assert any("parent" in archive.read_text(encoding="utf-8") for archive in archives)
    assert any("subagent" in archive.read_text(encoding="utf-8") for archive in archives)
    assert second.created == 0
    assert second.updated == 0
    assert second.skipped == 2


def test_sync_claude_code_discovers_nested_sessions_and_latest_uses_mtime(tmp_path):
    projects_dir = tmp_path / "projects"
    older = projects_dir / "2026" / "06" / "15" / "older.jsonl"
    newer = projects_dir / "2026" / "06" / "16" / "newer.jsonl"
    _write_session(older, "older-session", "Older Session", "旧会话")
    _write_session(newer, "newer-session", "Newer Session", "新会话")
    older.touch()
    newer.touch()

    output_dir = tmp_path / "out"
    result = sync_claude_code(projects_dir, output_dir, tmp_path / "state.json", latest=1)

    archives = list(output_dir.glob("*.md"))
    assert result.checked == 1
    assert result.created == 1
    assert len(archives) == 1
    content = archives[0].read_text(encoding="utf-8")
    assert "新会话" in content
    assert "旧会话" not in content


def test_sync_claude_code_session_path_overrides_latest_mtime(tmp_path):
    projects_dir = tmp_path / "projects"
    older = projects_dir / "older.jsonl"
    newer = projects_dir / "newer.jsonl"
    _write_session(older, "older-session", "Older Session", "hook target")
    _write_session(newer, "newer-session", "Newer Session", "mtime winner")
    newer.touch()

    output_dir = tmp_path / "out"
    result = sync_claude_code(projects_dir, output_dir, tmp_path / "state.json", latest=1, session_path=older)

    archives = list(output_dir.glob("*.md"))
    assert result.checked == 1
    assert result.created == 1
    assert len(archives) == 1
    content = archives[0].read_text(encoding="utf-8")
    assert "hook target" in content
    assert "mtime winner" not in content


def test_sync_claude_code_counts_noise_files_as_checked_without_creating_archive(tmp_path):
    projects_dir = tmp_path / "projects"
    projects_dir.mkdir()
    (projects_dir / "noise.jsonl").write_text(
        '{"sessionId":"noise","timestamp":"2026-06-16T08:03:00Z","type":"tool_result","content":"noise"}\n',
        encoding="utf-8",
    )

    result = sync_claude_code(projects_dir, tmp_path / "out", tmp_path / "state.json", latest=1)

    assert result.checked == 1
    assert result.created == 0
    assert result.updated == 0
    assert result.skipped == 0


def test_sync_claude_code_skips_meta_user_messages(tmp_path):
    projects_dir = tmp_path / "projects"
    projects_dir.mkdir()
    (projects_dir / "meta.jsonl").write_text(
        "\n".join(
            [
                '{"sessionId":"meta","timestamp":"2026-06-16T08:00:00Z","type":"summary","summary":"Meta"}',
                (
                    '{"sessionId":"meta","timestamp":"2026-06-16T08:01:00Z","type":"user","isMeta":true,'
                    '"message":{"role":"user","content":"internal reminder should not leak"}}'
                ),
                (
                    '{"sessionId":"meta","timestamp":"2026-06-16T08:02:00Z","type":"user",'
                    '"message":{"role":"user","content":"real user message"}}'
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    output_dir = tmp_path / "out"
    result = sync_claude_code(projects_dir, output_dir, tmp_path / "state.json", latest=1)

    archives = list(output_dir.glob("*.md"))
    assert result.created == 1
    assert len(archives) == 1
    content = archives[0].read_text(encoding="utf-8")
    assert "real user message" in content
    assert "internal reminder should not leak" not in content


def test_sync_claude_code_skips_bad_json_lines_and_keeps_valid_messages(tmp_path):
    projects_dir = tmp_path / "projects"
    projects_dir.mkdir()
    (projects_dir / "bad-line.jsonl").write_text(
        "\n".join(
            [
                '{"sessionId":"bad-line","timestamp":"2026-06-16T08:00:00Z","type":"summary","summary":"Bad Line"}',
                "{bad json",
                '{"sessionId":"bad-line","timestamp":"2026-06-16T08:01:00Z","type":"user","message":{"role":"user","content":"still works"}}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    output_dir = tmp_path / "out"
    result = sync_claude_code(projects_dir, output_dir, tmp_path / "state.json", latest=1)

    archives = list(output_dir.glob("*.md"))
    assert result.checked == 1
    assert result.created == 1
    assert len(archives) == 1
    assert "still works" in archives[0].read_text(encoding="utf-8")


def test_sync_claude_code_bounds_archive_filename_for_long_titles(tmp_path):
    projects_dir = tmp_path / "projects"
    long_title = "Claude " + ("very-long-title-" * 30)
    _write_session(projects_dir / "long.jsonl", "session-with-a-long-stable-id", long_title, "hello")

    output_dir = tmp_path / "out"
    result = sync_claude_code(projects_dir, output_dir, tmp_path / "state.json", latest=1)

    archives = list(output_dir.glob("*.md"))
    assert result.created == 1
    assert len(archives) == 1
    assert archives[0].name == "20260616_session-.md"


def test_sync_claude_code_removes_stale_archive_when_filename_scheme_changes(tmp_path):
    projects_dir = tmp_path / "projects"
    _write_session(projects_dir / "-tmp-project" / "long.jsonl", "session-with-a-long-stable-id", "Old Long Name", "hello")
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    old_archive = output_dir / "2026-06-16-session-with-a-long-stable-id-long-digest-old.md"
    old_archive.write_text("old", encoding="utf-8")
    state_path = tmp_path / "state.json"
    state_path.write_text(
        '{"claude-code":{"session-with-a-long-stable-id:-tmp-project/long.jsonl":{"archive":"2026-06-16-session-with-a-long-stable-id-long-digest-old.md","message_count":0,"source_path":"old"}}}',
        encoding="utf-8",
    )

    result = sync_claude_code(projects_dir, output_dir, state_path, latest=1)

    assert result.updated == 1
    assert not old_archive.exists()
    assert (output_dir / "20260616_session-.md").exists()


def test_sync_claude_code_uses_first_title_timestamp_for_filename(tmp_path):
    projects_dir = tmp_path / "projects"
    session = projects_dir / "-tmp-project" / "333d2d3f-8218-49a9-b99b-37987f3ba96f.jsonl"
    session.parent.mkdir(parents=True)
    session.write_text(
        "\n".join(
            [
                '{"sessionId":"333d2d3f-8218-49a9-b99b-37987f3ba96f","timestamp":"2026-06-16T13:00:00Z","type":"summary","summary":"first"}',
                '{"sessionId":"333d2d3f-8218-49a9-b99b-37987f3ba96f","timestamp":"2026-06-16T13:01:00Z","type":"user","message":{"role":"user","content":"hello"}}',
                '{"sessionId":"333d2d3f-8218-49a9-b99b-37987f3ba96f","timestamp":"2026-06-17T01:00:00Z","type":"summary","summary":"later"}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = sync_claude_code(projects_dir, tmp_path / "out", tmp_path / "state.json", latest=1)

    assert result.created == 1
    assert (tmp_path / "out" / "20260616_333d2d3f.md").exists()
    assert not (tmp_path / "out" / "20260617_333d2d3f.md").exists()


def test_sync_claude_code_uses_local_date_for_archive_filename(tmp_path, set_timezone):
    set_timezone("Asia/Shanghai")
    projects_dir = tmp_path / "projects"
    session = projects_dir / "-tmp-project" / "local-date.jsonl"
    session.parent.mkdir(parents=True)
    session.write_text(
        "\n".join(
            [
                '{"sessionId":"local-date","timestamp":"2026-06-16T20:00:00Z","type":"summary","summary":"Local Date"}',
                '{"sessionId":"local-date","timestamp":"2026-06-16T20:01:00Z","type":"user","message":{"role":"user","content":"hello"}}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = sync_claude_code(projects_dir, tmp_path / "out", tmp_path / "state.json", latest=1)

    assert result.created == 1
    assert (tmp_path / "out" / "20260617_local-da.md").exists()


def test_sync_claude_code_uses_title_events(tmp_path):
    projects_dir = tmp_path / "projects"
    projects_dir.mkdir()
    (projects_dir / "title.jsonl").write_text(
        "\n".join(
            [
                '{"sessionId":"title-session","timestamp":"2026-06-16T08:00:00Z","type":"ai-title","title":"AI Generated Title"}',
                '{"sessionId":"title-session","timestamp":"2026-06-16T08:01:00Z","type":"user","message":{"role":"user","content":"hello"}}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    output_dir = tmp_path / "out"
    result = sync_claude_code(projects_dir, output_dir, tmp_path / "state.json", latest=1)

    archives = list(output_dir.glob("*.md"))
    assert result.created == 1
    assert len(archives) == 1
    assert "# 2026-06-16 - AI Generated Title" in archives[0].read_text(encoding="utf-8")
