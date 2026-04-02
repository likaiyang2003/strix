from __future__ import annotations

from strix.interface.tui import StrixTUIApp
from strix.tools.agents_graph import agents_graph_actions


class _FakeTracer:
    def __init__(self) -> None:
        self.chat_messages: list[dict[str, object]] = []
        self.agents: dict[str, dict[str, object]] = {}

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
    handle_tree_node_selected = StrixTUIApp.handle_tree_node_selected
    _show_slash_command_error = StrixTUIApp._show_slash_command_error
    _build_src_file_hint_text = StrixTUIApp._build_src_file_hint_text
    _complete_src_file_input = StrixTUIApp._complete_src_file_input

    def __init__(self) -> None:
        self.selected_agent_id = "child-agent"
        self.screen_stack = [object()]
        self.show_splash = False
        self.is_mounted = True
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


class _RealSendApp:
    _send_message_to_agent = StrixTUIApp._send_message_to_agent
    _should_interrupt_agent_on_user_message = StrixTUIApp._should_interrupt_agent_on_user_message

    def __init__(self) -> None:
        self.tracer = _FakeTracer()
        self._displayed_events: set[str] = set()
        self.chat_view_updates = 0
        self.cancelled_agent_ids: list[str] = []

    def _cancel_agent_execution(self, agent_id: str) -> None:
        self.cancelled_agent_ids.append(agent_id)

    def _update_chat_view(self) -> None:
        self.chat_view_updates += 1


class _FakeTreeNode:
    def __init__(self, agent_id: str, allow_expand: bool = False, is_expanded: bool = False) -> None:
        self.data = {"agent_id": agent_id}
        self.allow_expand = allow_expand
        self.is_expanded = is_expanded

    def collapse(self) -> None:
        self.is_expanded = False

    def expand(self) -> None:
        self.is_expanded = True


class _FakeNodeSelectedEvent:
    def __init__(self, node: _FakeTreeNode) -> None:
        self.node = node


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


def test_send_user_message_sends_plain_text_to_selected_child_agent() -> None:
    app = _FakeTuiApp()

    app._send_user_message("这是给子 agent 的补充信息")

    assert app.dispatched_messages == [("child-agent", "这是给子 agent 的补充信息")]
    assert app.focus_refresh_calls == 1


def test_send_message_to_subagent_does_not_interrupt_execution(monkeypatch) -> None:
    sent_messages: list[tuple[str, str]] = []

    child_agent = type(
        "ChildAgent",
        (),
        {"state": type("ChildState", (), {"parent_id": "root-agent"})()},
    )()

    monkeypatch.setattr(agents_graph_actions, "get_agent_instance", lambda agent_id: child_agent)
    monkeypatch.setattr(agents_graph_actions, "get_root_agent_id", lambda: "root-agent")
    monkeypatch.setattr(
        agents_graph_actions,
        "send_user_message_to_agent",
        lambda agent_id, message: sent_messages.append((agent_id, message))
        or {"success": True},
    )

    app = _RealSendApp()

    app._send_message_to_agent("child-agent", "account=admin password=12345")

    assert app.cancelled_agent_ids == []
    assert sent_messages == [("child-agent", "account=admin password=12345")]
    assert app.tracer.chat_messages[-1]["agent_id"] == "child-agent"
    assert app.chat_view_updates == 1


def test_send_message_to_root_agent_still_interrupts_execution(monkeypatch) -> None:
    sent_messages: list[tuple[str, str]] = []

    root_agent = type(
        "RootAgent",
        (),
        {"state": type("RootState", (), {"parent_id": None})()},
    )()

    monkeypatch.setattr(agents_graph_actions, "get_agent_instance", lambda agent_id: root_agent)
    monkeypatch.setattr(agents_graph_actions, "get_root_agent_id", lambda: "root-agent")
    monkeypatch.setattr(
        agents_graph_actions,
        "send_user_message_to_agent",
        lambda agent_id, message: sent_messages.append((agent_id, message))
        or {"success": True},
    )

    app = _RealSendApp()

    app._send_message_to_agent("root-agent", "only test post-login flow")

    assert app.cancelled_agent_ids == ["root-agent"]
    assert sent_messages == [("root-agent", "only test post-login flow")]
    assert app.tracer.chat_messages[-1]["agent_id"] == "root-agent"
    assert app.chat_view_updates == 1


def test_handle_tree_node_selected_switches_selected_agent() -> None:
    app = _FakeTuiApp()
    app.selected_agent_id = "root-agent"

    app.handle_tree_node_selected(_FakeNodeSelectedEvent(_FakeTreeNode("child-agent")))

    assert app.selected_agent_id == "child-agent"


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
    assert app.notifications == [
        "Usage: `/src <report_text>` or `/src @<file>` or `/src run <report_text>` or "
        "`/src run @<file>` or `/src verify <report_text>` or `/src verify @<file>`"
    ]
    assert app.chat_view_updates == 1
    assert app.tracer.chat_messages[-1]["agent_id"] == "child-agent"
    assert "/src 命令错误" in str(app.tracer.chat_messages[-1]["content"])
    assert "`/src verify @<file>`" in str(app.tracer.chat_messages[-1]["content"])


