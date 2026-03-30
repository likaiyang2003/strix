from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from xml.sax.saxutils import escape

DEFAULT_SRC_REPORTS_DIR_NAME = "Vul_report"


class SlashCommandError(ValueError):
    """Raised when a slash command is malformed or cannot be resolved."""


@dataclass(frozen=True)
class SrcCommandRequest:
    report_text: str
    source_label: str
    original_message: str
    skip_analysis: bool = False


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
    skip_analysis = False
    normalized_remainder = raw_remainder
    if raw_remainder == "run":
        skip_analysis = True
        normalized_remainder = ""
    elif raw_remainder.startswith("run "):
        skip_analysis = True
        normalized_remainder = raw_remainder[4:].strip()

    if not normalized_remainder:
        raise SlashCommandError(
            "Usage: `/src <report_text>` or `/src @<file>` or `/src run <report_text>` or `/src run @<file>`"
        )

    resolved_cwd = cwd or Path.cwd()
    if normalized_remainder.startswith("@"):
        path_str = _strip_wrapping_quotes(normalized_remainder[1:].strip())
        if not path_str:
            command_usage = "`/src run @file`" if skip_analysis else "`/src @file`"
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
        )

    return SrcCommandRequest(
        report_text=normalized_remainder,
        source_label="inline",
        original_message=message,
        skip_analysis=skip_analysis,
    )


def build_src_task_message(request: SrcCommandRequest) -> str:
    escaped_source_label = escape(request.source_label)
    report_text_cdata = _wrap_cdata(request.report_text)
    analysis_mode = "skip" if request.skip_analysis else "full"
    workflow_text = (
        "    用户显式要求跳过 analyzer，直接进入 reproducer。\n"
        if request.skip_analysis
        else "    保持严格串行工作流：先 analyzer，再 reproducer。\n"
    )

    return (
        "<src_repro_task>\n"
        "  <mode>src_reproduction</mode>\n"
        f"  <analysis_mode>{analysis_mode}</analysis_mode>\n"
        "  <requested_root_skill>src_repro_root</requested_root_skill>\n"
        f"  <source_label>{escaped_source_label}</source_label>\n"
        "  <instructions>\n"
        "    Treat the following vulnerability report as a dedicated `/src` reproduction task.\n"
        "    Do not perform broad reconnaissance or generic vulnerability scanning.\n"
        f"{workflow_text}"
        "    Keep analyzer and reproducer responsibilities separated.\n"
        "    Use the `src_repro_root` orchestration workflow for this task.\n"
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
    if raw_remainder == "run":
        return None
    if raw_remainder.startswith("run "):
        raw_remainder = raw_remainder[4:].strip()

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
    "SlashCommandError",
    "SrcCommandRequest",
    "build_src_dispatch",
    "build_src_task_message",
    "complete_src_report_reference",
    "is_slash_command",
    "list_src_report_suggestions",
    "parse_src_command",
]
