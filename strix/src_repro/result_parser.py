from __future__ import annotations

import json
import re
from typing import Any

from .contracts import SrcReproAnalysis


_JSON_CODE_BLOCK_PATTERN = re.compile(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", re.IGNORECASE)
_LIST_SPLIT_PATTERN = re.compile(r"[,;|\n\r\t\u3001\uff0c\uff1b]+")

_POSITIVE_HINTS = (
    "can reproduce",
    "reproducible",
    "reproduction is possible",
    "able to reproduce",
    "can be reproduced",
    "possible to reproduce",
    "can reproduce now",
    "is reproducible",
    "can_reproduce true",
    "can_reproduce: true",
    "can_reproduce=true",
    'can_reproduce": true',
    "\u53ef\u590d\u73b0",
    "\u53ef\u4ee5\u590d\u73b0",
    "\u80fd\u591f\u590d\u73b0",
)
_NEGATIVE_HINTS = (
    "cannot reproduce",
    "can not reproduce",
    "unable to reproduce",
    "not reproducible",
    "cannot be reproduced",
    "insufficient information",
    "not enough information",
    "missing information",
    "missing details",
    "can_reproduce false",
    "can_reproduce: false",
    "can_reproduce=false",
    'can_reproduce": false',
    "\u65e0\u6cd5\u590d\u73b0",
    "\u4e0d\u53ef\u590d\u73b0",
    "\u4e0d\u80fd\u590d\u73b0",
    "\u4fe1\u606f\u4e0d\u8db3",
    "\u4fe1\u606f\u7f3a\u5931",
)
_MISSING_HINTS = (
    "missing",
    "need",
    "required",
    "lack",
    "\u7f3a\u5931",
    "\u7f3a\u5c11",
    "\u9700\u8981",
)


def parse_analysis(raw_text: str) -> SrcReproAnalysis:
    normalized_raw_text = _validate_non_empty_text(raw_text, "raw_text")
    payload = _try_parse_json_payload(normalized_raw_text)

    if payload is not None:
        can_reproduce = _extract_can_reproduce(payload, normalized_raw_text)
        return SrcReproAnalysis(
            can_reproduce=can_reproduce,
            reason=_extract_reason(payload, normalized_raw_text),
            missing_info=_extract_missing_info(
                payload,
                raw_text=normalized_raw_text,
                can_reproduce=can_reproduce,
            ),
        )

    can_reproduce = _infer_can_reproduce(normalized_raw_text)
    return SrcReproAnalysis(
        can_reproduce=can_reproduce,
        reason=_infer_reason(normalized_raw_text),
        missing_info=[] if can_reproduce else _infer_missing_info(normalized_raw_text),
    )


def _validate_non_empty_text(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} cannot be empty")
    return value.strip()


def _try_parse_json_payload(raw_text: str) -> dict[str, Any] | None:
    candidates: list[str] = [raw_text]

    code_block_match = _JSON_CODE_BLOCK_PATTERN.search(raw_text)
    if code_block_match:
        candidates.append(code_block_match.group(1))

    first_brace = raw_text.find("{")
    last_brace = raw_text.rfind("}")
    if first_brace >= 0 and last_brace > first_brace:
        candidates.append(raw_text[first_brace : last_brace + 1])

    for candidate in candidates:
        stripped_candidate = candidate.strip()
        if not stripped_candidate:
            continue

        try:
            parsed = json.loads(stripped_candidate)
        except json.JSONDecodeError:
            continue

        if isinstance(parsed, dict):
            return parsed

    return None


def _extract_can_reproduce(payload: dict[str, Any], raw_text: str) -> bool:
    parsed_bool = _parse_bool(payload.get("can_reproduce"))
    if parsed_bool is not None:
        return parsed_bool
    return _infer_can_reproduce(raw_text)


def _extract_reason(payload: dict[str, Any], raw_text: str) -> str:
    reason = payload.get("reason")
    if isinstance(reason, str) and reason.strip():
        return reason.strip()
    if reason is not None:
        normalized = str(reason).strip()
        if normalized:
            return normalized
    return _infer_reason(raw_text)


def _extract_missing_info(
    payload: dict[str, Any],
    *,
    raw_text: str,
    can_reproduce: bool,
) -> list[str]:
    value = payload.get("missing_info")
    missing_info = _normalize_missing_info(value)
    if "missing_info" in payload:
        return missing_info
    if missing_info:
        return missing_info
    if can_reproduce:
        return []
    return _infer_missing_info(raw_text)


def _normalize_missing_info(value: Any) -> list[str]:
    if isinstance(value, list):
        return _unique_non_empty_items(value)
    if isinstance(value, str):
        return _split_text_to_items(value)
    return []


def _parse_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value

    if isinstance(value, int) and not isinstance(value, bool):
        return bool(value)

    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "yes", "y", "1"}:
            return True
        if normalized in {"false", "no", "n", "0"}:
            return False
        if _contains_any(normalized, _NEGATIVE_HINTS):
            return False
        if _contains_any(normalized, _POSITIVE_HINTS):
            return True

    return None


