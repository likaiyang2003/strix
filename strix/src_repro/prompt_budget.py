from __future__ import annotations

_HIGH_PRIORITY_HINTS = (
    "http://",
    "https://",
    "url",
    "domain",
    "ip",
    "\u8d26\u53f7",
    "\u5bc6\u7801",
    "account",
    "password",
    "payload",
    "endpoint",
    "step",
    "\u6b65\u9aa4",
    "\u6f0f\u6d1e",
    "\u590d\u73b0",
    "post ",
    "get ",
    "host:",
)

_SENSITIVE_HINTS = (
    "cookie",
    "jwt",
    "token",
    "authorization",
)

DEFAULT_ANALYSIS_TEXT_MAX_CHARS = 3200
DEFAULT_PLAN_TEXT_MAX_CHARS = 3200
DEFAULT_REPRO_TEXT_MAX_CHARS = 3600
DEFAULT_REPRO_PLAN_MAX_CHARS = 1800
DEFAULT_PROMPT_MAX_CHARS = 5000
MAX_LINE_CHARS = 320
MAX_SENSITIVE_LINE_CHARS = 180
_PLAN_VERDICT_HINTS = (
    "\u6210\u529f\u5224\u5b9a",
    "\u6210\u529f\u6807\u5fd7",
    "\u505c\u6b62\u6761\u4ef6",
    "success criteria",
    "success marker",
    "stop condition",
)


def trim_for_analysis(text: str, *, max_chars: int = DEFAULT_ANALYSIS_TEXT_MAX_CHARS) -> str:
    return _trim_text(text, max_chars=max_chars)


def trim_for_plan(text: str, *, max_chars: int = DEFAULT_PLAN_TEXT_MAX_CHARS) -> str:
    return _trim_text(text, max_chars=max_chars)


def trim_for_reproduction(text: str, *, max_chars: int = DEFAULT_REPRO_TEXT_MAX_CHARS) -> str:
    return _trim_text(text, max_chars=max_chars)


def trim_plan_for_reproduction(
    plan: str,
    *,
    max_chars: int = DEFAULT_REPRO_PLAN_MAX_CHARS,
) -> str:
    normalized = _normalize_text(plan)
    if not normalized or max_chars <= 0:
        return ""

    lines = [_sanitize_line(line) for line in normalized.split("\n")]
    lines = [line for line in lines if line]
    if not lines:
        return ""

    joined = "\n".join(lines)
    if len(joined) <= max_chars:
        return joined

    verdict_start = _find_verdict_section_start(lines)
    if verdict_start is None:
        return _trim_text(normalized, max_chars=max_chars)

    verdict_lines = lines[verdict_start:]
    verdict_text = "\n".join(verdict_lines).strip()
    if not verdict_text:
        return _trim_text(normalized, max_chars=max_chars)

    if len(verdict_text) >= max_chars:
        return verdict_text[:max_chars].rstrip()

    reserved_for_verdict = len(verdict_text) + 2
    head_budget = max(max_chars - reserved_for_verdict, 0)
    if head_budget <= 0:
        return verdict_text[:max_chars].rstrip()

    head_text = _trim_text("\n".join(lines[:verdict_start]), max_chars=head_budget).strip()
    if not head_text:
        return verdict_text[:max_chars].rstrip()
    return f"{head_text}\n\n{verdict_text}".strip()


def build_budgeted_prompt(
    template: str,
    *,
    text: str,
    max_chars: int = DEFAULT_PROMPT_MAX_CHARS,
    plan: str | None = None,
) -> str:
    if not isinstance(template, str) or not template or max_chars <= 0:
        return ""

    has_plan_slot = "{plan}" in template
    if has_plan_slot:
        normalized_plan = plan or ""
        fixed_overhead = len(template.format(text="", plan=""))
        payload_budget = max(max_chars - fixed_overhead, 0)
        text_budget = int(payload_budget * 0.65)
        plan_budget = max(payload_budget - text_budget, 0)

        trimmed_text = _trim_text(text, max_chars=text_budget)
        trimmed_plan = trim_plan_for_reproduction(normalized_plan, max_chars=plan_budget)
        prompt = template.format(text=trimmed_text, plan=trimmed_plan)
    else:
        fixed_overhead = len(template.format(text=""))
        text_budget = max(max_chars - fixed_overhead, 0)
        trimmed_text = _trim_text(text, max_chars=text_budget)
        prompt = template.format(text=trimmed_text)

    if len(prompt) <= max_chars:
        return prompt
    return prompt[:max_chars].rstrip()


def _trim_text(text: str, *, max_chars: int) -> str:
    normalized = _normalize_text(text)
    if not normalized or max_chars <= 0:
        return ""

    lines = [_sanitize_line(line) for line in normalized.split("\n")]
    lines = [line for line in lines if line]
    if not lines:
        return ""

    joined = "\n".join(lines)
    if len(joined) <= max_chars:
        return joined

    selected: list[str] = []
    seen: set[str] = set()
    used = 0

    def add_line(line: str) -> None:
        nonlocal used
        if not line or line in seen:
            return

        next_len = len(line) if not selected else len(line) + 1
        if used + next_len > max_chars:
            return

        selected.append(line)
        seen.add(line)
        used += next_len

    for line in lines[:60]:
        add_line(line)

    for line in lines:
        if _is_high_priority(line):
            add_line(line)

    for line in lines[60:]:
        add_line(line)

    result = "\n".join(selected).strip()
    if result:
        return result
    return joined[:max_chars].rstrip()


def _normalize_text(text: str) -> str:
    if not isinstance(text, str):
        return ""
    return text.replace("\r\n", "\n").replace("\r", "\n").strip()


def _find_verdict_section_start(lines: list[str]) -> int | None:
    for index, line in enumerate(lines):
        lowered = line.lower()
        if any(hint in lowered for hint in _PLAN_VERDICT_HINTS):
            return index
    return None


def _sanitize_line(line: str) -> str:
    stripped = line.strip()
    if not stripped:
        return ""

    lowered = stripped.lower()
    max_line_chars = (
        MAX_SENSITIVE_LINE_CHARS if any(hint in lowered for hint in _SENSITIVE_HINTS) else MAX_LINE_CHARS
    )
    if len(stripped) <= max_line_chars:
        return stripped
    return stripped[:max_line_chars].rstrip() + " ...[TRUNCATED]"


def _is_high_priority(line: str) -> bool:
    lowered = line.lower()
    return any(hint in lowered for hint in _HIGH_PRIORITY_HINTS)


__all__ = [
    "DEFAULT_ANALYSIS_TEXT_MAX_CHARS",
    "DEFAULT_PLAN_TEXT_MAX_CHARS",
    "DEFAULT_PROMPT_MAX_CHARS",
    "DEFAULT_REPRO_PLAN_MAX_CHARS",
    "DEFAULT_REPRO_TEXT_MAX_CHARS",
    "build_budgeted_prompt",
    "trim_for_analysis",
    "trim_for_plan",
    "trim_for_reproduction",
    "trim_plan_for_reproduction",
]
