from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from dataclasses import asdict
from typing import Any
from xml.sax.saxutils import escape

from .contracts import SrcReproAnalysis, SrcReproTask
from .prompt_budget import trim_for_analysis, trim_for_plan, trim_for_reproduction, trim_plan_for_reproduction
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
        "    Analyze only whether the report is reproducible.\n"
        "    Return strict JSON only, then call agent_finish and place that JSON in result_summary.\n"
        "    Do not execute, plan, or expand scope.\n"
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
        "    Convert the report into a structured reproduction checklist.\n"
        "    Respect the analyzer conclusion and do not re-judge reproducibility.\n"
        "    Put the full checklist into agent_finish.result_summary.\n"
        "  </instructions>\n"
        f"  <analysis_json><![CDATA[{analysis_json}]]></analysis_json>\n"
        f"  <report_text><![CDATA[{report_text}]]></report_text>\n"
        "</src_repro_planner_task>"
    )


def build_reproducer_task(task: SrcReproTask, analysis: SrcReproAnalysis, plan: str) -> str:
    report_text = _wrap_cdata(trim_for_reproduction(task.report_text))
    analysis_json = _wrap_cdata(json.dumps(asdict(analysis), ensure_ascii=False, indent=2))
    plan_text = _wrap_cdata(trim_plan_for_reproduction(plan))
    source_label = escape(task.source_label)
    return (
        "<src_repro_reproducer_task>\n"
        f"  <source_label>{source_label}</source_label>\n"
        "  <instructions>\n"
        "    Execute the provided reproduction plan exactly as written.\n"
        "    Use available browser, proxy, terminal, and python tools when needed.\n"
        "    Do not redesign the plan.\n"
        "    Put the full execution report into agent_finish.result_summary.\n"
        "  </instructions>\n"
        f"  <analysis_json><![CDATA[{analysis_json}]]></analysis_json>\n"
        f"  <report_text><![CDATA[{report_text}]]></report_text>\n"
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

    emit_message(f"/src task received from `{task.source_label}`. Starting analyzer stage.")
    analyzer_summary = await run_stage(
        "SRC Repro Analyzer",
        "report_repro_analyzer",
        build_analyzer_task(task),
    )
    analysis = parse_analysis(analyzer_summary)
    emit_message(
        "Analyzer completed: "
        f"can_reproduce={str(analysis.can_reproduce).lower()}, reason={analysis.reason}"
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

    emit_message("Analyzer passed. Starting planner stage.")
    reproduction_plan = await run_stage(
        "SRC Repro Planner",
        "report_to_repro_checklist",
        build_planner_task(task, analysis),
    )
    emit_message("Planner completed. Starting reproducer stage.")
    execution_report = await run_stage(
        "SRC Reproducer",
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
    missing_info = ", ".join(analysis.missing_info) if analysis.missing_info else "none"
    return (
        f"/src precheck finished for `{task.source_label}`.\n"
        f"Result: not reproducible.\n"
        f"Reason: {analysis.reason}\n"
        f"Missing info: {missing_info}"
    )


def _build_execution_summary_message(
    task: SrcReproTask,
    analysis: SrcReproAnalysis,
    execution_report: str,
) -> str:
    final_verdict = _infer_final_verdict(execution_report)
    return (
        f"/src execution finished for `{task.source_label}`.\n"
        f"Analyzer reason: {analysis.reason}\n"
        f"Final verdict: {final_verdict}"
    )


def _wrap_cdata(value: str) -> str:
    return value.replace("]]>", "]]]]><![CDATA[>")


__all__ = [
    "build_analyzer_task",
    "build_planner_task",
    "build_reproducer_task",
    "extract_summary_from_completion_report",
    "parse_src_repro_task_message",
    "run_src_repro_flow",
]
