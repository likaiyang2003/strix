from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from dataclasses import asdict
from typing import Any
from xml.sax.saxutils import escape

from .contracts import SrcReproAnalysis, SrcReproTask
from .prompt_budget import trim_for_analysis, trim_for_reproduction
from .result_parser import parse_analysis

_SUMMARY_PATTERN = re.compile(r"<summary>([\s\S]*?)</summary>", re.IGNORECASE)
_EXECUTION_TODO_PATTERN = re.compile(
    r"(##\s*1\)\s*Execution Todo[\s\S]*?)(?=\n##\s*\d+\)|\Z)",
    re.IGNORECASE,
)
_VERDICT_LINE_PATTERN = re.compile(r"^\s*-\s*verdict\s*:\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE)


def parse_src_repro_task_message(message: str) -> SrcReproTask | None:
    if not isinstance(message, str) or "<src_repro_task>" not in message:
        return None

    try:
        root = ET.fromstring(message)
    except ET.ParseError:
        return None

    if root.tag != "src_repro_task":
        return None

    mode = (root.findtext("mode") or "").strip()
    if mode != "src_reproduction":
        return None

    report_text = (root.findtext("report_text") or "").strip()
    source_label = (root.findtext("source_label") or "inline").strip() or "inline"
    analysis_mode = (root.findtext("analysis_mode") or "full").strip().lower() or "full"
    requested_root_skill = (
        (root.findtext("requested_root_skill") or "src_repro_root").strip() or "src_repro_root"
    )

    if not report_text:
        return None

    return SrcReproTask(
        report_text=report_text,
        source_label=source_label,
        requested_root_skill=requested_root_skill,
        original_message=message,
        skip_analysis=analysis_mode == "skip",
    )


def extract_summary_from_completion_report(message: str) -> str | None:
    if not isinstance(message, str) or "<agent_completion_report>" not in message:
        return None

    match = _SUMMARY_PATTERN.search(message)
    if not match:
        return None

    summary = match.group(1).strip()
    return summary or None


def build_analyzer_task(task: SrcReproTask) -> str:
    report_text = _wrap_cdata(trim_for_analysis(task.report_text))
    source_label = escape(task.source_label)
    return (
        "<src_repro_analyzer_task>\n"
        f"  <source_label>{source_label}</source_label>\n"
        "  <instructions>\n"
        "    只分析该报告当前是否具备可复现前提。\n"
        "    所有自然语言输出必须使用中文。\n"
        "    只返回严格 JSON，然后调用 agent_finish，并将该 JSON 放入 result_summary。\n"
        "    不要执行，不要规划，不要扩展范围。\n"
        "  </instructions>\n"
        f"  <report_text><![CDATA[{report_text}]]></report_text>\n"
        "</src_repro_analyzer_task>"
    )


def build_reproducer_task(task: SrcReproTask, analysis: SrcReproAnalysis) -> str:
    analysis_json = _wrap_cdata(json.dumps(asdict(analysis), ensure_ascii=False, indent=2))
    report_text = _wrap_cdata(trim_for_reproduction(task.report_text))
    source_label = escape(task.source_label)
    return (
        "<src_repro_reproducer_task>\n"
        f"  <source_label>{source_label}</source_label>\n"
        "  <instructions>\n"
        "    你是 `/src` 复现执行器。\n"
        "    必须尊重 analyzer 结论，但不要重新判断 can_reproduce。\n"
        "    先阅读 report_text，并且必须先调用 `create_src_repro_plan` 创建一份简短、原子化、可执行的 `/src` 专用步骤合同。\n"
        "    在 `create_src_repro_plan` 完成之前，不得先调用 `send_request`、`repeat_request`、`list_requests`、`view_request`、`browser_action`、`python_action` 或 `terminal_execute`。\n"
        "    如果报告属于 `ui_navigation + packet_replay` 联合场景，不得默认用裸 `send_request` 作为第一条主路线。\n"
        "    当报告同时给出 UI 路径、普通会话上下文、以及页面端成功标志或渲染验证点时，优先规划为“先进入 UI 并生成当前会话中的真实请求，再决定是否查看或重放请求”。\n"
        "    如果历史抓包中的头、cookie、token、nonce、checksum、appsecret 只是证据，而不是当前明确可复用输入，则不要把它们直接当作当前放包模板。\n"
        "    如果一次 `send_request` / `repeat_request` 只得到 Caido 或代理中间层错误，但报告里仍有尚未尝试的 UI 验证分支，不要立刻结束整个任务，应继续走该有界分支。\n"
        "    只有当报告内所有仍然有界且决定性的验证分支都已完成、命中成功标志或被真实阻断后，才输出最终 verdict。\n"
        "    本地信号不等于目标侧成功证据：payload 仅出现在输入框、本地 JS 成功执行、自己注入的控制台日志或 alert 监控钩子命中，这些都不能单独支持 `reproducible`。\n"
        "    对存储型 XSS、消息、客服、评论等场景，只有真实请求/响应证据、目标页面回显/存储证据、或真正出现报告定义的页面端成功标志，才能支持 `reproducible`。\n"
        "    如果最终没有命中成功标志，必须明确区分：是已完成决定性验证但未命中成功标志，从而判 `not reproducible`；还是决定性验证根本未完成，从而判 `blocked`。\n"
        "    然后严格按这份步骤合同执行，并基于真实执行结果给出最终 verdict。\n"
        "    所有自然语言输出必须使用中文。\n"
        "    不得 broad recon，不得扩展攻击面，不得把任务改造成通用扫描。\n"
        "    执行过程中应使用 `get_src_repro_plan` 或 `update_src_repro_plan_step` 维护步骤状态，而不是只在自然语言里口头描述计划。\n"
        "    在 `/src` reproducer 中不得使用通用 `todo` 工具。\n"
        "    必须把完整执行报告写入 agent_finish.result_summary。\n"
        "    输出必须按以下四个部分组织：\n"
        "    1. `## 1) Execution Todo`\n"
        "    2. `## 2) Reproduction Execution Notes`\n"
        "    3. `## 3) Skills/MCP Execution Trace`\n"
        "    4. `## 4) Final Verdict`\n"
        "  </instructions>\n"
        f"  <analysis_json><![CDATA[{analysis_json}]]></analysis_json>\n"
        f"  <report_text><![CDATA[{report_text}]]></report_text>\n"
        "</src_repro_reproducer_task>"
    )


async def run_src_repro_flow(
    raw_task_message: str,
    *,
    run_stage: Any,
    emit_message: Any,
) -> dict[str, Any]:
    task = parse_src_repro_task_message(raw_task_message)
    if task is None:
        raise ValueError("Invalid /src task message")

    if task.skip_analysis:
        emit_message(
            f"已收到 `/src run` 任务，来源：`{task.source_label}`。跳过 analyzer，直接进入 reproducer 阶段。"
        )
        analysis = SrcReproAnalysis(
            can_reproduce=True,
            reason="用户显式要求跳过分析，直接进入复现执行。",
            missing_info=[],
        )
    else:
        emit_message(f"已收到 `/src` 任务，来源：`{task.source_label}`。开始 analyzer 阶段。")
        analyzer_summary = await run_stage(
            "SRC Repro Analyzer",
            "report_repro_analyzer",
            build_analyzer_task(task),
        )
        analysis = parse_analysis(analyzer_summary)
        emit_message(
            "analyzer 已完成："
            f"can_reproduce={str(analysis.can_reproduce).lower()}，reason={analysis.reason}"
        )

        if not analysis.can_reproduce:
            final_message = _build_precheck_stop_message(task, analysis)
            emit_message(final_message)
            return {
                "mode": "src_reproduction",
                "source_label": task.source_label,
                "analysis": asdict(analysis),
                "reproduction_plan": None,
                "execution_report": None,
                "final_verdict": "not reproducible",
                "final_summary": final_message,
            }

    emit_message("开始 reproducer 阶段。")
    execution_report = await run_stage(
        "SRC Reproducer",
        "repro_plan_executor",
        build_reproducer_task(task, analysis),
    )
    reproduction_plan = extract_execution_todo(execution_report)

    final_message = _build_execution_summary_message(task, analysis, execution_report)
    emit_message(final_message)
    return {
        "mode": "src_reproduction",
        "source_label": task.source_label,
        "analysis": asdict(analysis),
        "reproduction_plan": reproduction_plan,
        "execution_report": execution_report,
        "final_verdict": _infer_final_verdict(execution_report),
        "final_summary": final_message,
    }


def extract_execution_todo(execution_report: str) -> str:
    if not isinstance(execution_report, str):
        return ""

    match = _EXECUTION_TODO_PATTERN.search(execution_report.strip())
    if not match:
        return ""

    return match.group(1).strip()


def _infer_final_verdict(execution_report: str) -> str:
    if not isinstance(execution_report, str):
        return "unknown"

    match = _VERDICT_LINE_PATTERN.search(execution_report)
    if match:
        verdict = match.group(1).strip().lower()
        if verdict in {"reproducible", "not reproducible", "blocked"}:
            return verdict

    lowered = execution_report.lower()
    if "not reproducible" in lowered:
        return "not reproducible"
    if "reproducible" in lowered:
        return "reproducible"
    if "blocked" in lowered:
        return "blocked"
    return "unknown"


def _build_precheck_stop_message(task: SrcReproTask, analysis: SrcReproAnalysis) -> str:
    missing_info = "；".join(analysis.missing_info) if analysis.missing_info else "无"
    return (
        f"`/src` 预检查已结束，来源：`{task.source_label}`。\n"
        "结果：不可复现。\n"
        f"原因：{analysis.reason}\n"
        f"缺失信息：{missing_info}"
    )


def _build_execution_summary_message(
    task: SrcReproTask,
    analysis: SrcReproAnalysis,
    execution_report: str,
) -> str:
    final_verdict = _infer_final_verdict(execution_report)
    verdict_label = {
        "reproducible": "可复现",
        "not reproducible": "不可复现",
        "blocked": "阻塞",
        "unknown": "未知",
    }.get(final_verdict, final_verdict)
    return (
        f"`/src` 执行已结束，来源：`{task.source_label}`。\n"
        f"analyzer 结论：{analysis.reason}\n"
        f"最终结论：{verdict_label}"
    )


def _wrap_cdata(value: str) -> str:
    return value.replace("]]>", "]]]]><![CDATA[>")


__all__ = [
    "build_analyzer_task",
    "build_reproducer_task",
    "extract_execution_todo",
    "extract_summary_from_completion_report",
    "parse_src_repro_task_message",
    "run_src_repro_flow",
]
