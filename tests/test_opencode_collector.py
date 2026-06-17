import json
import sqlite3
from pathlib import Path

from context_harness.collectors.opencode import sync_opencode


def _create_opencode_db(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        create table session (
            id text primary key,
            title text not null,
            directory text not null,
            agent text,
            model text,
            time_created integer not null,
            time_updated integer not null
        );
        create table message (
            id text primary key,
            session_id text not null,
            time_created integer not null,
            time_updated integer not null,
            data text not null
        );
        create table part (
            id text primary key,
            message_id text not null,
            session_id text not null,
            time_created integer not null,
            time_updated integer not null,
            data text not null
        );
        """
    )
    connection.commit()
    connection.close()


def _insert_session(
    db_path: Path,
    session_id: str,
    title: str,
    user_text: str,
    assistant_text: str = "Assistant reply",
    created: int = 1781596800000,
    updated: int | None = None,
) -> None:
    updated = updated or created + 120_000
    connection = sqlite3.connect(db_path)
    connection.execute(
        "insert into session values (?, ?, ?, ?, ?, ?, ?)",
        (session_id, title, "/tmp/project", "build", "openai/gpt-5.5", created, updated),
    )
    rows = [
        (
            f"msg-{session_id}-user",
            session_id,
            created + 60_000,
            created + 60_000,
            json.dumps({"role": "user", "time": {"created": created + 60_000}}),
            f"part-{session_id}-user",
            json.dumps({"type": "text", "text": user_text}),
        ),
        (
            f"msg-{session_id}-assistant",
            session_id,
            created + 120_000,
            created + 120_000,
            json.dumps({"role": "assistant", "time": {"created": created + 120_000}}),
            f"part-{session_id}-assistant",
            json.dumps({"type": "text", "text": assistant_text}),
        ),
    ]
    for message_id, sid, time_created, time_updated, message_data, part_id, part_data in rows:
        connection.execute(
            "insert into message values (?, ?, ?, ?, ?)",
            (message_id, sid, time_created, time_updated, message_data),
        )
        connection.execute(
            "insert into part values (?, ?, ?, ?, ?, ?)",
            (part_id, message_id, sid, time_created, time_updated, part_data),
        )
    connection.commit()
    connection.close()


def test_sync_opencode_writes_markdown_archive(tmp_path):
    data_dir = tmp_path / "opencode"
    db_path = data_dir / "opencode.db"
    _create_opencode_db(db_path)
    _insert_session(db_path, "ses_test123456789", "Context Harness", "User prompt")
    connection = sqlite3.connect(db_path)
    connection.execute(
        "insert into part values (?, ?, ?, ?, ?, ?)",
        (
            "part-tool",
            "msg-ses_test123456789-assistant",
            "ses_test123456789",
            1781596921000,
            1781596921000,
            json.dumps({"type": "tool", "tool": "bash"}),
        ),
    )
    connection.execute(
        "insert into part values (?, ?, ?, ?, ?, ?)",
        (
            "part-reasoning",
            "msg-ses_test123456789-assistant",
            "ses_test123456789",
            1781596922000,
            1781596922000,
            json.dumps({"type": "reasoning", "text": "hidden chain"}),
        ),
    )
    connection.commit()
    connection.close()

    output_dir = tmp_path / "out"
    result = sync_opencode(data_dir, output_dir, tmp_path / "state.json", latest=1)

    archives = list(output_dir.glob("*.md"))
    assert result.created == 1
    assert len(archives) == 1
    content = archives[0].read_text(encoding="utf-8")
    assert "- **Source**: opencode" in content
    assert "- **Messages**: 2" in content
    assert "### **User** 08:01" in content
    assert "### **Assistant** 08:02" in content
    assert "User prompt" in content
    assert "Assistant reply" in content
    assert "hidden chain" not in content


def test_sync_opencode_skips_unchanged_archive(tmp_path):
    data_dir = tmp_path / "opencode"
    db_path = data_dir / "opencode.db"
    _create_opencode_db(db_path)
    _insert_session(db_path, "ses_skip", "Skip", "hello")

    sync_opencode(data_dir, tmp_path / "out", tmp_path / "state.json", latest=1)
    second = sync_opencode(data_dir, tmp_path / "out", tmp_path / "state.json", latest=1)

    assert second.created == 0
    assert second.updated == 0
    assert second.skipped == 1


def test_sync_opencode_missing_database_returns_empty_result(tmp_path):
    result = sync_opencode(tmp_path / "missing", tmp_path / "out", tmp_path / "state.json", latest=1)

    assert result.checked == 0
    assert result.created == 0
    assert result.updated == 0
    assert result.skipped == 0


def test_sync_opencode_latest_uses_session_updated_time(tmp_path):
    data_dir = tmp_path / "opencode"
    db_path = data_dir / "opencode.db"
    _create_opencode_db(db_path)
    _insert_session(db_path, "ses_older", "Older", "old", updated=1781596900000)
    _insert_session(db_path, "ses_newer", "Newer", "new", updated=1781597000000)

    result = sync_opencode(data_dir, tmp_path / "out", tmp_path / "state.json", latest=1)

    archives = list((tmp_path / "out").glob("*.md"))
    assert result.checked == 1
    assert result.created == 1
    assert len(archives) == 1
    content = archives[0].read_text(encoding="utf-8")
    assert "new" in content
    assert "old" not in content


def test_sync_opencode_session_path_overrides_configured_database(tmp_path):
    configured_dir = tmp_path / "configured"
    configured_db = configured_dir / "opencode.db"
    target_db = tmp_path / "target" / "opencode.db"
    _create_opencode_db(configured_db)
    _create_opencode_db(target_db)
    _insert_session(configured_db, "ses_configured", "Configured", "configured")
    _insert_session(target_db, "ses_target", "Target", "target")

    result = sync_opencode(
        configured_dir,
        tmp_path / "out",
        tmp_path / "state.json",
        latest=1,
        session_path=target_db,
    )

    archive = next((tmp_path / "out").glob("*.md"))
    content = archive.read_text(encoding="utf-8")
    assert result.checked == 1
    assert "target" in content
    assert "configured" not in content


def test_sync_opencode_skips_bad_json_parts_and_keeps_valid_messages(tmp_path):
    data_dir = tmp_path / "opencode"
    db_path = data_dir / "opencode.db"
    _create_opencode_db(db_path)
    _insert_session(db_path, "ses_bad_json", "Bad JSON", "still works")
    connection = sqlite3.connect(db_path)
    connection.execute(
        "insert into part values (?, ?, ?, ?, ?, ?)",
        ("part-bad", "msg-ses_bad_json-user", "ses_bad_json", 1781596861000, 1781596861000, "{bad json"),
    )
    connection.commit()
    connection.close()

    result = sync_opencode(data_dir, tmp_path / "out", tmp_path / "state.json", latest=1)

    archive = next((tmp_path / "out").glob("*.md"))
    assert result.created == 1
    assert "still works" in archive.read_text(encoding="utf-8")


def test_sync_opencode_bounds_archive_filename_for_long_session_id(tmp_path):
    data_dir = tmp_path / "opencode"
    db_path = data_dir / "opencode.db"
    _create_opencode_db(db_path)
    _insert_session(db_path, "ses_with_a_long_stable_identifier", "Long", "hello")

    result = sync_opencode(data_dir, tmp_path / "out", tmp_path / "state.json", latest=1)

    assert result.created == 1
    assert (tmp_path / "out" / "20260616_ses_with.md").exists()


def test_sync_opencode_removes_stale_archive_when_filename_scheme_changes(tmp_path):
    data_dir = tmp_path / "opencode"
    db_path = data_dir / "opencode.db"
    _create_opencode_db(db_path)
    _insert_session(db_path, "ses_stale", "Stale", "hello")
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    old_archive = output_dir / "old-opencode-name.md"
    old_archive.write_text("old", encoding="utf-8")
    state_path = tmp_path / "state.json"
    state_path.write_text(
        '{"opencode":{"ses_stale":{"archive":"old-opencode-name.md","message_count":0,"source_path":"old"}}}',
        encoding="utf-8",
    )

    result = sync_opencode(data_dir, output_dir, state_path, latest=1)

    assert result.updated == 1
    assert not old_archive.exists()
    assert (output_dir / "20260616_ses_stal.md").exists()
