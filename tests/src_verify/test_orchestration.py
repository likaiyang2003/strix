import asyncio

from strix.src_repro.contracts import SrcReproAnalysis, SrcReproTask
from strix.src_verify import run_src_verify_flow
from strix.src_verify.orchestration import _build_verify_executor_task


def test_run_src_verify_flow_uses_verify_executor_skill_and_fixed_verdict() -> None:
    stage_calls: list[tuple[str, str, str]] = []
    emitted_messages: list[str] = []
    raw_message = """<src_repro_task>
  <mode>src_verification</mode>
  <execution_stage>verify</execution_stage>
  <analysis_mode>full</analysis_mode>
  <requested_root_skill>src_verify_root</requested_root_skill>
  <source_label>report.txt</source_label>
  <report_text><![CDATA[target=https://demo.local path=/admin]]></report_text>
</src_repro_task>"""

    async def fake_stage_runner(stage_name: str, skill_name: str, task_text: str) -> str:
        stage_calls.append((stage_name, skill_name, task_text))
        return (
            "## 1) Execution Todo\n"
            "- Open page\n"
            "- Verify fixed behavior\n\n"
            "## 2) Verification Execution Notes\n"
            "- observed fixed behavior\n\n"
            "## 3) Skills/MCP Execution Trace\n"
            "- requested tool: browser_action\n\n"
            "## 4) Final Verdict\n"
            "- verdict: fixed\n"
            "- reason: fix verified\n"
            "- comparability: established\n"
            "- old_success_marker: not_hit\n"
            "- secure_behavior: observed"
        )

    result = asyncio.run(
        run_src_verify_flow(
            raw_message,
            run_stage=fake_stage_runner,
            emit_message=emitted_messages.append,
        )
    )

    assert stage_calls == [
        (
            "SRC Verify Executor",
            "verify_plan_executor",
            stage_calls[0][2],
        )
    ]
    assert result["mode"] == "src_verification"
    assert result["execution_stage"] == "verify"
    assert result["final_verdict"] == "fixed"
    assert "/src verify" in emitted_messages[0]
    assert "verify executor" in emitted_messages[0]


def test_run_src_verify_flow_supports_still_reproducible_verdict() -> None:
    stage_calls: list[tuple[str, str, str]] = []
    emitted_messages: list[str] = []
    raw_message = """<src_repro_task>
  <mode>src_verification</mode>
  <execution_stage>verify</execution_stage>
  <analysis_mode>skip</analysis_mode>
  <requested_root_skill>src_verify_root</requested_root_skill>
  <source_label>inline</source_label>
  <report_text><![CDATA[target=https://demo.local path=/admin]]></report_text>
</src_repro_task>"""

    async def fake_stage_runner(stage_name: str, skill_name: str, task_text: str) -> str:
        stage_calls.append((stage_name, skill_name, task_text))
        return (
            "## 1) Execution Todo\n"
            "- Open page\n\n"
            "## 2) Verification Execution Notes\n"
            "- old success marker hit again\n\n"
            "## 3) Skills/MCP Execution Trace\n"
            "- requested tool: browser_action\n\n"
            "## 4) Final Verdict\n"
            "- verdict: still reproducible\n"
            "- reason: xss alert still triggered\n"
            "- comparability: established\n"
            "- old_success_marker: hit\n"
            "- secure_behavior: not_observed"
        )

    result = asyncio.run(
        run_src_verify_flow(
            raw_message,
            run_stage=fake_stage_runner,
            emit_message=emitted_messages.append,
        )
    )

    assert [call[:2] for call in stage_calls] == [("SRC Verify Executor", "verify_plan_executor")]
    assert result["mode"] == "src_verification"
    assert result["execution_stage"] == "verify"
    assert result["final_verdict"] == "still reproducible"
    assert "/src verify" in emitted_messages[0]


def test_run_src_verify_flow_supports_blocked_verdict() -> None:
    stage_calls: list[tuple[str, str, str]] = []
    emitted_messages: list[str] = []
    raw_message = """<src_repro_task>
  <mode>src_verification</mode>
  <execution_stage>verify</execution_stage>
  <analysis_mode>full</analysis_mode>
  <requested_root_skill>src_verify_root</requested_root_skill>
  <source_label>inline</source_label>
  <report_text><![CDATA[target=https://demo.local path=/admin]]></report_text>
</src_repro_task>"""

    async def fake_stage_runner(stage_name: str, skill_name: str, task_text: str) -> str:
        stage_calls.append((stage_name, skill_name, task_text))
        return (
            "## 1) Execution Todo\n"
            "- Open page\n\n"
            "## 2) Verification Execution Notes\n"
            "- blocked by environment\n\n"
            "## 3) Skills/MCP Execution Trace\n"
            "- requested tool: browser_action\n\n"
            "## 4) Final Verdict\n"
            "- verdict: blocked\n"
            "- reason: environment blocked\n"
            "- comparability: missing\n"
            "- old_success_marker: unknown\n"
            "- secure_behavior: unknown"
        )

    result = asyncio.run(
        run_src_verify_flow(
            raw_message,
            run_stage=fake_stage_runner,
            emit_message=emitted_messages.append,
        )
    )

    assert [call[:2] for call in stage_calls] == [("SRC Verify Executor", "verify_plan_executor")]
    assert result["mode"] == "src_verification"
    assert result["execution_stage"] == "verify"
    assert result["final_verdict"] == "blocked"


def test_build_verify_executor_task_uses_verify_executor_tag() -> None:
    task = SrcReproTask(
        report_text="report body",
        source_label="inline",
        mode="src_verification",
        requested_root_skill="src_verify_root",
        execution_stage="verify",
    )
    analysis = SrcReproAnalysis(can_reproduce=True, reason="ok", missing_info=[])

    rendered = _build_verify_executor_task(task, analysis)

    assert "<src_verify_executor_task>" in rendered
    assert "</src_verify_executor_task>" in rendered
    assert "<src_verify_reproducer_task>" not in rendered
    assert "still reproducible" in rendered
    assert "fixed" in rendered
    assert "comparability" in rendered
