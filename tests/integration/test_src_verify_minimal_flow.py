import asyncio
import json
from pathlib import Path

from strix.agents.StrixAgent.strix_agent import StrixAgent
from strix.agents.state import AgentState
from strix.interface.slash_commands import build_src_task_message, parse_src_command
from strix.telemetry import tracer as tracer_module
from strix.telemetry.tracer import Tracer, set_global_tracer
from strix.tools.agents_graph import agents_graph_actions


def test_src_verify_minimal_flow_persists_bundle(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("STRIX_TELEMETRY", "0")
    monkeypatch.setattr(tracer_module, "_global_tracer", None)
    monkeypatch.setattr(tracer_module, "_OTEL_BOOTSTRAPPED", False)
    monkeypatch.setattr(tracer_module, "_OTEL_REMOTE_ENABLED", False)

    tracer = Tracer("src-verify-minimal-flow")
    set_global_tracer(tracer)

    agent = StrixAgent.__new__(StrixAgent)
    agent.state = AgentState(agent_id="root-agent", agent_name="Root Agent", parent_id=None)
    agent.llm_config = type("DummyConfig", (), {"timeout": 5})()

    task_message = build_src_task_message(
        parse_src_command("/src verify target=https://demo.local path=/admin")
    )
    agent.state.add_message("user", task_message)

    stage_calls: list[tuple[str, str, bool | None]] = []
    messages = agents_graph_actions.__dict__["_agent_messages"]
    graph = agents_graph_actions.__dict__["_agent_graph"]
    original_messages = {key: list(value) for key, value in messages.items()}
    original_graph = {
        "nodes": dict(graph["nodes"]),
        "edges": list(graph["edges"]),
    }

    reproducer_summary = (
        "## 1) Execution Todo\n"
        "- Open the page\n"
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

    def _fake_create_agent(
        agent_state: AgentState,
        task: str,
        name: str,
        inherit_context: bool = True,
        skills: str | None = None,
        interactive_override: bool | None = None,
    ) -> dict[str, object]:
        del task, agent_state
        child_agent_id = f"{name.lower().replace(' ', '-')}-id"
        stage_calls.append((name, skills or "", interactive_override))

        summary = reproducer_summary

        messages.setdefault("root-agent", []).append(
            {
                "id": f"msg-{child_agent_id}",
                "from": child_agent_id,
                "to": "root-agent",
                "content": (
                    "<agent_completion_report><results><summary>"
                    f"{summary}"
                    "</summary></results></agent_completion_report>"
                ),
                "read": False,
            }
        )
        graph["nodes"][child_agent_id] = {"status": "completed"}

        return {
            "success": True,
            "agent_id": child_agent_id,
            "message": f"created {name}",
            "agent_info": {"id": child_agent_id, "name": name},
        }

    monkeypatch.setattr(
        "strix.tools.agents_graph.agents_graph_actions.create_agent",
        _fake_create_agent,
    )

    try:
        result = asyncio.run(agent._maybe_handle_special_task(tracer))
    finally:
        messages.clear()
        messages.update(original_messages)
        graph["nodes"].clear()
        graph["nodes"].update(original_graph["nodes"])
        graph["edges"].clear()
        graph["edges"].extend(original_graph["edges"])
        monkeypatch.setattr(tracer_module, "_global_tracer", None)

    assert result is not None
    assert result["mode"] == "src_verification"
    assert result["final_verdict"] == "fixed"
    assert [call[0] for call in stage_calls] == ["SRC Verify Executor"]
    assert [call[1] for call in stage_calls] == ["verify_plan_executor"]
    assert all(call[2] is False for call in stage_calls)

    artifacts = result["artifacts"]
    output_dir = Path(artifacts["output_dir"])
    assert output_dir.exists()
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["final_verdict"] == "fixed"
