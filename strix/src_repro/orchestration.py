from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from dataclasses import asdict
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from .contracts import SrcReproAnalysis, SrcReproTask
from .prompt_budget import trim_for_analysis, trim_for_plan, trim_plan_for_reproduction
from .result_parser import parse_analysis


_SUMMARY_PATTERN = re.compile(r"<summary>([\s\S]*?)</summary>", re.IGNORECASE)


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
        "    只分析该报告当前是否具备可复现条件。\n"
        "    所有自然语言输出必须使用中文。\n"
        "    只返回严格 JSON，然后调用 agent_finish，并将该 JSON 放入 result_summary。\n"
        "    不要执行、不要规划、不要扩大范围。\n"
        "  </instructions>\n"
        f"  <report_text><![CDATA[{report_text}]]></report_text>\n"
        "</src_repro_analyzer_task>"
    )


def build_planner_task(task: SrcReproTask, analysis: SrcReproAnalysis) -> str:
    report_text = _wrap_cdata(trim_for_plan(task.report_text))
    analysis_json = _wrap_cdata(json.dumps(asdict(analysis), ensure_ascii=False, indent=2))
    source_label = escape(task.source_label)
    return (
        "<src_repro_planner_task>\n"
        f"  <source_label>{source_label}</source_label>\n"
        "  <instructions>\n"
        "    将报告转换为结构化复现清单。\n"
        "    所有自然语言输出必须使用中文。\n"
        "    必须遵守 analyzer 结论，不要重新判断可复现性。\n"
        "    将完整清单放入 agent_finish.result_summary。\n"
        "  </instructions>\n"
        f"  <analysis_json><![CDATA[{analysis_json}]]></analysis_json>\n"
        f"  <report_text><![CDATA[{report_text}]]></report_text>\n"
        "</src_repro_planner_task>"
    )


def build_reproducer_task(task: SrcReproTask, analysis: SrcReproAnalysis, plan: str) -> str:
    analysis_json = _wrap_cdata(json.dumps(asdict(analysis), ensure_ascii=False, indent=2))
    plan_text = _wrap_cdata(trim_plan_for_reproduction(plan))
    source_label = escape(task.source_label)
    source_meta = _describe_report_source(task.source_label)
    source_type = escape(source_meta["source_type"])
    source_path = escape(source_meta["source_path"])
    source_dir = escape(source_meta["source_dir"])
    source_name = escape(source_meta["source_name"])
    source_available = str(source_meta["source_available"]).lower()
    return (
        "<src_repro_reproducer_task>\n"
        f"  <source_label>{source_label}</source_label>\n"
        "  <original_report_source>\n"
        f"    <source_type>{source_type}</source_type>\n"
        f"    <source_available>{source_available}</source_available>\n"
        f"    <source_path>{source_path}</source_path>\n"
        f"    <source_dir>{source_dir}</source_dir>\n"
        f"    <source_name>{source_name}</source_name>\n"
        "  </original_report_source>\n"
        "  <instructions>\n"
        "    严格按提供的复现计划执行。\n"
        "    所有自然语言输出必须使用中文。\n"
        "    需要时使用现有 browser、proxy、terminal、python 工具。\n"
        "    默认只依赖 reproduction_plan 执行，不要把自己重新退回到原始漏洞报告驱动模式。\n"
        "    不要重写或重设计计划。\n"
        "    如果当前来源是文件，并且你在执行中遇到计划缺口、字段歧义、请求细节不完整、证据口径不清等问题，"
        "先查看 original_report_source 中给出的源报告目录和文件名，再调用 load_src_report_source 按 source_label 读取原始报告补充信息。\n"
        "    只有在执行确实遇到问题时，才允许按需查看原始报告；不要在一开始就重复通读原始报告。\n"
        "    如果来源是 inline，则说明没有可回看的文件版原始报告。\n"
        "    将完整执行报告放入 agent_finish.result_summary。\n"
        "  </instructions>\n"
        f"  <analysis_json><![CDATA[{analysis_json}]]></analysis_json>\n"
        f"  <reproduction_plan><![CDATA[{plan_text}]]></reproduction_plan>\n"
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
        emit_message(f"已收到 `/src run` 任务，来源：`{task.source_label}`。跳过 analyzer，直接进入 planner 阶段。")
        analysis = SrcReproAnalysis(
            can_reproduce=True,
            reason="用户显式要求跳过分析，直接生成复现步骤并执行。",
            missing_info=[],
        )
    else:
        emit_message(f"已收到 `/src` 任务，来源：`{task.source_label}`。开始 analyzer 阶段。")
        analyzer_summary = await run_stage(
            "SRC 复现分析器",
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

    emit_message("analyzer 通过，开始 planner 阶段。")
    reproduction_plan = await run_stage(
        "SRC 复现规划器",
        "report_to_repro_checklist",
        build_planner_task(task, analysis),
    )
    emit_message("planner 已完成，开始 reproducer 阶段。")
    execution_report = await run_stage(
        "SRC 复现执行器",
        "repro_plan_executor",
        build_reproducer_task(task, analysis, reproduction_plan),
    )

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


def _infer_final_verdict(execution_report: str) -> str:
    lowered = execution_report.lower()
    if "verdict" in lowered and "reproducible" in lowered and "not reproducible" not in lowered:
        return "reproducible"
    if "verdict" in lowered and "blocked" in lowered:
        return "blocked"
    if "not reproducible" in lowered:
        return "not reproducible"
    return "unknown"


def _build_precheck_stop_message(task: SrcReproTask, analysis: SrcReproAnalysis) -> str:
    missing_info = "，".join(analysis.missing_info) if analysis.missing_info else "无"
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
        f"analyzer 原因：{analysis.reason}\n"
        f"最终结论：{verdict_label}"
    )


def _wrap_cdata(value: str) -> str:
    return value.replace("]]>", "]]]]><![CDATA[>")


def _describe_report_source(source_label: str) -> dict[str, str | bool]:
    normalized = (source_label or "").strip()
    if not normalized or normalized == "inline":
        return {
            "source_type": "inline",
            "source_available": False,
            "source_path": "inline",
            "source_dir": "",
            "source_name": "",
        }

    source_path = Path(normalized)
    return {
        "source_type": "file",
        "source_available": True,
        "source_path": str(source_path),
        "source_dir": str(source_path.parent),
        "source_name": source_path.name,
    }


__all__ = [
    "build_analyzer_task",
    "build_planner_task",
    "build_reproducer_task",
    "extract_summary_from_completion_report",
    "parse_src_repro_task_message",
    "run_src_repro_flow",
]
