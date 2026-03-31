import asyncio

from strix.src_repro import (
    build_reproducer_task,
    extract_execution_todo,
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


def test_extract_execution_todo_returns_first_section() -> None:
    execution_report = """## 1) Execution Todo
- Open page
- Replay request

## 2) Reproduction Execution Notes
- observed"""

    todo = extract_execution_todo(execution_report)

    assert todo.startswith("## 1) Execution Todo")
    assert "Replay request" in todo
    assert "Reproduction Execution Notes" not in todo


def test_build_reproducer_task_embeds_report_text_only() -> None:
    task = SrcReproTask(
        report_text="report body",
        source_label=r"F:\Study\strix\Vul_report\demo-report.md",
    )
    analysis = SrcReproAnalysis(can_reproduce=True, reason="ok", missing_info=[])

    rendered = build_reproducer_task(task, analysis)

    assert "<src_repro_reproducer_task>" in rendered
    assert "<report_text><![CDATA[" in rendered
    assert "report body" in rendered
    assert "## 1) Execution Todo" in rendered
    assert "<analysis_json><![CDATA[" in rendered
    assert "create_src_repro_plan" in rendered
    assert "update_src_repro_plan_step" in rendered
    assert "get_src_repro_plan" in rendered
    assert "不得默认用裸 `send_request` 作为第一条主路线" in rendered
    assert "先进入 UI 并生成当前会话中的真实请求" in rendered
    assert "不要立刻结束整个任务，应继续走该有界分支" in rendered
    assert "先用三层规则思考" in rendered
    assert "一个决定性验证节点只对应一个步骤" in rendered
    assert "验证节点骨架" in rendered
    assert "漏洞族覆盖规则" in rendered
    assert "统一通过 verdict 闸门收口" in rendered
    assert "优先使用 `success_judgment`、`negative_judgment`、`blocked_judgment`" in rendered
    assert "`success_judgment` 只写目标侧成功证据" in rendered
    assert "judgment 只能评价当前步骤对应的那个节点，不得跨步引用后续节点" in rendered
    assert "本地信号不等于目标侧成功证据" in rendered
    assert "只有真实请求/响应证据、目标页面回显/存储证据" in rendered
    assert "判 `not reproducible`；还是决定性验证根本未完成，从而判 `blocked`" in rendered
    assert "`todo`" in rendered
    assert "<original_report_source>" not in rendered
    assert "<reproduction_plan>" not in rendered


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
    assert stage_calls[0][0] == "SRC Repro Analyzer"
    assert result["analysis"]["can_reproduce"] is False
    assert result["reproduction_plan"] is None
    assert result["execution_report"] is None
    assert result["final_verdict"] == "not reproducible"
    assert "/src" in emitted_messages[0]
    assert "analyzer" in emitted_messages[0]
    assert "不可复现" in emitted_messages[-1]


def test_run_src_repro_flow_runs_analyzer_then_reproducer() -> None:
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
        if stage_name == "SRC Repro Analyzer":
            return '{"can_reproduce": true, "reason": "信息充分", "missing_info": []}'
        return (
            "## 1) Execution Todo\n"
            "- Open page\n"
            "- Replay request\n\n"
            "## 2) Reproduction Execution Notes\n"
            "- observed request\n\n"
            "## 3) Skills/MCP Execution Trace\n"
            "- requested tool: send_request\n\n"
            "## 4) Final Verdict\n"
            "- verdict: reproducible\n"
            "- reason: leak observed"
        )

    result = asyncio.run(
        run_src_repro_flow(
            raw_message,
            run_stage=fake_stage_runner,
            emit_message=emitted_messages.append,
        )
    )

    assert [call[0] for call in stage_calls] == [
        "SRC Repro Analyzer",
        "SRC Reproducer",
    ]
    assert result["analysis"]["can_reproduce"] is True
    assert result["reproduction_plan"].startswith("## 1) Execution Todo")
    assert result["final_verdict"] == "reproducible"
    assert "reproducer" in emitted_messages[-2]
    assert emitted_messages[-1].startswith("`/src`")


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
        return (
            "## 1) Execution Todo\n"
            "- Open page\n\n"
            "## 2) Reproduction Execution Notes\n"
            "- proxy blocked\n\n"
            "## 3) Skills/MCP Execution Trace\n"
            "- requested tool: browser_action\n\n"
            "## 4) Final Verdict\n"
            "- verdict: blocked\n"
            "- reason: proxy blocked"
        )

    result = asyncio.run(
        run_src_repro_flow(
            raw_message,
            run_stage=fake_stage_runner,
            emit_message=emitted_messages.append,
        )
    )

    assert [call[0] for call in stage_calls] == ["SRC Reproducer"]
    assert result["analysis"]["can_reproduce"] is True
    assert result["analysis"]["reason"] == "用户显式要求跳过分析，直接进入复现执行。"
    assert result["final_verdict"] == "blocked"
    assert "/src run" in emitted_messages[0]
