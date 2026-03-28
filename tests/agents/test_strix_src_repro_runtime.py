import asyncio

from strix.agents.StrixAgent.strix_agent import StrixAgent
from strix.agents.state import AgentState
from strix.src_repro.contracts import SrcReproTask
from strix.tools.agents_graph import agents_graph_actions


def test_wait_for_src_repro_stage_summary_consumes_completion_report() -> None:
    agent = StrixAgent.__new__(StrixAgent)
    agent.state = AgentState(agent_id="root-agent", agent_name="Root Agent", parent_id=None)
    agent.llm_config = type("DummyConfig", (), {"timeout": 5})()

    messages = agents_graph_actions.__dict__["_agent_messages"]
    graph = agents_graph_actions.__dict__["_agent_graph"]
    original_messages = {key: list(value) for key, value in messages.items()}
    original_graph = {
        "nodes": dict(graph["nodes"]),
        "edges": list(graph["edges"]),
    }

    try:
        messages.clear()
        graph["nodes"].clear()
        graph["edges"].clear()
        messages["root-agent"] = [
            {
                "id": "msg-1",
                "from": "child-agent",
                "to": "root-agent",
                "content": (
                    "<agent_completion_report><results><summary>"
                    '{"can_reproduce": true, "reason": "ok", "missing_info": []}'
                    "</summary></results></agent_completion_report>"
                ),
                "read": False,
            }
        ]
        graph["nodes"]["child-agent"] = {"status": "completed"}

        summary = asyncio.run(agent._wait_for_src_repro_stage_summary("child-agent"))

        assert summary == '{"can_reproduce": true, "reason": "ok", "missing_info": []}'
        assert messages["root-agent"][0]["read"] is True
        assert messages["root-agent"][0]["src_repro_consumed"] is True
    finally:
        messages.clear()
        messages.update(original_messages)
        graph["nodes"].clear()
        graph["nodes"].update(original_graph["nodes"])
        graph["edges"].clear()
        graph["edges"].extend(original_graph["edges"])


def test_persist_src_repro_bundle_logs_tool_result(monkeypatch) -> None:
    class _DummyTracer:
        def __init__(self) -> None:
            self.starts: list[tuple[str, dict[str, object]]] = []
            self.updates: list[tuple[int, str, dict[str, object]]] = []

        def log_tool_execution_start(self, agent_id: str, tool_name: str, args: dict[str, object]) -> int:
            self.starts.append((tool_name, args))
            return 1

        def update_tool_execution(self, execution_id: int, status: str, result: dict[str, object]) -> None:
            self.updates.append((execution_id, status, result))

    agent = StrixAgent.__new__(StrixAgent)
    agent.state = AgentState(agent_id="root-agent", agent_name="Root Agent", parent_id=None)

    monkeypatch.setattr(
        "strix.tools.src_repro.save_src_repro_bundle",
        lambda **kwargs: {
            "success": True,
            "output_dir": "F:/Study/strix/strix_runs/demo/src_repro/bundle-1",
            "files": {"manifest": "manifest.json"},
            "echo": kwargs,
        },
    )

    tracer = _DummyTracer()
    task = SrcReproTask(report_text="report body", source_label="inline")
    result = {
        "analysis": {"can_reproduce": True, "reason": "ok", "missing_info": []},
        "reproduction_plan": "plan",
        "execution_report": "trace",
        "final_summary": "Final verdict: reproducible",
    }

    persisted = agent._persist_src_repro_bundle(task, result, tracer)

    assert persisted["success"] is True
    assert tracer.starts[0][0] == "save_src_repro_bundle"
    assert tracer.updates[0][1] == "completed"
    assert "analysis_json" in persisted["echo"]
