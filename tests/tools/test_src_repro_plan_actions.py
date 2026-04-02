from strix.agents.state import AgentState
from strix.tools import get_tool_names
from strix.tools.src_repro.src_repro_plan_actions import (
    create_src_plan,
    get_src_plan,
    update_src_plan_step,
)


def test_src_repro_plan_tools_are_registered() -> None:
    names = get_tool_names()

    assert "create_src_plan" in names
    assert "get_src_plan" in names
    assert "update_src_plan_step" in names


def test_create_src_plan_creates_ordered_steps_and_context() -> None:
    agent_state = AgentState(agent_id="agent-src-plan")

    result = create_src_plan(
        agent_state,
        title="Demo Plan",
        source_label="inline",
        steps="""
        [
          {
            "title": "打开首页",
            "objective": "进入入口",
            "suggested_action": "browser_action(action=\\"launch\\", url=\\"https://demo.local\\")",
            "required_inputs": ["https://demo.local"],
            "expected_evidence": "首页成功加载",
            "evidence_type": "ui",
            "success_judgment": "首页加载且入口可见则该步成功",
            "negative_judgment": "首页已加载但关键入口缺失则记为负向结果",
            "blocked_judgment": "页面无法访问或无法完成加载则该步阻塞",
            "failure_judgment": "页面未加载或入口不存在则该步失败",
            "stop_rule": "无法访问则 blocked"
          },
          {
            "title": "查看代理请求"
          }
        ]
        """,
    )

    assert result["success"] is True
    assert result["plan"]["title"] == "Demo Plan"
    assert result["plan"]["steps"][0]["step_id"] == "S1"
    assert result["plan"]["steps"][0]["success_judgment"] == "首页加载且入口可见则该步成功"
    assert result["plan"]["steps"][0]["negative_judgment"] == "首页已加载但关键入口缺失则记为负向结果"
    assert result["plan"]["steps"][0]["blocked_judgment"] == "页面无法访问或无法完成加载则该步阻塞"
    assert result["plan"]["steps"][0]["failure_judgment"] == "页面未加载或入口不存在则该步失败"
    assert result["plan"]["steps"][1]["step_id"] == "S2"
    assert agent_state.context["src_repro_plan_created"] is True
    assert agent_state.context["src_repro_plan_required"] is True
    assert agent_state.context["src_repro_plan_step_count"] == 2


def test_get_src_plan_returns_existing_plan() -> None:
    agent_state = AgentState(agent_id="agent-src-plan-get")
    create_src_plan(agent_state, steps='["第一步", "第二步"]')

    result = get_src_plan(agent_state)

    assert result["success"] is True
    assert result["summary"]["total"] == 2
    assert result["plan"]["steps"][0]["title"] == "第一步"


def test_update_src_plan_step_updates_status_and_notes() -> None:
    agent_state = AgentState(agent_id="agent-src-plan-update")
    create_src_plan(agent_state, steps='["第一步", "第二步"]')

    result = update_src_plan_step(
        agent_state,
        updates="""
        [
          {
            "step_id": "S1",
            "status": "done",
            "actual_action": "browser_action(action=\\"launch\\", url=\\"https://demo.local\\")",
            "actual_observation": "页面打开成功",
            "actual_evidence": "看到了首页标题"
          },
          {
            "step_id": "S2",
            "status": "in_progress",
            "notes": "正在查看代理"
          }
        ]
        """,
    )

    assert result["updated_count"] == 2
    assert "plan" not in result
    assert result["view"] == "delta"
    assert result["updated_steps"][0]["status"] == "done"
    assert result["updated_steps"][0]["actual_evidence"] == "看到了首页标题"
    assert result["updated_steps"][1]["status"] == "in_progress"
    assert result["latest_step"]["step_id"] == "S2"
    assert result["current_in_progress_step"]["step_id"] == "S2"
    assert result["summary"]["done"] == 1
    assert result["summary"]["in_progress"] == 1


def test_src_repro_plan_response_is_snapshot_not_shared_reference() -> None:
    agent_state = AgentState(agent_id="agent-src-plan-snapshot")

    created = create_src_plan(agent_state, steps='["第一步", "第二步"]')
    created_plan_snapshot = created["plan"]

    update_src_plan_step(
        agent_state,
        step_id="S1",
        status="done",
        actual_action="send_request",
        actual_observation="请求已发送",
        actual_evidence="返回 200",
    )

    assert created_plan_snapshot["steps"][0]["status"] == "pending"
    assert created_plan_snapshot["steps"][0]["actual_action"] is None
    assert created["summary"]["pending"] == 2
    assert created["summary"]["done"] == 0


def test_create_src_plan_rejects_duplicate_without_replace() -> None:
    agent_state = AgentState(agent_id="agent-src-plan-duplicate")
    create_src_plan(agent_state, steps='["第一步"]')

    result = create_src_plan(agent_state, steps='["第二步"]')

    assert result["success"] is False
    assert "replace=true" in result["error"]
