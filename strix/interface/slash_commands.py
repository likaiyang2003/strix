from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from xml.sax.saxutils import escape

DEFAULT_SRC_REPORTS_DIR_NAME = "Vul_report"
SRC_TASK_MODE_REPRODUCTION = "src_reproduction"
SRC_TASK_MODE_VERIFY = "src_verification"
SRC_ROOT_SKILL_REPRODUCTION = "src_repro_root"
SRC_ROOT_SKILL_VERIFY = "src_verify_root"
SRC_EXECUTION_STAGE_REPRODUCTION = "reproduction"
SRC_EXECUTION_STAGE_VERIFY = "verify"


class SlashCommandError(ValueError):
    """Raised when a slash command is malformed or cannot be resolved."""


@dataclass(frozen=True)
class SrcCommandRequest:
    report_text: str
    source_label: str
    original_message: str
    skip_analysis: bool = False
    mode: str = SRC_TASK_MODE_REPRODUCTION
    requested_root_skill: str = SRC_ROOT_SKILL_REPRODUCTION
    execution_stage: str = SRC_EXECUTION_STAGE_REPRODUCTION


def is_slash_command(message: str) -> bool:
    if not isinstance(message, str):
        return False
    return message.lstrip().startswith("/")


def parse_src_command(message: str, cwd: Path | None = None) -> SrcCommandRequest:
    if not isinstance(message, str) or not message.strip():
        raise SlashCommandError("`/src` command cannot be empty.")

    stripped = message.strip()
    command, _, remainder = stripped.partition(" ")

    if command != "/src":
        raise SlashCommandError(f"Unsupported slash command: {command}")

    raw_remainder = remainder.strip()
    execution_stage, skip_analysis, normalized_remainder = _parse_src_remainder(raw_remainder)
    if execution_stage == SRC_EXECUTION_STAGE_VERIFY and skip_analysis:
        raise SlashCommandError(_build_src_verify_run_removed_text())
    mode = _get_src_task_mode(execution_stage)
    requested_root_skill = _get_src_root_skill_name(execution_stage)

    if not normalized_remainder:
        raise SlashCommandError(_build_src_usage_text())

    resolved_cwd = cwd or Path.cwd()
    if normalized_remainder.startswith("@"):
        path_str = _strip_wrapping_quotes(normalized_remainder[1:].strip())
        if not path_str:
            command_usage = _build_src_file_usage(execution_stage, skip_analysis)
            raise SlashCommandError(f"{command_usage} requires a non-empty file path.")

        file_path = Path(path_str)
        file_path = _resolve_src_report_path(file_path, resolved_cwd)

        if not file_path.exists():
            raise SlashCommandError(f"SRC report file not found: {file_path}")
        if not file_path.is_file():
            raise SlashCommandError(f"SRC report path is not a file: {file_path}")

        report_text = _read_text_file(file_path)
        if not report_text.strip():
            raise SlashCommandError(f"SRC report file is empty: {file_path}")

        return SrcCommandRequest(
            report_text=report_text.strip(),
            source_label=str(file_path),
            original_message=message,
            skip_analysis=skip_analysis,
            mode=mode,
            requested_root_skill=requested_root_skill,
            execution_stage=execution_stage,
        )

    return SrcCommandRequest(
        report_text=normalized_remainder,
        source_label="inline",
        original_message=message,
        skip_analysis=skip_analysis,
        mode=mode,
        requested_root_skill=requested_root_skill,
        execution_stage=execution_stage,
    )


