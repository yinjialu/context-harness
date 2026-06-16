from pathlib import Path

from context_harness.collectors.codex import sync_codex


def _write_session(path: Path, session_id: str, title: str, message: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                (
                    '{"timestamp":"2026-06-16T08:00:00Z","type":"session_meta",'
                    f'"payload":{{"id":"{session_id}","cwd":"/tmp/project","title":"{title}"}}}}'
                ),
                (
                    '{"timestamp":"2026-06-16T08:01:00Z","type":"event_msg",'
                    f'"payload":{{"role":"user","content":"{message}"}}}}'
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )


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


def test_sync_codex_discovers_nested_sessions_and_latest_uses_mtime(tmp_path):
    sessions_dir = tmp_path / "sessions"
    older = sessions_dir / "2026" / "06" / "15" / "older.jsonl"
    newer = sessions_dir / "2026" / "06" / "16" / "newer.jsonl"
    _write_session(older, "older-session", "Older Session", "旧会话")
    _write_session(newer, "newer-session", "Newer Session", "新会话")
    older.touch()
    newer.touch()

    output_dir = tmp_path / "out"
    result = sync_codex(sessions_dir, output_dir, tmp_path / "state.json", latest=1)

    archives = list(output_dir.glob("*.md"))
    assert result.checked == 1
    assert result.created == 1
    assert len(archives) == 1
    content = archives[0].read_text(encoding="utf-8")
    assert "新会话" in content
    assert "旧会话" not in content


def test_sync_codex_session_path_overrides_latest_mtime(tmp_path):
    sessions_dir = tmp_path / "sessions"
    older = sessions_dir / "older.jsonl"
    newer = sessions_dir / "newer.jsonl"
    _write_session(older, "older-session", "Older Session", "hook target")
    _write_session(newer, "newer-session", "Newer Session", "mtime winner")
    newer.touch()

    output_dir = tmp_path / "out"
    result = sync_codex(sessions_dir, output_dir, tmp_path / "state.json", latest=1, session_path=older)

    archives = list(output_dir.glob("*.md"))
    assert result.checked == 1
    assert result.created == 1
    assert len(archives) == 1
    content = archives[0].read_text(encoding="utf-8")
    assert "hook target" in content
    assert "mtime winner" not in content


def test_sync_codex_reads_response_item_message_content_arrays(tmp_path):
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    fixture = Path("tests/fixtures/codex-response-session.jsonl").read_text(encoding="utf-8")
    (sessions_dir / "real-codex-session-1.jsonl").write_text(fixture, encoding="utf-8")

    output_dir = tmp_path / "out"
    result = sync_codex(sessions_dir, output_dir, tmp_path / "state.json", latest=1)

    archives = list(output_dir.glob("*.md"))
    assert result.created == 1
    assert len(archives) == 1
    content = archives[0].read_text(encoding="utf-8")
    assert "- **Messages**: 2" in content
    assert "第一行\n第二行" in content
    assert "收到\n继续" in content


def test_sync_codex_bounds_archive_filename_for_long_titles(tmp_path):
    sessions_dir = tmp_path / "sessions"
    long_title = "Codex " + ("very-long-title-" * 30)
    _write_session(sessions_dir / "long.jsonl", "session-with-a-long-stable-id", long_title, "hello")

    output_dir = tmp_path / "out"
    result = sync_codex(sessions_dir, output_dir, tmp_path / "state.json", latest=1)

    archives = list(output_dir.glob("*.md"))
    assert result.created == 1
    assert len(archives) == 1
    assert len(archives[0].name) < 160
    assert archives[0].name.startswith("2026-06-16-session-with-a-long-stable-id-")


def test_sync_codex_counts_noise_files_as_checked_without_creating_archive(tmp_path):
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    (sessions_dir / "noise.jsonl").write_text(
        '{"timestamp":"2026-06-16T08:03:00Z","type":"tool_call","payload":{"name":"exec_command"}}\n',
        encoding="utf-8",
    )

    result = sync_codex(sessions_dir, tmp_path / "out", tmp_path / "state.json", latest=1)

    assert result.checked == 1
    assert result.created == 0
    assert result.updated == 0
    assert result.skipped == 0


def test_sync_codex_skips_bad_json_lines_and_keeps_valid_messages(tmp_path):
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    (sessions_dir / "bad-line.jsonl").write_text(
        "\n".join(
            [
                '{"timestamp":"2026-06-16T08:00:00Z","type":"session_meta","payload":{"id":"bad-line","title":"Bad Line"}}',
                "{bad json",
                '{"timestamp":"2026-06-16T08:01:00Z","type":"event_msg","payload":{"role":"user","content":"still works"}}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    output_dir = tmp_path / "out"
    result = sync_codex(sessions_dir, output_dir, tmp_path / "state.json", latest=1)

    archives = list(output_dir.glob("*.md"))
    assert result.checked == 1
    assert result.created == 1
    assert len(archives) == 1
    assert "still works" in archives[0].read_text(encoding="utf-8")
