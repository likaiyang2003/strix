from __future__ import annotations

import json
import re
from dataclasses import asdict
from typing import Any
from xml.sax.saxutils import escape

from strix.src_repro.contracts import SrcReproAnalysis, SrcReproTask
from strix.src_repro.orchestration import extract_execution_todo, parse_src_repro_task_message
from strix.src_repro.prompt_budget import trim_for_reproduction

_VERDICT_LINE_PATTERN = re.compile(r"^\s*(?:-\s*)?verdict\s*:\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE)


async def run_src_verify_flow(
    raw_task_message: str,
    *,
    run_stage: Any,
    emit_message: Any,
) -> dict[str, Any]:
    task = parse_src_repro_task_message(raw_task_message)
    if task is None:
        raise ValueError("Invalid /src task message")
    if task.mode != "src_verification":
        raise ValueError(f"Expected src_verification task, got {task.mode}")

    command_label = _build_verify_command_label()
    analysis = SrcReproAnalysis(
        can_reproduce=True,
        reason="`/src verify` 当前使用单子 agent 直接执行修复后验证，不单独运行 verify analyzer。",
        missing_info=[],
    )

    emit_message(
        f"已收到 `{command_label}` 任务，来源：`{task.source_label}`。\n"
        "当前 `/src verify` 使用单子 agent 验证流，直接进入 verify executor 阶段。"
    )

    execution_report = await run_stage(
        "SRC Verify Executor",
        "verify_plan_executor",
        _build_verify_executor_task(task, analysis),
    )
    reproduction_plan = extract_execution_todo(execution_report)
    final_verdict = _infer_final_verdict(execution_report)
    final_message = _build_verify_execution_summary_message(task, analysis, final_verdict)
    emit_message(final_message)

    return {
        "mode": task.mode,
        "source_label": task.source_label,
        "execution_stage": task.execution_stage,
        "analysis": asdict(analysis),
        "reproduction_plan": reproduction_plan,
        "execution_report": execution_report,
        "final_verdict": final_verdict,
        "final_summary": final_message,
    }


def _build_verify_command_label() -> str:
    return "/src verify"


def _build_verify_executor_task(task: SrcReproTask, analysis: SrcReproAnalysis) -> str:
    analysis_json = _wrap_cdata(json.dumps(asdict(analysis), ensure_ascii=False, indent=2))
    report_text = _wrap_cdata(trim_for_reproduction(task.report_text))
    source_label = escape(task.source_label)
    execution_stage = escape(task.execution_stage)
    return (
        "<src_verify_executor_task>\n"
        f"  <execution_stage>{execution_stage}</execution_stage>\n"
        f"  <source_label>{source_label}</source_label>\n"
        "  <instructions>\n"
        "    你是 `/src verify` 的 verify executor。\n"
        "    你的目标不是再次证明漏洞能否复现，而是验证修复后原漏洞链是否仍然成立。\n"
        "    在开始任何执行型工具之前，必须先调用 `create_src_plan` 创建详细 verification plan。\n"
        "    verification plan 必须明确旧成功标志、comparability 条件，以及修复后应观察到的安全行为。\n"
        "    最终 verdict 只能是 `still reproducible`、`fixed`、`blocked` 三种之一。\n"
        "    只有在 comparability 成立、旧成功标志未命中、且修复后安全行为成立时，才能判 `fixed`。\n"
        "    如果旧成功标志再次命中，必须判 `still reproducible`。\n"
        "    如果决定性验证链未完成、comparability 不成立，或缺少支持 fixed 的必要证据，必须判 `blocked`。\n"
        "    执行中应使用 `get_src_plan` / `update_src_plan_step` 维护步骤状态。\n"
        "    在 `/src verify` executor 中不得使用通用 `todo` 工具。\n"
        "    所有自然语言输出必须使用中文。\n"
        "    输出必须按以下四个部分组织：\n"
        "    1. `## 1) Execution Todo`\n"
        "    2. `## 2) Verification Execution Notes`\n"
        "    3. `## 3) Skills/MCP Execution Trace`\n"
        "    4. `## 4) Final Verdict`\n"
        "    在 `## 4) Final Verdict` 中至少输出：\n"
        "    - `verdict: still reproducible|fixed|blocked`\n"
        "    - `reason: ...`\n"
        "    - `comparability: established|partial|missing`\n"
        "    - `old_success_marker: hit|not_hit|unknown`\n"
        "    - `secure_behavior: observed|not_observed|unknown`\n"
        "  </instructions>\n"
        f"  <analysis_json><![CDATA[{analysis_json}]]></analysis_json>\n"
        f"  <report_text><![CDATA[{report_text}]]></report_text>\n"
        "</src_verify_executor_task>"
    )


def _infer_final_verdict(execution_report: str) -> str:
    if not isinstance(execution_report, str):
        return "unknown"

    match = _VERDICT_LINE_PATTERN.search(execution_report)
    if match:
        verdict = _normalize_verify_verdict(match.group(1))
        if verdict is not None:
            return verdict

    lowered = execution_report.lower()
    for candidate in ("still reproducible", "fixed", "blocked"):
        verdict = _normalize_verify_verdict(candidate if candidate in lowered else "")
        if verdict is not None:
            return verdict

    return "unknown"


def _normalize_verify_verdict(value: str) -> str | None:
    normalized = value.strip().lower()
    if normalized in {"still reproducible", "fixed", "blocked"}:
        return normalized
    return None


def _build_verify_execution_summary_message(
    task: SrcReproTask,
    analysis: SrcReproAnalysis,
    final_verdict: str,
) -> str:
    verdict_label = {
        "still reproducible": "仍可复现",
        "fixed": "修复已验证",
        "blocked": "验证受阻",
        "unknown": "未知",
    }.get(final_verdict, final_verdict)
    return (
        f"`{_build_verify_command_label()}` 执行已结束，来源：`{task.source_label}`。\n"
        f"verify workflow 说明：{analysis.reason}\n"
        f"最终结论：{verdict_label}"
    )


def _wrap_cdata(value: str) -> str:
    return value.replace("]]>", "]]]]><![CDATA[>")


__all__ = ["run_src_verify_flow", "_build_verify_executor_task"]