def build_src_task_message(request: SrcCommandRequest) -> str:
    escaped_source_label = escape(request.source_label)
    escaped_mode = escape(request.mode)
    escaped_root_skill = escape(request.requested_root_skill)
    report_text_cdata = _wrap_cdata(request.report_text)
    analysis_mode = "skip" if request.skip_analysis else "full"
    execution_stage = escape(request.execution_stage)
    root_workflow_name = request.requested_root_skill
    task_kind_text = (
        "verification"
        if request.mode == SRC_TASK_MODE_VERIFY
        else "reproduction"
    )
    stage_text = (
        "    The execution stage is remediation verification after a fix.\n"
        if request.execution_stage == SRC_EXECUTION_STAGE_VERIFY
        else "    The execution stage is initial report-driven reproduction.\n"
    )
    if request.mode == SRC_TASK_MODE_VERIFY:
        workflow_text = "    当前 verify workflow 使用单个 verify executor，不单独运行 analyzer。\n"
        responsibility_text = "    Keep the verification executor responsibilities focused on plan-first verification.\n"
    else:
        workflow_text = (
            "    用户显式要求跳过 analyzer，直接进入 reproducer。\n"
            if request.skip_analysis
            else "    保持严格串行工作流：先 analyzer，再 reproducer。\n"
        )
        responsibility_text = "    Keep analyzer and reproducer responsibilities separated.\n"

    return (
        "<src_repro_task>\n"
        f"  <mode>{escaped_mode}</mode>\n"
        f"  <execution_stage>{execution_stage}</execution_stage>\n"
        f"  <analysis_mode>{analysis_mode}</analysis_mode>\n"
        f"  <requested_root_skill>{escaped_root_skill}</requested_root_skill>\n"
        f"  <source_label>{escaped_source_label}</source_label>\n"
        "  <instructions>\n"
        f"    Treat the following vulnerability report as a dedicated `/src` {task_kind_text} task.\n"
        "    Do not perform broad reconnaissance or generic vulnerability scanning.\n"
        f"{stage_text}"
        f"{workflow_text}"
        f"{responsibility_text}"
        f"    Use the `{root_workflow_name}` orchestration workflow for this task.\n"
        "  </instructions>\n"
        f"  <report_text><![CDATA[{report_text_cdata}]]></report_text>\n"
        "</src_repro_task>"
    )


def build_src_dispatch(
    message: str,
    *,
    root_agent_id: str | None,
    cwd: Path | None = None,
) -> tuple[str, str]:
    request = parse_src_command(message, cwd=cwd)
    if not root_agent_id:
        raise SlashCommandError("Cannot dispatch /src command because no root agent is available.")
    return root_agent_id, build_src_task_message(request)


def list_src_report_suggestions(
    message: str,
    cwd: Path | None = None,
    *,
    max_items: int = 8,
) -> tuple[Path, list[str]] | None:
    if not isinstance(message, str):
        return None

    stripped = message.strip()
    if not stripped.startswith("/src"):
        return None

    _, _, remainder = stripped.partition(" ")
    raw_remainder = remainder.strip()
    execution_stage, skip_analysis, raw_remainder = _parse_src_remainder(raw_remainder)
    if execution_stage == SRC_EXECUTION_STAGE_VERIFY and skip_analysis:
        return None
    if not raw_remainder:
        return None

    if not raw_remainder.startswith("@"):
        return None

    partial = _strip_wrapping_quotes(raw_remainder[1:].strip())
    base_dir = _get_src_reports_dir(cwd or Path.cwd())
    if not base_dir.exists() or not base_dir.is_dir():
        return (base_dir, [])

    entries: list[str] = []
    partial_lower = partial.lower()
    for child in sorted(base_dir.iterdir(), key=lambda item: (item.is_file() is False, item.name.lower())):
        if not child.is_file():
            continue
        if partial and not child.name.lower().startswith(partial_lower):
            continue
        entries.append(child.name)
        if len(entries) >= max_items:
            break

    return (base_dir, entries)


def complete_src_report_reference(
    message: str,
    cwd: Path | None = None,
) -> str | None:
    suggestions = list_src_report_suggestions(message, cwd=cwd, max_items=2)
    if suggestions is None:
        return None

    _, names = suggestions
    if len(names) != 1:
        return None

    stripped = message.rstrip()
    at_index = stripped.rfind("@")
    if at_index == -1:
        return None

    return stripped[: at_index + 1] + names[0]


