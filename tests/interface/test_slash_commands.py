from pathlib import Path

import pytest

from strix.interface.slash_commands import (
    DEFAULT_SRC_REPORTS_DIR_NAME,
    SRC_EXECUTION_STAGE_REPRODUCTION,
    SRC_EXECUTION_STAGE_VERIFY,
    SRC_ROOT_SKILL_REPRODUCTION,
    SRC_ROOT_SKILL_VERIFY,
    SRC_TASK_MODE_REPRODUCTION,
    SRC_TASK_MODE_VERIFY,
    SlashCommandError,
    build_src_dispatch,
    build_src_task_message,
    complete_src_report_reference,
    list_src_report_suggestions,
    parse_src_command,
)


def test_parse_src_command_supports_inline_report_text() -> None:
    request = parse_src_command("/src target=https://app.example.com path=/admin")

    assert request.report_text == "target=https://app.example.com path=/admin"
    assert request.source_label == "inline"
    assert request.original_message == "/src target=https://app.example.com path=/admin"
    assert request.skip_analysis is False
    assert request.mode == SRC_TASK_MODE_REPRODUCTION
    assert request.requested_root_skill == SRC_ROOT_SKILL_REPRODUCTION
    assert request.execution_stage == SRC_EXECUTION_STAGE_REPRODUCTION


def test_parse_src_command_supports_run_inline_report_text() -> None:
    request = parse_src_command("/src run target=https://app.example.com path=/admin")

    assert request.report_text == "target=https://app.example.com path=/admin"
    assert request.source_label == "inline"
    assert request.skip_analysis is True
    assert request.mode == SRC_TASK_MODE_REPRODUCTION
    assert request.requested_root_skill == SRC_ROOT_SKILL_REPRODUCTION
    assert request.execution_stage == SRC_EXECUTION_STAGE_REPRODUCTION


def test_parse_src_command_supports_verify_inline_report_text() -> None:
    request = parse_src_command("/src verify target=https://app.example.com path=/admin")

    assert request.report_text == "target=https://app.example.com path=/admin"
    assert request.source_label == "inline"
    assert request.skip_analysis is False
    assert request.mode == SRC_TASK_MODE_VERIFY
    assert request.requested_root_skill == SRC_ROOT_SKILL_VERIFY
    assert request.execution_stage == SRC_EXECUTION_STAGE_VERIFY


def test_parse_src_command_rejects_verify_run_inline_report_text() -> None:
    with pytest.raises(SlashCommandError, match="`/src verify run` 已移除"):
        parse_src_command("/src verify run target=https://app.example.com path=/admin")


def test_parse_src_command_supports_file_reference(tmp_path: Path) -> None:
    report_path = tmp_path / "report.txt"
    report_path.write_text("internal src report", encoding="utf-8")

    request = parse_src_command(f"/src @{report_path}", cwd=tmp_path)

    assert request.report_text == "internal src report"
    assert request.source_label == str(report_path.resolve())
    assert request.skip_analysis is False
    assert request.mode == SRC_TASK_MODE_REPRODUCTION
    assert request.execution_stage == SRC_EXECUTION_STAGE_REPRODUCTION


def test_parse_src_command_supports_run_file_reference(tmp_path: Path) -> None:
    report_path = tmp_path / "report.txt"
    report_path.write_text("internal src report", encoding="utf-8")

    request = parse_src_command(f"/src run @{report_path}", cwd=tmp_path)

    assert request.report_text == "internal src report"
    assert request.source_label == str(report_path.resolve())
    assert request.skip_analysis is True
    assert request.mode == SRC_TASK_MODE_REPRODUCTION
    assert request.execution_stage == SRC_EXECUTION_STAGE_REPRODUCTION


def test_parse_src_command_supports_verify_file_reference(tmp_path: Path) -> None:
    report_path = tmp_path / "report.txt"
    report_path.write_text("internal src report", encoding="utf-8")

    request = parse_src_command(f"/src verify @{report_path}", cwd=tmp_path)

    assert request.report_text == "internal src report"
    assert request.source_label == str(report_path.resolve())
    assert request.skip_analysis is False
    assert request.mode == SRC_TASK_MODE_VERIFY
    assert request.execution_stage == SRC_EXECUTION_STAGE_VERIFY


def test_parse_src_command_rejects_verify_run_file_reference(tmp_path: Path) -> None:
    report_path = tmp_path / "report.txt"
    report_path.write_text("internal src report", encoding="utf-8")

    with pytest.raises(SlashCommandError, match="`/src verify run` 已移除"):
        parse_src_command(f"/src verify run @{report_path}", cwd=tmp_path)


def test_parse_src_command_resolves_relative_file_from_vul_report_directory(tmp_path: Path) -> None:
    report_dir = tmp_path / DEFAULT_SRC_REPORTS_DIR_NAME
    report_dir.mkdir()
    report_path = report_dir / "demo-report.md"
    report_path.write_text("demo report body", encoding="utf-8")

    request = parse_src_command("/src @demo-report.md", cwd=tmp_path)

    assert request.report_text == "demo report body"
    assert request.source_label == str(report_path.resolve())