def _infer_can_reproduce(raw_text: str) -> bool:
    lowered = raw_text.lower()
    if _contains_any(lowered, _NEGATIVE_HINTS):
        return False
    if _contains_any(lowered, _POSITIVE_HINTS):
        return True
    return False


def _infer_reason(raw_text: str) -> str:
    lines: list[str] = []

    for raw_line in raw_text.splitlines():
        stripped_line = raw_line.strip()
        if not stripped_line:
            continue

        normalized_line = stripped_line.strip(" -*\t")
        if not normalized_line:
            continue

        if _is_noise_reason_line(normalized_line):
            continue

        lines.append(normalized_line)

    if lines:
        return lines[0]
    return "No reason provided"


def _infer_missing_info(raw_text: str) -> list[str]:
    candidates: list[str] = []

    for raw_line in raw_text.splitlines():
        line = raw_line.strip(" -*\t")
        if not line:
            continue

        lowered = line.lower()
        if not _contains_any(lowered, _MISSING_HINTS):
            continue

        segment = line
        for delimiter in (":", "=>"):
            if delimiter in segment:
                segment = segment.split(delimiter, 1)[1]
                break

        if segment == line and " - " in segment:
            segment = segment.split(" - ", 1)[1]

        parts = _split_text_to_items(segment)
        if parts:
            candidates.extend(parts)
        else:
            candidates.append(line)

    return _unique_non_empty_items(candidates)


def _split_text_to_items(text: str) -> list[str]:
    return _unique_non_empty_items(_LIST_SPLIT_PATTERN.split(text))


def _unique_non_empty_items(items: list[Any]) -> list[str]:
    normalized_items: list[str] = []
    seen: set[str] = set()

    for item in items:
        normalized = str(item).strip().strip(".[]\"'")
        if not normalized:
            continue

        lowered = normalized.lower()
        if lowered in seen:
            continue

        seen.add(lowered)
        normalized_items.append(normalized)

    return normalized_items


def _contains_any(text: str, hints: tuple[str, ...]) -> bool:
    return any(hint in text for hint in hints)


def _is_noise_reason_line(line: str) -> bool:
    if line.startswith("```"):
        return True

    if line in {"{", "}", "[", "]"}:
        return True

    if re.match(r'^"[^"\\]+"\s*:\s*.*[,}]?$', line):
        return True

    if (line.startswith("{") and line.endswith("}")) or (
        line.startswith("[") and line.endswith("]")
    ):
        try:
            json.loads(line)
        except json.JSONDecodeError:
            return False
        return True

    return False


__all__ = [
    "parse_analysis",
    "_infer_can_reproduce",
    "_infer_missing_info",
    "_infer_reason",
]
