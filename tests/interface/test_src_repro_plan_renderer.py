from rich.text import Text

from strix.interface.tui import StrixTUIApp


class _FakeRenderApp:
    _render_tool_content_simple = StrixTUIApp._render_tool_content_simple
    _render_streaming_tool = StrixTUIApp._render_streaming_tool
    _extract_widget_content = staticmethod(StrixTUIApp._extract_widget_content)

    def _render_error_details(self, text: Text, tool_name: str, args: dict[str, str]) -> Text:
        del tool_name, args
        return text


def test_render_tool_content_simple_supports_src_repro_plan_renderer() -> None:
    app = _FakeRenderApp()

    result = app._render_tool_content_simple(
        {
            "tool_name": "create_src_repro_plan",
            "args": {},
            "status": "completed",
            "result": {
                "success": True,
                "summary": {
                    "total": 2,
                    "pending": 1,
                    "in_progress": 1,
                    "done": 0,
                    "blocked": 0,
                    "skipped": 0,
                },
                "plan": {
                    "title": "Demo Plan",
                    "source_label": "inline",
                    "steps": [
                        {
                            "step_id": "S1",
                            "title": "打开首页",
                            "objective": "进入入口",
                            "suggested_action": "browser_action(action=\"launch\", url=\"https://demo.local\")",
                            "required_inputs": ["https://demo.local"],
                            "expected_evidence": "首页加载成功",
                            "success_judgment": "首页加载且入口可见则该步成功",
                            "negative_judgment": "首页已加载但关键入口缺失则记为负向结果",
                            "blocked_judgment": "页面无法访问则该步阻塞",
                            "failure_judgment": "页面未加载则该步失败",
                            "status": "done",
                        },
                        {
                            "step_id": "S2",
                            "title": "检查代理流量",
                            "status": "in_progress",
                            "notes": "正在查看 POST 请求",
                        },
                    ],
                },
            },
        }
    )

    assert isinstance(result, Text)
    assert "Demo Plan" in result.plain
    assert "S1 打开首页" in result.plain
    assert "检查代理流量" in result.plain
    assert "成功判断" in result.plain
    assert "负向判断" in result.plain
    assert "阻塞判断" in result.plain
    assert "首页加载且入口可见则该步成功" in result.plain
    assert "首页已加载但关键入口缺失则记为负向结果" in result.plain
    assert "页面无法访问则该步阻塞" in result.plain
    assert "正在查看 POST 请求" in result.plain


def test_render_tool_content_simple_renders_src_repro_update_as_delta() -> None:
    app = _FakeRenderApp()

    result = app._render_tool_content_simple(
        {
            "tool_name": "update_src_repro_plan_step",
            "args": {},
            "status": "completed",
            "result": {
                "success": True,
                "view": "delta",
                "title": "Demo Plan",
                "source_label": "inline",
                "updated_count": 1,
                "summary": {
                    "total": 2,
                    "pending": 0,
                    "in_progress": 1,
                    "done": 1,
                    "blocked": 0,
                    "skipped": 0,
                },
                "updated_steps": [
                    {
                        "step_id": "S2",
                        "title": "检查代理流量",
                        "status": "in_progress",
                        "notes": "正在查看 POST 请求",
                        "expected_evidence": "响应中包含 payload",
                    }
                ],
            },
        }
    )

    assert isinstance(result, Text)
    assert "已更新 1 步" in result.plain
    assert "S2 检查代理流量" in result.plain
    assert "正在查看 POST 请求" in result.plain
    assert "响应中包含 payload" not in result.plain
    assert "Demo Plan" not in result.plain


def test_build_src_repro_status_content_is_compact() -> None:
    result = StrixTUIApp._build_src_repro_status_content(
        "SRC Reproducer",
        {
            "title": "Demo Plan",
            "source_label": "inline",
            "steps": [
                {
                    "step_id": "S1",
                    "title": "打开首页",
                    "status": "done",
                    "actual_observation": "首页打开成功",
                },
                {
                    "step_id": "S2",
                    "title": "检查代理流量",
                    "status": "in_progress",
                    "notes": "正在查看 POST /demo",
                    "suggested_action": "list_requests()",
                },
            ],
        },
    )

    assert isinstance(result, Text)
    assert "SRC 状态" in result.plain
    assert "Demo Plan" in result.plain
    assert "SRC Reproducer" in result.plain
    assert "S2 检查代理流量" in result.plain
    assert "正在查看 POST /demo" in result.plain
    assert "list_requests()" not in result.plain