def test_send_user_message_routes_src_run_command_to_root_agent(monkeypatch) -> None:
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

    app._send_user_message("/src run target=https://app.example.com path=/admin")

    assert app.selected_agent_id == "root-agent"
    assert loaded_skills == [("root-agent", ["src_repro_root"])]
    assert app.focus_refresh_calls == 1
    assert app.dispatched_messages[0][0] == "root-agent"
    assert "<src_repro_task>" in app.dispatched_messages[0][1]
    assert "<analysis_mode>skip</analysis_mode>" in app.dispatched_messages[0][1]
    assert "target=https://app.example.com path=/admin" in app.dispatched_messages[0][1]


def test_send_user_message_routes_src_verify_command_to_root_agent(monkeypatch) -> None:
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

    app._send_user_message("/src verify target=https://app.example.com path=/admin")

    assert app.selected_agent_id == "root-agent"
    assert loaded_skills == [("root-agent", ["src_verify_root"])]
    assert "<mode>src_verification</mode>" in app.dispatched_messages[0][1]
    assert "<execution_stage>verify</execution_stage>" in app.dispatched_messages[0][1]
    assert "<analysis_mode>full</analysis_mode>" in app.dispatched_messages[0][1]
    assert "不单独运行 analyzer" in app.dispatched_messages[0][1]

def test_send_user_message_surfaces_src_verify_run_removed_error_to_user(monkeypatch) -> None:
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

    app._send_user_message("/src verify run target=https://app.example.com path=/admin")

    assert app.selected_agent_id == "child-agent"
    assert loaded_skills == []
    assert app.dispatched_messages == []
    assert app.notifications == [
        "`/src verify run` 已移除，请直接使用 `/src verify <report_text>` 或 `/src verify @<file>`。"
    ]
    assert "/src verify run" in str(app.tracer.chat_messages[-1]["content"])


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


def test_build_src_file_hint_text_lists_vul_report_files(monkeypatch, tmp_path) -> None:
    report_dir = tmp_path / "Vul_report"
    report_dir.mkdir()
    (report_dir / "alpha.md").write_text("a", encoding="utf-8")
    (report_dir / "beta.md").write_text("b", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    app = _FakeTuiApp()
    hint = app._build_src_file_hint_text("/src @")

    assert str(report_dir.resolve()) in hint
    assert "alpha.md" in hint
    assert "beta.md" in hint


def test_build_src_file_hint_text_filters_run_mode(monkeypatch, tmp_path) -> None:
    report_dir = tmp_path / "Vul_report"
    report_dir.mkdir()
    (report_dir / "audit.md").write_text("a", encoding="utf-8")
    (report_dir / "beta.md").write_text("b", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    app = _FakeTuiApp()
    hint = app._build_src_file_hint_text("/src run @au")

    assert "audit.md" in hint
    assert "beta.md" not in hint


def test_build_src_file_hint_text_filters_verify_run_mode(monkeypatch, tmp_path) -> None:
    report_dir = tmp_path / "Vul_report"
    report_dir.mkdir()
    (report_dir / "audit.md").write_text("a", encoding="utf-8")
    (report_dir / "beta.md").write_text("b", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    app = _FakeTuiApp()
    hint = app._build_src_file_hint_text("/src verify run @au")

    assert hint == ""


def test_complete_src_file_input_completes_unique_match(monkeypatch, tmp_path) -> None:
    report_dir = tmp_path / "Vul_report"
    report_dir.mkdir()
    (report_dir / "audit.md").write_text("a", encoding="utf-8")
    (report_dir / "beta.md").write_text("b", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    app = _FakeTuiApp()
    completed = app._complete_src_file_input("/src run @au")

    assert completed == "/src run @audit.md"


def test_complete_src_file_input_completes_unique_match_for_verify_mode(monkeypatch, tmp_path) -> None:
    report_dir = tmp_path / "Vul_report"
    report_dir.mkdir()
    (report_dir / "audit.md").write_text("a", encoding="utf-8")
    (report_dir / "beta.md").write_text("b", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    app = _FakeTuiApp()
    completed = app._complete_src_file_input("/src verify run @au")

    assert completed is None


def test_complete_src_file_input_returns_none_for_ambiguous_match(monkeypatch, tmp_path) -> None:
    report_dir = tmp_path / "Vul_report"
    report_dir.mkdir()
    (report_dir / "audit.md").write_text("a", encoding="utf-8")
    (report_dir / "audio.md").write_text("b", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    app = _FakeTuiApp()
    completed = app._complete_src_file_input("/src run @au")

    assert completed is None
