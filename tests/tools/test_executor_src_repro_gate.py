from strix.agents.state import AgentState
from strix.tools.executor import _validate_src_repro_tool_gate


def _build_src_reproducer_state(plan_created: bool = False) -> AgentState:
    agent_state = AgentState(agent_id="agent-src-gate")
    agent_state.update_context("src_repro_plan_required", True)
    agent_state.update_context("src_repro_stage", "reproducer")
    agent_state.update_context("src_repro_plan_created", plan_created)
    return agent_state


def test_src_repro_gate_blocks_execution_before_plan_created() -> None:
    agent_state = _build_src_reproducer_state(plan_created=False)

    error = _validate_src_repro_tool_gate("send_request", agent_state)

    assert error is not None
    assert "create_src_plan" in error


def test_src_repro_gate_blocks_legacy_todo_tools() -> None:
    agent_state = _build_src_reproducer_state(plan_created=True)

    error = _validate_src_repro_tool_gate("create_todo", agent_state)

    assert error is not None
    assert "通用 todo 工具" in error


def test_src_repro_gate_blocks_create_agent_for_reproducer() -> None:
    agent_state = _build_src_reproducer_state(plan_created=True)

    error = _validate_src_repro_tool_gate("create_agent", agent_state)

    assert error is not None
    assert "禁止创建额外子 agent" in error


def test_src_repro_gate_allows_execution_after_plan_created() -> None:
    agent_state = _build_src_reproducer_state(plan_created=True)

    error = _validate_src_repro_tool_gate("send_request", agent_state)

    assert error is None


def test_src_repro_gate_does_not_apply_to_non_src_agents() -> None:
    agent_state = AgentState(agent_id="agent-normal")

    error = _validate_src_repro_tool_gate("create_todo", agent_state)

    assert error is None
