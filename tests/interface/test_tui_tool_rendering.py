from __future__ import annotations

from rich.text import Text

from strix.interface.tui import StrixTUIApp


class _FakeRenderApp:
    _render_tool_content_simple = StrixTUIApp._render_tool_content_simple
    _render_streaming_tool = StrixTUIApp._render_streaming_tool
    _extract_widget_content = staticmethod(StrixTUIApp._extract_widget_content)

    def _render_error_details(self, text: Text, tool_name: str, args: dict[str, str]) -> Text:
        del tool_name, args
        return text


def test_render_tool_content_simple_supports_static_renderer_output() -> None:
    app = _FakeRenderApp()

    result = app._render_tool_content_simple(
        {
            "tool_name": "scan_start_info",
            "args": {
                "targets": [
                    {
                        "type": "web_application",
                        "details": {"target_url": "http://host.docker.internal"},
                        "original": "http://127.0.0.1",
                    }
                ]
            },
            "status": "completed",
            "result": {},
        }
    )

    assert isinstance(result, Text)
    assert "Starting penetration test" in result.plain
    assert "http://127.0.0.1" in result.plain


def test_render_streaming_tool_supports_static_renderer_output() -> None:
    app = _FakeRenderApp()

    result = app._render_streaming_tool(
        "scan_start_info",
        {
            "targets": [
                {
                    "type": "web_application",
                    "details": {"target_url": "http://host.docker.internal"},
                    "original": "http://127.0.0.1",
                }
            ]
        },
        True,
    )

    assert isinstance(result, Text)
    assert "Starting penetration test" in result.plain
