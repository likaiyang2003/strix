from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from xml.sax.saxutils import escape


class SlashCommandError(ValueError):
    """Raised when a slash command is malformed or cannot be resolved."""


@dataclass(frozen=True)
class SrcCommandRequest:
    report_text: str
    source_label: str
    original_message: str


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

    normalized_remainder = remainder.strip()
    if not normalized_remainder:
        raise SlashCommandError("Usage: `/src <report_text>` or `/src @<file>`")

    resolved_cwd = cwd or Path.cwd()
    if normalized_remainder.startswith("@"):
        path_str = _strip_wrapping_quotes(normalized_remainder[1:].strip())
        if not path_str:
            raise SlashCommandError("`/src @file` requires a non-empty file path.")

        file_path = Path(path_str)
        if not file_path.is_absolute():
            file_path = resolved_cwd / file_path
        file_path = file_path.resolve()

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
        )

    return SrcCommandRequest(
        report_text=normalized_remainder,
        source_label="inline",
        original_message=message,
    )


def build_src_task_message(request: SrcCommandRequest) -> str:
    escaped_source_label = escape(request.source_label)
    report_text_cdata = _wrap_cdata(request.report_text)

    return (
        "<src_repro_task>\n"
        "  <mode>src_reproduction</mode>\n"
        "  <requested_root_skill>src_repro_root</requested_root_skill>\n"
        f"  <source_label>{escaped_source_label}</source_label>\n"
        "  <instructions>\n"
        "    Treat the following vulnerability report as a dedicated `/src` reproduction task.\n"
        "    Do not perform broad reconnaissance or generic vulnerability scanning.\n"
        "    Keep the workflow strictly serial: analyzer first, planner second, reproducer last.\n"
        "    Keep analyzer, planner, and reproducer responsibilities separated.\n"
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


def _strip_wrapping_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1].strip()
    return value


def _wrap_cdata(value: str) -> str:
    # XML CDATA cannot contain the literal token "]]>".
    return value.replace("]]>", "]]]]><![CDATA[>")


__all__ = [
    "SlashCommandError",
    "SrcCommandRequest",
    "build_src_dispatch",
    "build_src_task_message",
    "is_slash_command",
    "parse_src_command",
]
