from __future__ import annotations

from strix.interface.tui import StrixTUIApp
from strix.tools.agents_graph import agents_graph_actions


class _FakeTracer:
    def __init__(self) -> None:
        self.chat_messages: list[dict[str, object]] = []

    def log_chat_message(
        self,
        content: str,
        role: str,
        agent_id: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> None:
        self.chat_messages.append(
            {
                "content": content,
                "role": role,
                "agent_id": agent_id,
                "metadata": metadata or {},
            }
        )


class _FakeTuiApp:
    _send_user_message = StrixTUIApp._send_user_message
    _handle_slash_command = StrixTUIApp._handle_slash_command
    _show_slash_command_error = StrixTUIApp._show_slash_command_error

    def __init__(self) -> None:
        self.selected_agent_id = "child-agent"
        self.dispatched_messages: list[tuple[str, str]] = []
        self.focus_refresh_calls = 0
        self.notifications: list[str] = []
        self.tracer = _FakeTracer()
        self._displayed_events: set[str] = set()
        self.chat_view_updates = 0

    def _send_message_to_agent(self, agent_id: str, message: str) -> None:
        self.dispatched_messages.append((agent_id, message))

    def call_after_refresh(self, callback: object) -> None:
        self.focus_refresh_calls += 1

    def _focus_chat_input(self) -> None:
        return None

    def _update_chat_view(self) -> None:
        self.chat_view_updates += 1

    def notify(self, message: str, timeout: int | None = None) -> None:
        del timeout
        self.notifications.append(message)


def test_send_user_message_routes_src_command_to_root_agent(monkeypatch) -> None:
    loaded_skills: list[tuple[str, list[str]]] = []

    monkeypatch.setattr(agents_graph_actions, "get_root_agent_id", lambda: "root-agent")
    monkeypatch.setattr(
        agents_graph_actions,
        "load_skills_into_agent",
        lambda agent_id, skill_names: (
            loaded_skills.append((agent_id, skill_names))
            or {
                "success": True,
                "loaded_skills": skill_names,
                "newly_loaded_skills": skill_names,
                "already_loaded_skills": [],
            }
        ),
    )
    app = _FakeTuiApp()

    app._send_user_message("/src target=https://app.example.com path=/admin")

    assert app.selected_agent_id == "root-agent"
    assert loaded_skills == [("root-agent", ["src_repro_root"])]
    assert app.focus_refresh_calls == 1
    assert app.dispatched_messages[0][0] == "root-agent"
    assert "<src_repro_task>" in app.dispatched_messages[0][1]
    assert "target=https://app.example.com path=/admin" in app.dispatched_messages[0][1]


def test_send_user_message_surfaces_src_usage_error_to_user(monkeypatch) -> None:
    monkeypatch.setattr(agents_graph_actions, "get_root_agent_id", lambda: "root-agent")
    monkeypatch.setattr(
        agents_graph_actions,
        "load_skills_into_agent",
        lambda agent_id, skill_names: {
            "success": True,
            "loaded_skills": skill_names,
            "newly_loaded_skills": skill_names,
            "already_loaded_skills": [],
        },
    )
    app = _FakeTuiApp()

    app._send_user_message("/src")

    assert app.selected_agent_id == "child-agent"
    assert app.dispatched_messages == []
    assert app.focus_refresh_calls == 1
    assert app.notifications == ["Usage: `/src <report_text>` or `/src @<file>`"]
    assert app.chat_view_updates == 1
    assert app.tracer.chat_messages[-1]["agent_id"] == "child-agent"
    assert "/src 命令错误" in str(app.tracer.chat_messages[-1]["content"])
    assert "Usage: `/src <report_text>` or `/src @<file>`" in str(
        app.tracer.chat_messages[-1]["content"]
    )


def test_send_user_message_surfaces_src_missing_file_error_to_user(monkeypatch) -> None:
    monkeypatch.setattr(agents_graph_actions, "get_root_agent_id", lambda: "root-agent")
    monkeypatch.setattr(
        agents_graph_actions,
        "load_skills_into_agent",
        lambda agent_id, skill_names: {
            "success": True,
            "loaded_skills": skill_names,
            "newly_loaded_skills": skill_names,
            "already_loaded_skills": [],
        },
    )
    app = _FakeTuiApp()

    app._send_user_message("/src @missing-report.txt")

    assert app.dispatched_messages == []
    assert app.focus_refresh_calls == 1
    assert app.notifications
    assert app.notifications[-1].startswith("SRC report file not found:")
    assert app.chat_view_updates == 1
    assert app.tracer.chat_messages[-1]["agent_id"] == "child-agent"
    assert "SRC report file not found:" in str(app.tracer.chat_messages[-1]["content"])
