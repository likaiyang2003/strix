import asyncio

from strix.src_repro import (
    build_reproducer_task,
    extract_summary_from_completion_report,
    parse_src_repro_task_message,
    run_src_repro_flow,
)
from strix.src_repro.contracts import SrcReproAnalysis, SrcReproTask


def test_parse_src_repro_task_message_reads_structured_payload() -> None:
    message = """<src_repro_task>
  <mode>src_reproduction</mode>
  <analysis_mode>full</analysis_mode>
  <requested_root_skill>src_repro_root</requested_root_skill>
  <source_label>inline</source_label>
  <report_text><![CDATA[target=https://demo.local path=/admin]]></report_text>
</src_repro_task>"""

    task = parse_src_repro_task_message(message)

    assert task is not None
    assert task.report_text == "target=https://demo.local path=/admin"
    assert task.source_label == "inline"
    assert task.requested_root_skill == "src_repro_root"
    assert task.skip_analysis is False


def test_parse_src_repro_task_message_reads_skip_analysis_mode() -> None:
    message = """<src_repro_task>
  <mode>src_reproduction</mode>
  <analysis_mode>skip</analysis_mode>
  <requested_root_skill>src_repro_root</requested_root_skill>
  <source_label>inline</source_label>
  <report_text><![CDATA[target=https://demo.local path=/admin]]></report_text>
</src_repro_task>"""

    task = parse_src_repro_task_message(message)

    assert task is not None
    assert task.skip_analysis is True


def test_extract_summary_from_completion_report_returns_summary_block() -> None:
    message = """<agent_completion_report>
    <results>
        <summary>{"can_reproduce": true, "reason": "信息充分", "missing_info": []}</summary>
    </results>
</agent_completion_report>"""

    summary = extract_summary_from_completion_report(message)

    assert summary == '{"can_reproduce": true, "reason": "信息充分", "missing_info": []}'


def test_build_reproducer_task_embeds_plan_and_report() -> None:
    task = SrcReproTask(
        report_text="report body",
        source_label=r"F:\Study\strix\Vul_report\demo-report.md",
    )
    analysis = SrcReproAnalysis(can_reproduce=True, reason="ok", missing_info=[])

    rendered = build_reproducer_task(task, analysis, "Success Criteria\n- Success Marker: visible")

    assert "<src_repro_reproducer_task>" in rendered
    assert "<reproduction_plan><![CDATA[" in rendered
    assert "Success Criteria" in rendered
    assert "report body" not in rendered
    assert "<source_type>file</source_type>" in rendered
    assert "<source_dir>F:\\Study\\strix\\Vul_report</source_dir>" in rendered
    assert "<source_name>demo-report.md</source_name>" in rendered
    assert "load_src_report_source" in rendered


def test_run_src_repro_flow_stops_after_analyzer_when_not_reproducible() -> None:
    stage_calls: list[tuple[str, str, str]] = []
    emitted_messages: list[str] = []
    raw_message = """<src_repro_task>
  <mode>src_reproduction</mode>
  <analysis_mode>full</analysis_mode>
  <requested_root_skill>src_repro_root</requested_root_skill>
  <source_label>inline</source_label>
  <report_text><![CDATA[target=https://demo.local path=/admin]]></report_text>
</src_repro_task>"""

    async def fake_stage_runner(stage_name: str, skill_name: str, task_text: str) -> str:
        stage_calls.append((stage_name, skill_name, task_text))
        return (
            '{"can_reproduce": false, '
            '"reason": "缺少完整 API 接口路径", '
            '"missing_info": ["缺少完整 API 接口路径（例如 /api/v1/...）"]}'
        )

    result = asyncio.run(
        run_src_repro_flow(
            raw_message,
            run_stage=fake_stage_runner,
            emit_message=emitted_messages.append,
        )
    )

    assert len(stage_calls) == 1
    assert stage_calls[0][0] == "SRC 复现分析器"
    assert result["analysis"]["can_reproduce"] is False
    assert result["reproduction_plan"] is None
    assert result["execution_report"] is None
    assert result["final_verdict"] == "not reproducible"
    assert "开始 analyzer 阶段" in emitted_messages[0]
    assert emitted_messages[-1].startswith("`/src` 预检查已结束")


def test_run_src_repro_flow_runs_all_three_stages() -> None:
    stage_calls: list[tuple[str, str, str]] = []
    emitted_messages: list[str] = []
    raw_message = """<src_repro_task>
  <mode>src_reproduction</mode>
  <analysis_mode>full</analysis_mode>
  <requested_root_skill>src_repro_root</requested_root_skill>
  <source_label>report.txt</source_label>
  <report_text><![CDATA[target=https://demo.local path=/admin]]></report_text>
</src_repro_task>"""

    async def fake_stage_runner(stage_name: str, skill_name: str, task_text: str) -> str:
        stage_calls.append((stage_name, skill_name, task_text))
        if stage_name == "SRC 复现分析器":
            return '{"can_reproduce": true, "reason": "信息充分", "missing_info": []}'
        if stage_name == "SRC 复现规划器":
            return "## Detailed Reproduction Steps\n1. Open page\n## Success Criteria\n- Success Marker: leak"
        return "## 4) Final Verdict\n- verdict: reproducible\n- reason: leak observed"

    result = asyncio.run(
        run_src_repro_flow(
            raw_message,
            run_stage=fake_stage_runner,
            emit_message=emitted_messages.append,
        )
    )

    assert [call[0] for call in stage_calls] == [
        "SRC 复现分析器",
        "SRC 复现规划器",
        "SRC 复现执行器",
    ]
    assert result["analysis"]["can_reproduce"] is True
    assert result["reproduction_plan"].startswith("## Detailed Reproduction Steps")
    assert result["final_verdict"] == "reproducible"
    assert emitted_messages[-1].startswith("`/src` 执行已结束")


def test_run_src_repro_flow_skips_analyzer_for_run_mode() -> None:
    stage_calls: list[tuple[str, str, str]] = []
    emitted_messages: list[str] = []
    raw_message = """<src_repro_task>
  <mode>src_reproduction</mode>
  <analysis_mode>skip</analysis_mode>
  <requested_root_skill>src_repro_root</requested_root_skill>
  <source_label>inline</source_label>
  <report_text><![CDATA[target=https://demo.local path=/admin]]></report_text>
</src_repro_task>"""

    async def fake_stage_runner(stage_name: str, skill_name: str, task_text: str) -> str:
        stage_calls.append((stage_name, skill_name, task_text))
        if stage_name == "SRC 复现规划器":
            return "## Detailed Reproduction Steps\n1. Open page\n## Success Criteria\n- Success Marker: leak"
        return "## 4) Final Verdict\n- verdict: blocked\n- reason: proxy blocked"

    result = asyncio.run(
        run_src_repro_flow(
            raw_message,
            run_stage=fake_stage_runner,
            emit_message=emitted_messages.append,
        )
    )

    assert [call[0] for call in stage_calls] == [
        "SRC 复现规划器",
        "SRC 复现执行器",
    ]
    assert result["analysis"]["can_reproduce"] is True
    assert result["analysis"]["reason"] == "用户显式要求跳过分析，直接生成复现步骤并执行。"
    assert result["final_verdict"] == "blocked"
    assert emitted_messages[0].startswith("已收到 `/src run` 任务")
