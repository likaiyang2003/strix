from pathlib import Path

from strix.tools.src_repro import src_repro_actions


class _DummyTracer:
    def __init__(self, run_dir: Path) -> None:
        self._run_dir = run_dir

    def get_run_dir(self) -> Path:
        return self._run_dir


def test_save_src_repro_bundle_tool_persists_bundle(monkeypatch, tmp_path: Path) -> None:
    tracer = _DummyTracer(tmp_path / "strix_runs" / "demo-run")

    monkeypatch.setattr(
        "strix.telemetry.tracer.get_global_tracer",
        lambda: tracer,
    )

    result = src_repro_actions.save_src_repro_bundle(
        source_report="target=https://demo.local path=/admin",
        analysis_json='{"can_reproduce": true, "reason": "Enough details", "missing_info": []}',
        reproduction_plan="## Detailed Reproduction Steps\n1. Open page",
        execution_trace="## 4) Final Verdict\n- verdict: reproducible",
        final_verdict="/src execution finished.\nFinal verdict: reproducible",
        source_label="inline",
        bundle_id="src-repro-tool",
    )

    assert result["success"] is True
    assert Path(result["output_dir"]).exists()
    assert Path(result["files"]["manifest"]).exists()


def test_save_src_repro_bundle_tool_returns_error_without_tracer(monkeypatch) -> None:
    monkeypatch.setattr(
        "strix.telemetry.tracer.get_global_tracer",
        lambda: None,
    )

    result = src_repro_actions.save_src_repro_bundle(
        source_report="report",
        final_verdict="blocked",
    )

    assert result["success"] is False
    assert "tracer" in result["message"].lower()


def test_load_src_report_source_reads_file_backed_report(tmp_path: Path) -> None:
    report_path = tmp_path / "demo-report.md"
    report_path.write_text("line1\nline2\nline3", encoding="utf-8")

    result = src_repro_actions.load_src_report_source(str(report_path), max_chars=20)

    assert result["success"] is True
    assert result["source_path"] == str(report_path)
    assert result["source_dir"] == str(tmp_path)
    assert result["source_name"] == "demo-report.md"
    assert result["content"] == "line1\nline2\nline3"
    assert result["truncated"] is False


def test_load_src_report_source_rejects_inline_source() -> None:
    result = src_repro_actions.load_src_report_source("inline")

    assert result["success"] is False
    assert "inline" in result["message"]
