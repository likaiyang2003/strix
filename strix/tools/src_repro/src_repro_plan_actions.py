from __future__ import annotations

import json
import uuid
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

from strix.tools.registry import register_tool


VALID_SRC_REPRO_STEP_STATUSES = ["pending", "in_progress", "done", "blocked", "skipped"]

_src_repro_plan_storage: dict[str, dict[str, Any]] = {}


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _get_agent_plan(agent_id: str) -> dict[str, Any] | None:
    return _src_repro_plan_storage.get(agent_id)


def _normalize_status(status: str | None, default: str = "pending") -> str:
    candidate = (status or default or "pending").strip().lower()
    if candidate not in VALID_SRC_REPRO_STEP_STATUSES:
        raise ValueError(
            "Invalid status. Must be one of: "
            + ", ".join(VALID_SRC_REPRO_STEP_STATUSES)
        )
    return candidate


def _normalize_string_list(value: Any) -> list[str]:
    if value is None:
        return []

    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return []
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            return [stripped]
        return _normalize_string_list(parsed)

    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]

    return [str(value).strip()]


def _coerce_steps_payload(raw_steps: Any) -> list[Any]:
    if raw_steps is None:
        return []

    data = raw_steps
    if isinstance(raw_steps, str):
        stripped = raw_steps.strip()
        if not stripped:
            return []
        try:
            data = json.loads(stripped)
        except json.JSONDecodeError:
            return [line.strip(" -*\t") for line in stripped.splitlines() if line.strip(" -*\t")]

    if isinstance(data, dict):
        data = [data]

    if not isinstance(data, list):
        raise TypeError("Steps must be provided as a list, dict, or JSON string")

    return data


def _normalize_step_entry(raw_step: Any, order: int) -> dict[str, Any]:
    if isinstance(raw_step, str):
        title = raw_step.strip()
        if not title:
            raise ValueError("Each step must include a non-empty title")
        timestamp = _utc_now_iso()
        return {
            "step_id": f"S{order}",
            "order": order,
            "title": title,
            "objective": "",
            "suggested_action": "",
            "required_inputs": [],
            "expected_evidence": "",
            "evidence_type": "",
            "success_judgment": "",
            "negative_judgment": "",
            "blocked_judgment": "",
            "failure_judgment": "",
            "stop_rule": "",
            "status": "pending",
            "notes": None,
            "actual_action": None,
            "actual_observation": None,
            "actual_evidence": None,
            "created_at": timestamp,
            "updated_at": timestamp,
            "started_at": None,
            "completed_at": None,
        }

    if not isinstance(raw_step, dict):
        raise TypeError("Each step must be a string or object with a title")

    title = str(raw_step.get("title", "")).strip()
    if not title:
        raise ValueError("Each step must include a non-empty title")

    normalized_status = _normalize_status(str(raw_step.get("status") or "pending"))
    timestamp = _utc_now_iso()
    return {
        "step_id": str(raw_step.get("step_id") or f"S{order}").strip() or f"S{order}",
        "order": order,
        "title": title,
        "objective": str(raw_step.get("objective") or "").strip(),
        "suggested_action": str(raw_step.get("suggested_action") or raw_step.get("action") or "").strip(),
        "required_inputs": _normalize_string_list(
            raw_step.get("required_inputs") or raw_step.get("inputs")
        ),
        "expected_evidence": str(
            raw_step.get("expected_evidence") or raw_step.get("evidence") or ""
        ).strip(),
        "evidence_type": str(raw_step.get("evidence_type") or "").strip(),
        "success_judgment": str(raw_step.get("success_judgment") or "").strip(),
        "negative_judgment": str(
            raw_step.get("negative_judgment") or raw_step.get("failure_judgment") or ""
        ).strip(),
        "blocked_judgment": str(raw_step.get("blocked_judgment") or "").strip(),
        "failure_judgment": str(
            raw_step.get("failure_judgment") or raw_step.get("failure_rule") or ""
        ).strip(),
        "stop_rule": str(raw_step.get("stop_rule") or "").strip(),
        "status": normalized_status,
        "notes": str(raw_step.get("notes") or "").strip() or None,
        "actual_action": str(raw_step.get("actual_action") or "").strip() or None,
        "actual_observation": str(raw_step.get("actual_observation") or "").strip() or None,
        "actual_evidence": str(raw_step.get("actual_evidence") or "").strip() or None,
        "created_at": timestamp,
        "updated_at": timestamp,
        "started_at": timestamp if normalized_status == "in_progress" else None,
        "completed_at": timestamp if normalized_status in {"done", "blocked", "skipped"} else None,
    }


def _normalize_steps(raw_steps: Any) -> list[dict[str, Any]]:
    data = _coerce_steps_payload(raw_steps)
    if not data:
        raise ValueError("Provide at least one step.")
    return [_normalize_step_entry(step, index) for index, step in enumerate(data, start=1)]


