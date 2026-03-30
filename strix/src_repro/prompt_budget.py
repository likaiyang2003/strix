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
DEFAULT_REPRO_PLAN_MAX_CHARS = 2600
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
_SECTION_TITLE_HINTS = {
    "detailed_reproduction_steps": (
        "## detailed reproduction steps",
        "detailed reproduction steps",
    ),
    "success_criteria": (
        "## success criteria",
        "success criteria",
    ),
    "evidence_checklist": (
        "## evidence checklist",
        "evidence checklist",
    ),
    "extracted_facts": (
        "## extracted facts",
        "extracted facts",
    ),
    "preconditions": (
        "## preconditions",
        "preconditions",
    ),
}


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

    preferred_sections = _build_preferred_reproduction_plan(lines, max_chars=max_chars)
    if preferred_sections:
        return preferred_sections

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


def _build_preferred_reproduction_plan(lines: list[str], *, max_chars: int) -> str:
    sections = _extract_plan_sections(lines)
    detailed_section = (sections.get("detailed_reproduction_steps") or "").strip()
    success_section = (sections.get("success_criteria") or "").strip()
    evidence_section = (sections.get("evidence_checklist") or "").strip()

    if not detailed_section and not success_section:
        return ""

    if not success_section:
        return _trim_text(detailed_section, max_chars=max_chars)

    success_len = len(success_section)
    if success_len >= max_chars:
        reserve_for_steps = min(max_chars // 2, 900)
        if reserve_for_steps > 120 and detailed_section:
            trimmed_detailed = _trim_text(detailed_section, max_chars=reserve_for_steps).strip()
            remaining = max(max_chars - len(trimmed_detailed) - 2, 0)
            trimmed_success = success_section[:remaining].rstrip()
            if trimmed_detailed and trimmed_success:
                return f"{trimmed_detailed}\n\n{trimmed_success}".rstrip()
        return success_section[:max_chars].rstrip()

    reserve_for_success = success_len + 2
    detailed_budget = max(max_chars - reserve_for_success, 0)
    trimmed_detailed = _trim_text(detailed_section, max_chars=detailed_budget).strip()

    blocks: list[str] = []
    if trimmed_detailed:
        blocks.append(trimmed_detailed)
    blocks.append(success_section)

    combined = "\n\n".join(blocks).strip()
    remaining_after_core = max(max_chars - len(combined) - (2 if evidence_section else 0), 0)

    if evidence_section and remaining_after_core > 80:
        trimmed_evidence = _trim_text(evidence_section, max_chars=remaining_after_core).strip()
        if trimmed_evidence:
            combined = f"{combined}\n\n{trimmed_evidence}"

    return combined[:max_chars].rstrip()


def _extract_plan_sections(lines: list[str]) -> dict[str, str]:
    section_boundaries: list[tuple[int, str]] = []
    for index, line in enumerate(lines):
        section_name = _match_section_name(line)
        if section_name:
            section_boundaries.append((index, section_name))

    sections: dict[str, str] = {}
    for boundary_index, (start, section_name) in enumerate(section_boundaries):
        end = (
            section_boundaries[boundary_index + 1][0]
            if boundary_index + 1 < len(section_boundaries)
            else len(lines)
        )
        section_text = "\n".join(lines[start:end]).strip()
        if section_text:
            sections[section_name] = section_text
    return sections


def _match_section_name(line: str) -> str | None:
    lowered = line.strip().lower()
    for section_name, hints in _SECTION_TITLE_HINTS.items():
        if any(lowered.startswith(hint) for hint in hints):
            return section_name
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
