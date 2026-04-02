from __future__ import annotations

from typing import Any, ClassVar

from rich.text import Text
from textual.widgets import Static

from .base_renderer import BaseToolRenderer
from .registry import register_tool_renderer


STATUS_MARKERS: dict[str, str] = {
    "pending": "[ ]",
    "in_progress": "[~]",
    "done": "[✓]",
    "blocked": "[!]",
    "skipped": "[-]",
}


def _extract_plan(result: Any) -> dict[str, Any] | None:
    if not isinstance(result, dict):
        return None
    plan = result.get("plan")
    return plan if isinstance(plan, dict) else None


def _extract_summary(result: Any) -> dict[str, Any]:
    if not isinstance(result, dict):
        return {}
    summary = result.get("summary")
    return summary if isinstance(summary, dict) else {}


def _status_marker(status: str | None) -> str:
    normalized = str(status or "pending").strip().lower()
    return STATUS_MARKERS.get(normalized, STATUS_MARKERS["pending"])


def _status_style(status: str | None) -> str | None:
    normalized = str(status or "pending").strip().lower()
    if normalized == "done":
        return "dim strike"
    if normalized == "in_progress":
        return "bold"
    if normalized == "blocked":
        return "#f59e0b"
    return None


def _truncate(value: str, limit: int = 88) -> str:
    if len(value) <= limit:
        return value
    return value[: limit - 3].rstrip() + "..."


def _append_summary(text: Text, summary: dict[str, Any]) -> None:
    if not summary:
        return

    text.append("\n  ")
    text.append(
        (
            f"共 {summary.get('total', 0)} 步 | "
            f"pending {summary.get('pending', 0)} | "
            f"in_progress {summary.get('in_progress', 0)} | "
            f"done {summary.get('done', 0)} | "
            f"blocked {summary.get('blocked', 0)} | "
            f"skipped {summary.get('skipped', 0)}"
        ),
        style="dim",
    )


def _append_full_step_details(text: Text, step: dict[str, Any]) -> None:
    status = str(step.get("status") or "pending").strip().lower()
    step_id = str(step.get("step_id") or "?").strip() or "?"
    title = str(step.get("title") or "(untitled)").strip() or "(untitled)"

    text.append("\n  ")
    text.append(_status_marker(status))
    text.append(" ")
    text.append(f"{step_id} ", style="bold")
    text.append(title, style=_status_style(status))

    detail_fields = [
        ("目标", "objective"),
        ("动作", "suggested_action"),
        ("预期证据", "expected_evidence"),
        ("成功判断", "success_judgment"),
        ("负向判断", "negative_judgment"),
        ("阻塞判断", "blocked_judgment"),
        ("停止规则", "stop_rule"),
        ("实际动作", "actual_action"),
        ("实际观察", "actual_observation"),
        ("实际证据", "actual_evidence"),
        ("备注", "notes"),
    ]
    if not str(step.get("negative_judgment") or "").strip():
        detail_fields.insert(6, ("失败判断", "failure_judgment"))

    for label, key in detail_fields:
        value = str(step.get(key) or "").strip()
        if value:
            text.append("\n    ")
            text.append(label, style="dim")
            text.append(": ")
            text.append(value)

    required_inputs = step.get("required_inputs")
    if isinstance(required_inputs, list) and required_inputs:
        text.append("\n    ")
        text.append("输入", style="dim")
        text.append(": ")
        text.append(", ".join(str(item).strip() for item in required_inputs if str(item).strip()))


def _append_compact_step_line(text: Text, step: dict[str, Any]) -> None:
    status = str(step.get("status") or "pending").strip().lower()
    step_id = str(step.get("step_id") or "?").strip() or "?"
    title = str(step.get("title") or "(untitled)").strip() or "(untitled)"

    text.append("\n  ")
    text.append(_status_marker(status))
    text.append(" ")
    text.append(f"{step_id} ", style="bold")
    text.append(title, style=_status_style(status))

    detail_value = ""
    detail_label = ""
    for label, key in [
        ("观察", "actual_observation"),
        ("备注", "notes"),
        ("动作", "actual_action"),
        ("证据", "actual_evidence"),
    ]:
        candidate = str(step.get(key) or "").strip()
        if candidate:
            detail_label = label
            detail_value = _truncate(candidate, limit=68)
            break

    if detail_value:
        text.append("\n    ")
        text.append(detail_label, style="dim")
        text.append(": ")
        text.append(detail_value, style="dim")


def _render_error_widget(title_label: str, status: str, message: str) -> Static:
    text = Text()
    text.append(title_label, style="bold #22c55e")
    text.append("\n  ")
    text.append(message, style="#ef4444")
    return Static(text, classes=BaseToolRenderer.get_css_classes(status))


def _render_pending_widget(title_label: str, status: str, message: str = "处理中...") -> Static:
    text = Text()
    text.append(title_label, style="bold #22c55e")
    text.append("\n  ")
    text.append(message, style="dim")
    return Static(text, classes=BaseToolRenderer.get_css_classes(status))