def test_parse_src_command_rejects_empty_input() -> None:
    with pytest.raises(SlashCommandError, match="Usage: `/src <report_text>` or `/src @<file>`"):
        parse_src_command("/src")


def test_parse_src_command_rejects_empty_run_input() -> None:
    with pytest.raises(SlashCommandError, match="Usage: `/src <report_text>` or `/src @<file>`"):
        parse_src_command("/src run")


def test_parse_src_command_rejects_missing_file(tmp_path: Path) -> None:
    missing_path = tmp_path / "missing.txt"

    with pytest.raises(SlashCommandError, match="SRC report file not found"):
        parse_src_command(f"/src @{missing_path}", cwd=tmp_path)


def test_build_src_task_message_wraps_report_text_as_structured_task() -> None:
    request = parse_src_command("/src line1\nline2\n<xml-like>")

    message = build_src_task_message(request)

    assert "<src_repro_task>" in message
    assert "<mode>src_reproduction</mode>" in message
    assert "<execution_stage>reproduction</execution_stage>" in message
    assert "<analysis_mode>full</analysis_mode>" in message
    assert "<requested_root_skill>src_repro_root</requested_root_skill>" in message
    assert "<source_label>inline</source_label>" in message
    assert "<report_text><![CDATA[" in message
    assert "line1\nline2\n<xml-like>" in message


def test_build_src_task_message_marks_run_mode_as_skip_analysis() -> None:
    request = parse_src_command("/src run line1\nline2")

    message = build_src_task_message(request)

    assert "<analysis_mode>skip</analysis_mode>" in message
    assert "analyzer" in message
    assert "reproducer" in message


def test_build_src_task_message_marks_verify_stage() -> None:
    request = parse_src_command("/src verify line1\nline2")

    message = build_src_task_message(request)

    assert "<mode>src_verification</mode>" in message
    assert "<execution_stage>verify</execution_stage>" in message
    assert "<requested_root_skill>src_verify_root</requested_root_skill>" in message
    assert "remediation verification" in message
    assert "单个 verify executor" in message
    assert "不单独运行 analyzer" in message


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


def test_list_src_report_suggestions_lists_vul_report_files(tmp_path: Path) -> None:
    report_dir = tmp_path / DEFAULT_SRC_REPORTS_DIR_NAME
    report_dir.mkdir()
    (report_dir / "alpha.md").write_text("a", encoding="utf-8")
    (report_dir / "beta.md").write_text("b", encoding="utf-8")

    result = list_src_report_suggestions("/src @", cwd=tmp_path)

    assert result is not None
    base_dir, suggestions = result
    assert base_dir == report_dir.resolve()
    assert suggestions == ["alpha.md", "beta.md"]


def test_list_src_report_suggestions_filters_run_mode_by_prefix(tmp_path: Path) -> None:
    report_dir = tmp_path / DEFAULT_SRC_REPORTS_DIR_NAME
    report_dir.mkdir()
    (report_dir / "alpha.md").write_text("a", encoding="utf-8")
    (report_dir / "audit.md").write_text("b", encoding="utf-8")
    (report_dir / "beta.md").write_text("c", encoding="utf-8")

    result = list_src_report_suggestions("/src run @au", cwd=tmp_path)

    assert result is not None
    _, suggestions = result
    assert suggestions == ["audit.md"]


def test_list_src_report_suggestions_filters_verify_run_mode_by_prefix(tmp_path: Path) -> None:
    report_dir = tmp_path / DEFAULT_SRC_REPORTS_DIR_NAME
    report_dir.mkdir()
    (report_dir / "audit.md").write_text("a", encoding="utf-8")
    (report_dir / "auth.md").write_text("b", encoding="utf-8")
    (report_dir / "beta.md").write_text("c", encoding="utf-8")

    result = list_src_report_suggestions("/src verify run @au", cwd=tmp_path)

    assert result is None


def test_complete_src_report_reference_completes_unique_match(tmp_path: Path) -> None:
    report_dir = tmp_path / DEFAULT_SRC_REPORTS_DIR_NAME
    report_dir.mkdir()
    (report_dir / "audit.md").write_text("a", encoding="utf-8")
    (report_dir / "beta.md").write_text("b", encoding="utf-8")

    completed = complete_src_report_reference("/src run @au", cwd=tmp_path)

    assert completed == "/src run @audit.md"


def test_complete_src_report_reference_completes_unique_match_for_verify_mode(tmp_path: Path) -> None:
    report_dir = tmp_path / DEFAULT_SRC_REPORTS_DIR_NAME
    report_dir.mkdir()
    (report_dir / "audit.md").write_text("a", encoding="utf-8")
    (report_dir / "beta.md").write_text("b", encoding="utf-8")

    completed = complete_src_report_reference("/src verify run @au", cwd=tmp_path)

    assert completed is None


def test_complete_src_report_reference_returns_none_for_non_unique_match(tmp_path: Path) -> None:
    report_dir = tmp_path / DEFAULT_SRC_REPORTS_DIR_NAME
    report_dir.mkdir()
    (report_dir / "audit.md").write_text("a", encoding="utf-8")
    (report_dir / "audio.md").write_text("b", encoding="utf-8")

    completed = complete_src_report_reference("/src run @au", cwd=tmp_path)

    assert completed is None
