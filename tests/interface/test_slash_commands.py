from pathlib import Path

import pytest

from strix.interface.slash_commands import (
    SlashCommandError,
    build_src_dispatch,
    build_src_task_message,
    parse_src_command,
)


def test_parse_src_command_supports_inline_report_text() -> None:
    request = parse_src_command("/src target=https://app.example.com path=/admin")

    assert request.report_text == "target=https://app.example.com path=/admin"
    assert request.source_label == "inline"
    assert request.original_message == "/src target=https://app.example.com path=/admin"


def test_parse_src_command_supports_file_reference(tmp_path: Path) -> None:
    report_path = tmp_path / "report.txt"
    report_path.write_text("internal src report", encoding="utf-8")

    request = parse_src_command(f"/src @{report_path}", cwd=tmp_path)

    assert request.report_text == "internal src report"
    assert request.source_label == str(report_path.resolve())


def test_parse_src_command_rejects_empty_input() -> None:
    with pytest.raises(SlashCommandError, match="Usage: `/src <report_text>` or `/src @<file>`"):
        parse_src_command("/src")


def test_parse_src_command_rejects_missing_file(tmp_path: Path) -> None:
    missing_path = tmp_path / "missing.txt"

    with pytest.raises(SlashCommandError, match="SRC report file not found"):
        parse_src_command(f"/src @{missing_path}", cwd=tmp_path)


def test_build_src_task_message_wraps_report_text_as_structured_task() -> None:
    request = parse_src_command("/src line1\nline2\n<xml-like>")

    message = build_src_task_message(request)

    assert "<src_repro_task>" in message
    assert "<mode>src_reproduction</mode>" in message
    assert "<requested_root_skill>src_repro_root</requested_root_skill>" in message
    assert "<source_label>inline</source_label>" in message
    assert "<report_text><![CDATA[" in message
    assert "line1\nline2\n<xml-like>" in message


def test_build_src_dispatch_routes_message_to_root_agent() -> None:
    target_agent_id, structured_message = build_src_dispatch(
        "/src report text",
        root_agent_id="root-agent",
    )

    assert target_agent_id == "root-agent"
    assert "<src_repro_task>" in structured_message
    assert "report text" in structured_message


def test_build_src_dispatch_rejects_missing_root_agent() -> None:
    with pytest.raises(SlashCommandError, match="no root agent is available"):
        build_src_dispatch("/src report text", root_agent_id=None)
