from pathlib import Path

from context_harness.collectors.hermes_agent import sync_hermes_agent


def _write_export(path: Path, session_id: str, title: str, message: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                (
                    f'{{"id":"{session_id}","source":"cli","model":"gpt-5.5",'
                    f'"title":"{title}","started_at":1781703009.0,'
                    f'"messages":[{{"role":"user","content":"{message}","timestamp":1781703010.0}}]}}'
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_sync_hermes_agent_writes_markdown_archive(tmp_path):
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    fixture = Path("tests/fixtures/hermes-agent-session.jsonl").read_text(encoding="utf-8")
    (sessions_dir / "hermes-export.jsonl").write_text(fixture, encoding="utf-8")

    output_dir = tmp_path / "out"
    state_path = tmp_path / "state.json"
    result = sync_hermes_agent(sessions_dir, output_dir, state_path, latest=1)

    archives = list(output_dir.glob("*.md"))
    assert result.created == 1
    assert result.skipped == 0
    assert len(archives) == 1
    content = archives[0].read_text(encoding="utf-8")
    assert "- **Source**: hermes-agent" in content
    assert "- **Messages**: 2" in content
    assert "- **Hermes Source**: cli" in content
    assert "- **Model**: gpt-5.5" in content
    assert "### **User**" in content
    assert "### **Assistant**" in content
    assert "tool noise" not in content


def test_sync_hermes_agent_skips_unchanged_archive(tmp_path):
    sessions_dir = tmp_path / "sessions"
    _write_export(sessions_dir / "export.jsonl", "hermes-session", "Context Harness", "hello")

    output_dir = tmp_path / "out"
    state_path = tmp_path / "state.json"
    sync_hermes_agent(sessions_dir, output_dir, state_path, latest=1)
    second = sync_hermes_agent(sessions_dir, output_dir, state_path, latest=1)

    assert second.created == 0
    assert second.updated == 0
    assert second.skipped == 1


def test_sync_hermes_agent_missing_source_dir_returns_empty_result(tmp_path):
    result = sync_hermes_agent(tmp_path / "missing", tmp_path / "out", tmp_path / "state.json", latest=1)

    assert result.checked == 0
    assert result.created == 0
    assert result.updated == 0
    assert result.skipped == 0


def test_sync_hermes_agent_discovers_nested_sessions_and_latest_uses_mtime(tmp_path):
    sessions_dir = tmp_path / "sessions"
    older = sessions_dir / "2026" / "06" / "15" / "older.jsonl"
    newer = sessions_dir / "2026" / "06" / "16" / "newer.jsonl"
    _write_export(older, "older-session", "Older Session", "旧会话")
    _write_export(newer, "newer-session", "Newer Session", "新会话")
    older.touch()
    newer.touch()

    output_dir = tmp_path / "out"
    result = sync_hermes_agent(sessions_dir, output_dir, tmp_path / "state.json", latest=1)

    archives = list(output_dir.glob("*.md"))
    assert result.checked == 1
    assert result.created == 1
    assert len(archives) == 1
    content = archives[0].read_text(encoding="utf-8")
    assert "新会话" in content
    assert "旧会话" not in content


def test_sync_hermes_agent_session_path_overrides_latest_mtime(tmp_path):
    sessions_dir = tmp_path / "sessions"
    older = sessions_dir / "older.jsonl"
    newer = sessions_dir / "newer.jsonl"
    _write_export(older, "older-session", "Older Session", "hook target")
    _write_export(newer, "newer-session", "Newer Session", "mtime winner")
    newer.touch()

    output_dir = tmp_path / "out"
    result = sync_hermes_agent(sessions_dir, output_dir, tmp_path / "state.json", latest=1, session_path=older)

    archives = list(output_dir.glob("*.md"))
    assert result.checked == 1
    assert result.created == 1
    assert len(archives) == 1
    content = archives[0].read_text(encoding="utf-8")
    assert "hook target" in content
    assert "mtime winner" not in content


def test_sync_hermes_agent_counts_noise_files_as_checked_without_creating_archive(tmp_path):
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    (sessions_dir / "noise.jsonl").write_text(
        '{"id":"noise","messages":[{"role":"tool","content":"noise"}]}\n',
        encoding="utf-8",
    )

    result = sync_hermes_agent(sessions_dir, tmp_path / "out", tmp_path / "state.json", latest=1)

    assert result.checked == 1
    assert result.created == 0
    assert result.updated == 0
    assert result.skipped == 0


def test_sync_hermes_agent_skips_bad_json_lines_and_keeps_valid_messages(tmp_path):
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    (sessions_dir / "bad-line.jsonl").write_text(
        "\n".join(
            [
                "{bad json",
                '{"id":"bad-line","title":"Bad Line","started_at":"2026-06-16T08:00:00Z","messages":[{"role":"user","content":"still works","timestamp":"2026-06-16T08:01:00Z"}]}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    output_dir = tmp_path / "out"
    result = sync_hermes_agent(sessions_dir, output_dir, tmp_path / "state.json", latest=1)

    archives = list(output_dir.glob("*.md"))
    assert result.checked == 1
    assert result.created == 1
    assert len(archives) == 1
    assert "still works" in archives[0].read_text(encoding="utf-8")


def test_sync_hermes_agent_bounds_archive_filename_for_long_titles(tmp_path):
    sessions_dir = tmp_path / "sessions"
    long_title = "Hermes " + ("very-long-title-" * 30)
    _write_export(sessions_dir / "long.jsonl", "session-with-a-long-stable-id", long_title, "hello")

    output_dir = tmp_path / "out"
    result = sync_hermes_agent(sessions_dir, output_dir, tmp_path / "state.json", latest=1)

    archives = list(output_dir.glob("*.md"))
    assert result.created == 1
    assert len(archives) == 1
    assert archives[0].name.startswith("20260617_session-")


def test_sync_hermes_agent_same_day_date_prefixed_ids_do_not_collide(tmp_path):
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    # Both sessions carry date-prefixed ids (as Hermes canonical export produces)
    # and share the same started_at date. Without the fix, both resolve to
    # "20260617_20260617.md" and the second overwrites the first.
    (sessions_dir / "morning.jsonl").write_text(
        '{"id":"20260617_090000_111111","title":"Morning","started_at":1781703009.0,'
        '"messages":[{"role":"user","content":"morning task","timestamp":1781703010.0}]}\n',
        encoding="utf-8",
    )
    (sessions_dir / "afternoon.jsonl").write_text(
        '{"id":"20260617_153009_297382","title":"Afternoon","started_at":1781703009.0,'
        '"messages":[{"role":"user","content":"afternoon task","timestamp":1781703010.0}]}\n',
        encoding="utf-8",
    )

    output_dir = tmp_path / "out"
    result = sync_hermes_agent(sessions_dir, output_dir, tmp_path / "state.json")

    archives = sorted(output_dir.glob("*.md"))
    assert result.created == 2, f"expected 2 created, got {result.created}"
    assert len(archives) == 2, f"expected 2 archives, got: {[a.name for a in archives]}"
    names = {a.name for a in archives}
    assert "20260617_20260617.md" not in names, "date-prefix collision filename detected"
    assert any("morning task" in a.read_text(encoding="utf-8") for a in archives)
    assert any("afternoon task" in a.read_text(encoding="utf-8") for a in archives)


def test_sync_hermes_agent_reads_session_json_snapshots(tmp_path):
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    (sessions_dir / "snapshot.json").write_text(
        '{"id":"snapshot-session","title":"Snapshot","started_at":"2026-06-16T08:00:00Z","messages":[{"role":"user","content":"json snapshot","timestamp":"2026-06-16T08:01:00Z"}]}',
        encoding="utf-8",
    )

    output_dir = tmp_path / "out"
    result = sync_hermes_agent(sessions_dir, output_dir, tmp_path / "state.json", latest=1)

    archives = list(output_dir.glob("*.md"))
    assert result.created == 1
    assert len(archives) == 1
    assert "json snapshot" in archives[0].read_text(encoding="utf-8")
