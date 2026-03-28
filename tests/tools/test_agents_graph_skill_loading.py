from strix.agents.state import AgentState
from strix.tools.agents_graph import agents_graph_actions


class _DummyLLM:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def add_skills(self, skills: list[str]) -> list[str]:
        self.calls.append(list(skills))
        return list(skills)


class _DummyAgent:
    def __init__(self) -> None:
        self.llm = _DummyLLM()


def test_load_skills_into_agent_updates_llm_and_state() -> None:
    instances = agents_graph_actions.__dict__["_agent_instances"]
    states = agents_graph_actions.__dict__["_agent_states"]
    graph = agents_graph_actions.__dict__["_agent_graph"]
    original_instances = dict(instances)
    original_states = dict(states)
    original_graph = {
        "nodes": dict(graph["nodes"]),
        "edges": list(graph["edges"]),
    }

    try:
        agent = _DummyAgent()
        state = AgentState(agent_id="root-agent", agent_name="Root Agent", parent_id=None)
        instances.clear()
        states.clear()
        graph["nodes"].clear()
        graph["edges"].clear()
        instances["root-agent"] = agent
        states["root-agent"] = state
        graph["nodes"]["root-agent"] = {"parent_id": None}

        result = agents_graph_actions.load_skills_into_agent(
            "root-agent",
            ["src_repro_root"],
        )

        assert result["success"] is True
        assert result["newly_loaded_skills"] == ["src_repro_root"]
        assert agent.llm.calls == [["src_repro_root"]]
        assert state.context["loaded_skills"] == ["src_repro_root"]
        assert graph["nodes"]["root-agent"]["state"]["context"]["loaded_skills"] == [
            "src_repro_root"
        ]
    finally:
        instances.clear()
        instances.update(original_instances)
        states.clear()
        states.update(original_states)
        graph["nodes"].clear()
        graph["nodes"].update(original_graph["nodes"])
        graph["edges"].clear()
        graph["edges"].extend(original_graph["edges"])


def test_load_skills_into_agent_rejects_missing_agent() -> None:
    result = agents_graph_actions.load_skills_into_agent("missing-agent", ["src_repro_root"])

    assert result["success"] is False
    assert "not available" in result["error"]