def _read_text_file(path: Path) -> str:
    read_attempts: tuple[str | None, ...] = ("utf-8", "utf-8-sig", None)
    last_error: UnicodeError | OSError | None = None

    for encoding in read_attempts:
        try:
            if encoding is None:
                return path.read_text()
            return path.read_text(encoding=encoding)
        except (UnicodeError, OSError) as exc:
            last_error = exc

    raise SlashCommandError(f"Failed to read SRC report file: {path} ({last_error})") from last_error


def _parse_src_remainder(raw_remainder: str) -> tuple[str, bool, str]:
    execution_stage = SRC_EXECUTION_STAGE_REPRODUCTION
    skip_analysis = False
    normalized_remainder = raw_remainder

    if raw_remainder == SRC_EXECUTION_STAGE_VERIFY:
        execution_stage = SRC_EXECUTION_STAGE_VERIFY
        normalized_remainder = ""
    elif raw_remainder.startswith(f"{SRC_EXECUTION_STAGE_VERIFY} "):
        execution_stage = SRC_EXECUTION_STAGE_VERIFY
        normalized_remainder = raw_remainder[len(SRC_EXECUTION_STAGE_VERIFY) :].strip()

    if normalized_remainder == "run":
        skip_analysis = True
        normalized_remainder = ""
    elif normalized_remainder.startswith("run "):
        skip_analysis = True
        normalized_remainder = normalized_remainder[4:].strip()

    return execution_stage, skip_analysis, normalized_remainder


def _get_src_task_mode(execution_stage: str) -> str:
    if execution_stage == SRC_EXECUTION_STAGE_VERIFY:
        return SRC_TASK_MODE_VERIFY
    return SRC_TASK_MODE_REPRODUCTION


def _get_src_root_skill_name(execution_stage: str) -> str:
    if execution_stage == SRC_EXECUTION_STAGE_VERIFY:
        return SRC_ROOT_SKILL_VERIFY
    return SRC_ROOT_SKILL_REPRODUCTION


def _build_src_usage_text() -> str:
    return (
        "Usage: `/src <report_text>` or `/src @<file>` or `/src run <report_text>` or "
        "`/src run @<file>` or `/src verify <report_text>` or `/src verify @<file>`"
    )


def _build_src_verify_run_removed_text() -> str:
    return "`/src verify run` 已移除，请直接使用 `/src verify <report_text>` 或 `/src verify @<file>`。"


def _build_src_file_usage(execution_stage: str, skip_analysis: bool) -> str:
    parts = ["/src"]
    if execution_stage == SRC_EXECUTION_STAGE_VERIFY:
        parts.append("verify")
    if skip_analysis:
        parts.append("run")
    return f"`{' '.join(parts)} @file`"


def _resolve_src_report_path(path: Path, cwd: Path) -> Path:
    if path.is_absolute():
        return path.resolve()

    direct_path = (cwd / path).resolve()
    if direct_path.exists():
        return direct_path

    report_dir_path = (_get_src_reports_dir(cwd) / path).resolve()
    return report_dir_path


def _get_src_reports_dir(cwd: Path) -> Path:
    return (cwd / DEFAULT_SRC_REPORTS_DIR_NAME).resolve()


def _strip_wrapping_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1].strip()
    return value


def _wrap_cdata(value: str) -> str:
    return value.replace("]]>", "]]]]><![CDATA[>")


__all__ = [
    "DEFAULT_SRC_REPORTS_DIR_NAME",
    "SRC_ROOT_SKILL_REPRODUCTION",
    "SRC_ROOT_SKILL_VERIFY",
    "SRC_EXECUTION_STAGE_REPRODUCTION",
    "SRC_EXECUTION_STAGE_VERIFY",
    "SRC_TASK_MODE_REPRODUCTION",
    "SRC_TASK_MODE_VERIFY",
    "SlashCommandError",
    "SrcCommandRequest",
    "build_src_dispatch",
    "build_src_task_message",
    "complete_src_report_reference",
    "is_slash_command",
    "list_src_report_suggestions",
    "parse_src_command",
]
