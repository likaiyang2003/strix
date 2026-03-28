from strix.tools.agents_graph import agents_graph_actions


def test_get_root_agent_id_prefers_explicit_root() -> None:
    original_root = agents_graph_actions.__dict__["_root_agent_id"]
    original_graph = {
        "nodes": dict(agents_graph_actions.__dict__["_agent_graph"]["nodes"]),
        "edges": list(agents_graph_actions.__dict__["_agent_graph"]["edges"]),
    }

    try:
        agents_graph_actions.__dict__["_agent_graph"]["nodes"].clear()
        agents_graph_actions.__dict__["_agent_graph"]["edges"].clear()
        agents_graph_actions.__dict__["_agent_graph"]["nodes"]["root-a"] = {"parent_id": None}
        agents_graph_actions.__dict__["_root_agent_id"] = "root-a"

        assert agents_graph_actions.get_root_agent_id() == "root-a"
    finally:
        agents_graph_actions.__dict__["_root_agent_id"] = original_root
        agents_graph_actions.__dict__["_agent_graph"]["nodes"].clear()
        agents_graph_actions.__dict__["_agent_graph"]["nodes"].update(original_graph["nodes"])
        agents_graph_actions.__dict__["_agent_graph"]["edges"].clear()
        agents_graph_actions.__dict__["_agent_graph"]["edges"].extend(original_graph["edges"])


def test_get_root_agent_id_falls_back_to_parentless_node() -> None:
    original_root = agents_graph_actions.__dict__["_root_agent_id"]
    original_graph = {
        "nodes": dict(agents_graph_actions.__dict__["_agent_graph"]["nodes"]),
        "edges": list(agents_graph_actions.__dict__["_agent_graph"]["edges"]),
    }

    try:
        agents_graph_actions.__dict__["_root_agent_id"] = None
        agents_graph_actions.__dict__["_agent_graph"]["nodes"].clear()
        agents_graph_actions.__dict__["_agent_graph"]["edges"].clear()
        agents_graph_actions.__dict__["_agent_graph"]["nodes"]["child-a"] = {"parent_id": "root-b"}
        agents_graph_actions.__dict__["_agent_graph"]["nodes"]["root-b"] = {"parent_id": None}

        assert agents_graph_actions.get_root_agent_id() == "root-b"
    finally:
        agents_graph_actions.__dict__["_root_agent_id"] = original_root
        agents_graph_actions.__dict__["_agent_graph"]["nodes"].clear()
        agents_graph_actions.__dict__["_agent_graph"]["nodes"].update(original_graph["nodes"])
        agents_graph_actions.__dict__["_agent_graph"]["edges"].clear()
        agents_graph_actions.__dict__["_agent_graph"]["edges"].extend(original_graph["edges"])


def test_get_agent_instance_returns_instance_or_none() -> None:
    instances = agents_graph_actions.__dict__["_agent_instances"]
    original_instances = dict(instances)

    try:
        sentinel = object()
        instances.clear()
        instances["agent-x"] = sentinel

        assert agents_graph_actions.get_agent_instance("agent-x") is sentinel
        assert agents_graph_actions.get_agent_instance("missing-agent") is None
    finally:
        instances.clear()
        instances.update(original_instances)