def _build_summary(plan: dict[str, Any]) -> dict[str, int]:
    summary = {
        "total": 0,
        "pending": 0,
        "in_progress": 0,
        "done": 0,
        "blocked": 0,
        "skipped": 0,
    }
    steps = plan.get("steps", [])
    if not isinstance(steps, list):
        return summary

    summary["total"] = len(steps)
    for step in steps:
        status = str(step.get("status") or "pending").strip().lower()
        if status not in summary:
            summary[status] = 0
        summary[status] += 1
    return summary


def _sync_plan_context(agent_state: Any, plan: dict[str, Any]) -> None:
    if not hasattr(agent_state, "update_context"):
        return

    agent_state.update_context("src_repro_plan_required", True)
    agent_state.update_context("src_repro_plan_created", True)
    agent_state.update_context("src_repro_plan_id", plan["plan_id"])
    agent_state.update_context("src_repro_plan_step_count", len(plan.get("steps", [])))
    agent_state.update_context("src_repro_plan_title", plan.get("title", ""))
    agent_state.update_context("src_repro_source_label", plan.get("source_label", ""))


def _build_plan_response(plan: dict[str, Any]) -> dict[str, Any]:
    plan_snapshot = deepcopy(plan)
    return {
        "success": True,
        "plan_id": plan_snapshot["plan_id"],
        "title": plan_snapshot.get("title") or "SRC Repro Plan",
        "source_label": plan_snapshot.get("source_label") or "inline",
        "plan": plan_snapshot,
        "summary": _build_summary(plan_snapshot),
        "view": "full",
    }


def _build_step_snapshot(step: dict[str, Any]) -> dict[str, Any]:
    return deepcopy(step)


def _get_current_in_progress_step(plan: dict[str, Any]) -> dict[str, Any] | None:
    steps = plan.get("steps", [])
    if not isinstance(steps, list):
        return None

    for step in steps:
        if str(step.get("status") or "").strip().lower() == "in_progress":
            return step
    return None


