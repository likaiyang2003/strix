import json
from pathlib import Path

from strix.src_repro import SrcReproAnalysis
from strix.src_repro.contracts import SrcReproBundle
from strix.src_repro.output import save_src_repro_bundle


class _DummyTracer:
    def __init__(self, run_dir: Path) -> None:
        self._run_dir = run_dir

    def get_run_dir(self) -> Path:
        return self._run_dir


def test_save_src_repro_bundle_writes_expected_files(tmp_path: Path) -> None:
    tracer = _DummyTracer(tmp_path / "strix_runs" / "demo-run")
    bundle = SrcReproBundle(
        source_report="target=https://demo.local path=/admin",
        source_label="inline",
        analysis=SrcReproAnalysis(
            can_reproduce=True,
            reason="Enough details",
            missing_info=[],
        ),
        reproduction_plan="## Detailed Reproduction Steps\n1. Open page",
        execution_trace="## 4) Final Verdict\n- verdict: reproducible",
        final_verdict="/src execution finished.\nFinal verdict: reproducible",
        bundle_id="src-repro-fixed",
    )

    saved = save_src_repro_bundle(tracer, bundle)

    output_dir = Path(saved["output_dir"])
    assert output_dir.exists()
    assert (output_dir / "00_source_report.txt").read_text(encoding="utf-8") == bundle.source_report
    assert json.loads((output_dir / "01_analysis.json").read_text(encoding="utf-8")) == {
        "can_reproduce": True,
        "reason": "Enough details",
        "missing_info": [],
    }
    assert "Detailed Reproduction Steps" in (output_dir / "02_reproduction_plan.txt").read_text(
        encoding="utf-8"
    )
    assert "reproducible" in (output_dir / "03_execution_trace.md").read_text(encoding="utf-8")
    assert "Final verdict: reproducible" in (output_dir / "04_final_verdict.md").read_text(
        encoding="utf-8"
    )
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["bundle_id"] == "src-repro-fixed"
    assert manifest["final_verdict"] == "reproducible"


def test_save_src_repro_bundle_requires_tracer() -> None:
    bundle = SrcReproBundle(
        source_report="report",
        source_label="inline",
        final_verdict="blocked",
    )

    try:
        save_src_repro_bundle(None, bundle)
    except ValueError as exc:
        assert "get_run_dir" in str(exc)
    else:  # pragma: no cover - defensive
        raise AssertionError("Expected ValueError when tracer is missing")


def test_save_src_repro_bundle_supports_verify_verdict_labels(tmp_path: Path) -> None:
    tracer = _DummyTracer(tmp_path / "strix_runs" / "demo-run")
    bundle = SrcReproBundle(
        source_report="target=https://demo.local path=/admin",
        source_label="inline",
        final_verdict="verdict: fixed\n修复已验证",
        bundle_id="src-verify-fixed",
    )

    saved = save_src_repro_bundle(tracer, bundle)

    manifest = json.loads(Path(saved["files"]["manifest"]).read_text(encoding="utf-8"))
    assert manifest["bundle_id"] == "src-verify-fixed"
    assert manifest["final_verdict"] == "fixed"