def _render_full_plan_widget(title_label: str, tool_data: dict[str, Any]) -> Static:
    result = tool_data.get("result")
    status = tool_data.get("status", "completed")

    if isinstance(result, str) and result.strip():
        return _render_pending_widget(title_label, status, result.strip())
    if not isinstance(result, dict):
        return _render_pending_widget(title_label, status)
    if not result.get("success") and not _extract_plan(result):
        return _render_error_widget(title_label, status, str(result.get("error") or "操作失败"))

    plan = _extract_plan(result)
    if not plan:
        return _render_pending_widget(title_label, status, "当前没有可展示的 `/src` 步骤合同。")

    text = Text()
    text.append(title_label, style="bold #22c55e")

    plan_title = str(plan.get("title") or "SRC Plan").strip() or "SRC Plan"
    source_label = str(plan.get("source_label") or "").strip()

    text.append("\n  ")
    text.append(plan_title, style="bold")
    if source_label:
        text.append("\n  ")
        text.append(source_label, style="dim")

    _append_summary(text, _extract_summary(result))

    steps = plan.get("steps")
    if not isinstance(steps, list) or not steps:
        text.append("\n  ")
        text.append("没有步骤", style="dim")
    else:
        for step in steps:
            if isinstance(step, dict):
                _append_full_step_details(text, step)

    return Static(text, classes=BaseToolRenderer.get_css_classes(status))


def _render_plan_snapshot_widget(title_label: str, tool_data: dict[str, Any]) -> Static:
    result = tool_data.get("result")
    status = tool_data.get("status", "completed")

    if isinstance(result, str) and result.strip():
        return _render_pending_widget(title_label, status, result.strip())
    if not isinstance(result, dict):
        return _render_pending_widget(title_label, status)
    if not result.get("success") and not _extract_plan(result):
        return _render_error_widget(title_label, status, str(result.get("error") or "操作失败"))

    plan = _extract_plan(result)
    if not plan:
        return _render_pending_widget(title_label, status, "当前没有可展示的 `/src` 步骤合同。")

    text = Text()
    text.append(title_label, style="bold #22c55e")

    plan_title = str(plan.get("title") or "SRC Plan").strip() or "SRC Plan"
    source_label = str(plan.get("source_label") or "").strip()

    text.append("\n  ")
    text.append(plan_title, style="bold")
    if source_label:
        text.append("\n  ")
        text.append(source_label, style="dim")

    _append_summary(text, _extract_summary(result))

    steps = plan.get("steps")
    if isinstance(steps, list):
        for step in steps:
            if isinstance(step, dict):
                _append_compact_step_line(text, step)

    return Static(text, classes=BaseToolRenderer.get_css_classes(status))


def _render_plan_delta_widget(title_label: str, tool_data: dict[str, Any]) -> Static:
    result = tool_data.get("result")
    status = tool_data.get("status", "completed")

    if isinstance(result, str) and result.strip():
        return _render_pending_widget(title_label, status, result.strip())
    if not isinstance(result, dict):
        return _render_pending_widget(title_label, status)
    if not result.get("success") and not result.get("updated_steps"):
        return _render_error_widget(title_label, status, str(result.get("error") or "操作失败"))

    text = Text()
    text.append(title_label, style="bold #22c55e")

    updated_count = int(result.get("updated_count") or 0)
    if updated_count > 0:
        text.append("\n  ")
        text.append(f"已更新 {updated_count} 步", style="dim")

    updated_steps = result.get("updated_steps")
    if isinstance(updated_steps, list) and updated_steps:
        for step in updated_steps:
            if isinstance(step, dict):
                _append_compact_step_line(text, step)
    else:
        latest_step = result.get("latest_step")
        if isinstance(latest_step, dict):
            _append_compact_step_line(text, latest_step)
        else:
            text.append("\n  ")
            text.append("没有新的步骤变更", style="dim")

    _append_summary(text, _extract_summary(result))

    errors = result.get("errors")
    if isinstance(errors, list) and errors:
        for error in errors[:2]:
            if isinstance(error, dict):
                text.append("\n  ")
                text.append("错误", style="#ef4444")
                text.append(": ")
                text.append(str(error.get("error") or "未知错误"), style="#ef4444")

    return Static(text, classes=BaseToolRenderer.get_css_classes(status))


@register_tool_renderer
class CreateSrcReproPlanRenderer(BaseToolRenderer):
    tool_name: ClassVar[str] = "create_src_plan"
    css_classes: ClassVar[list[str]] = ["tool-call", "src-repro-plan-tool"]

    @classmethod
    def render(cls, tool_data: dict[str, Any]) -> Static:
        return _render_full_plan_widget(cls.tool_name, tool_data)


@register_tool_renderer
class GetSrcReproPlanRenderer(BaseToolRenderer):
    tool_name: ClassVar[str] = "get_src_plan"
    css_classes: ClassVar[list[str]] = ["tool-call", "src-repro-plan-tool"]

    @classmethod
    def render(cls, tool_data: dict[str, Any]) -> Static:
        return _render_plan_snapshot_widget(cls.tool_name, tool_data)


@register_tool_renderer
class UpdateSrcReproPlanStepRenderer(BaseToolRenderer):
    tool_name: ClassVar[str] = "update_src_plan_step"
    css_classes: ClassVar[list[str]] = ["tool-call", "src-repro-plan-tool"]

    @classmethod
    def render(cls, tool_data: dict[str, Any]) -> Static:
        return _render_plan_delta_widget(cls.tool_name, tool_data)