def _build_plan_delta_response(
    plan: dict[str, Any],
    *,
    updated: list[str],
    errors: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    updated_steps = [
        _build_step_snapshot(step)
        for step_id in updated
        if (step := _find_step(plan, step_id)) is not None
    ]
    current_in_progress_step = _get_current_in_progress_step(plan)
    latest_step = updated_steps[-1] if updated_steps else None

    response: dict[str, Any] = {
        "success": not bool(errors),
        "plan_id": str(plan.get("plan_id") or ""),
        "title": str(plan.get("title") or "SRC Repro Plan"),
        "source_label": str(plan.get("source_label") or "inline"),
        "summary": _build_summary(plan),
        "updated": list(updated),
        "updated_count": len(updated),
        "updated_steps": updated_steps,
        "latest_step": deepcopy(latest_step) if latest_step is not None else None,
        "current_in_progress_step": (
            _build_step_snapshot(current_in_progress_step)
            if current_in_progress_step is not None
            else None
        ),
        "plan_updated_at": str(plan.get("updated_at") or ""),
        "view": "delta",
    }
    if errors:
        response["errors"] = errors
    return response


def _normalize_bulk_step_updates(raw_updates: Any) -> list[dict[str, Any]]:
    if raw_updates is None:
        return []

    data = raw_updates
    if isinstance(raw_updates, str):
        stripped = raw_updates.strip()
        if not stripped:
            return []
        try:
            data = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise ValueError("Updates must be valid JSON") from exc

    if isinstance(data, dict):
        data = [data]

    if not isinstance(data, list):
        raise TypeError("Updates must be a list of step update objects")

    normalized: list[dict[str, Any]] = []
    for item in data:
        if not isinstance(item, dict):
            raise TypeError("Each update must be an object with step_id")

        step_id = str(item.get("step_id") or "").strip()
        if not step_id:
            raise ValueError("Each update must include a non-empty step_id")

        normalized.append(
            {
                "step_id": step_id,
                "status": item.get("status"),
                "notes": item.get("notes"),
                "actual_action": item.get("actual_action"),
                "actual_observation": item.get("actual_observation"),
                "actual_evidence": item.get("actual_evidence"),
            }
        )
    return normalized


def _find_step(plan: dict[str, Any], step_id: str) -> dict[str, Any] | None:
    steps = plan.get("steps", [])
    if not isinstance(steps, list):
        return None

    for step in steps:
        if str(step.get("step_id") or "").strip() == step_id:
            return step
    return None


def _apply_step_update(
    step: dict[str, Any],
    *,
    status: str | None = None,
    notes: str | None = None,
    actual_action: str | None = None,
    actual_observation: str | None = None,
    actual_evidence: str | None = None,
) -> None:
    timestamp = _utc_now_iso()

    if status is not None:
        previous_status = str(step.get("status") or "pending").strip().lower()
        normalized_status = _normalize_status(status, previous_status)
        step["status"] = normalized_status
        if normalized_status == "in_progress" and not step.get("started_at"):
            step["started_at"] = timestamp
        if normalized_status in {"done", "blocked", "skipped"}:
            step["completed_at"] = timestamp
        elif previous_status in {"done", "blocked", "skipped"} and normalized_status in {
            "pending",
            "in_progress",
        }:
            step["completed_at"] = None

    if notes is not None:
        step["notes"] = str(notes).strip() or None
    if actual_action is not None:
        step["actual_action"] = str(actual_action).strip() or None
    if actual_observation is not None:
        step["actual_observation"] = str(actual_observation).strip() or None
    if actual_evidence is not None:
        step["actual_evidence"] = str(actual_evidence).strip() or None

    step["updated_at"] = timestamp


@register_tool(sandbox_execution=False)
def create_src_repro_plan(
    agent_state: Any,
    steps: Any,
    title: str | None = None,
    source_label: str | None = None,
    replace: bool = False,
) -> dict[str, Any]:
    try:
        agent_id = agent_state.agent_id
        existing = _get_agent_plan(agent_id)
        if existing is not None and not replace:
            return {
                "success": False,
                "error": (
                    "当前 agent 已存在 `/src` 复现步骤合同。"
                    "如需重建，请显式传入 replace=true。"
                ),
            }

        plan_steps = _normalize_steps(steps)
        timestamp = _utc_now_iso()
        plan = {
            "plan_id": str(
                existing.get("plan_id") if existing and replace else f"srcplan_{uuid.uuid4().hex[:8]}"
            ),
            "title": (title or "").strip() or "SRC Repro Plan",
            "source_label": (
                source_label or agent_state.context.get("src_repro_source_label") or "inline"
            ).strip()
            or "inline",
            "created_at": existing.get("created_at", timestamp) if existing and replace else timestamp,
            "updated_at": timestamp,
            "steps": plan_steps,
        }
        _src_repro_plan_storage[agent_id] = plan
        _sync_plan_context(agent_state, plan)
    except (TypeError, ValueError) as exc:
        return {"success": False, "error": f"创建 `/src` 复现步骤合同失败：{exc}"}
    else:
        return _build_plan_response(plan)


@register_tool(sandbox_execution=False)
def get_src_repro_plan(agent_state: Any) -> dict[str, Any]:
    plan = _get_agent_plan(agent_state.agent_id)
    if plan is None:
        return {
            "success": False,
            "error": "当前 agent 还没有 `/src` 复现步骤合同。",
        }
    return _build_plan_response(plan)


@register_tool(sandbox_execution=False)
def update_src_repro_plan_step(
    agent_state: Any,
    step_id: str | None = None,
    status: str | None = None,
    notes: str | None = None,
    actual_action: str | None = None,
    actual_observation: str | None = None,
    actual_evidence: str | None = None,
    updates: Any | None = None,
) -> dict[str, Any]:
    try:
        plan = _get_agent_plan(agent_state.agent_id)
        if plan is None:
            return {
                "success": False,
                "error": "当前 agent 还没有 `/src` 复现步骤合同，无法更新步骤。",
            }

        step_updates = _normalize_bulk_step_updates(updates)
        if step_id is not None:
            normalized_step_id = str(step_id).strip()
            if not normalized_step_id:
                return {"success": False, "error": "step_id 不能为空。"}
            step_updates.append(
                {
                    "step_id": normalized_step_id,
                    "status": status,
                    "notes": notes,
                    "actual_action": actual_action,
                    "actual_observation": actual_observation,
                    "actual_evidence": actual_evidence,
                }
            )

        if not step_updates:
            return {
                "success": False,
                "error": "请提供 step_id 或 updates 来更新 `/src` 步骤。",
            }

        updated: list[str] = []
        errors: list[dict[str, str]] = []
        for item in step_updates:
            target_step = _find_step(plan, item["step_id"])
            if target_step is None:
                errors.append(
                    {
                        "step_id": item["step_id"],
                        "error": f"Step '{item['step_id']}' not found",
                    }
                )
                continue

            _apply_step_update(
                target_step,
                status=item.get("status"),
                notes=item.get("notes"),
                actual_action=item.get("actual_action"),
                actual_observation=item.get("actual_observation"),
                actual_evidence=item.get("actual_evidence"),
            )
            updated.append(item["step_id"])

        plan["updated_at"] = _utc_now_iso()
        _sync_plan_context(agent_state, plan)
        response = _build_plan_delta_response(plan, updated=updated, errors=errors)
    except (TypeError, ValueError) as exc:
        return {"success": False, "error": f"更新 `/src` 复现步骤失败：{exc}"}
    else:
        return response


__all__ = [
    "VALID_SRC_REPRO_STEP_STATUSES",
    "create_src_repro_plan",
    "get_src_repro_plan",
    "update_src_repro_plan_step",
]
