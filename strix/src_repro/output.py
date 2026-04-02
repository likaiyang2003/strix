from __future__ import annotations

import json
import re
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from .contracts import SrcReproAnalysis, SrcReproBundle
from .result_parser import parse_analysis

_VERDICT_LINE_PATTERN = re.compile(r"^\s*(?:-\s*)?verdict\s*:\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE)


def save_src_repro_bundle(
    tracer: Any,
    bundle: SrcReproBundle,
) -> dict[str, Any]:
    if tracer is None or not hasattr(tracer, "get_run_dir"):
        raise ValueError("A tracer with get_run_dir() is required to persist /src outputs.")

    bundle_dir = _get_src_repro_dir(tracer, bundle.bundle_id)
    bundle_dir.mkdir(parents=True, exist_ok=True)

    analysis_payload = _normalize_analysis(bundle.analysis)
    reproduction_plan = (bundle.reproduction_plan or "").strip()
    execution_trace = (bundle.execution_trace or "").strip()
    final_verdict = (bundle.final_verdict or "").strip()

    written_files = {
        "source_report": _write_text(bundle_dir / "00_source_report.txt", bundle.source_report.strip()),
        "analysis": _write_json(bundle_dir / "01_analysis.json", analysis_payload),
        "reproduction_plan": _write_text(bundle_dir / "02_reproduction_plan.txt", reproduction_plan),
        "execution_trace": _write_text(bundle_dir / "03_execution_trace.md", execution_trace),
        "final_verdict": _write_text(bundle_dir / "04_final_verdict.md", final_verdict),
    }

    manifest = {
        "bundle_id": bundle.bundle_id,
        "created_at": bundle.created_at,
        "source_label": bundle.source_label,
        "final_verdict": _extract_verdict_label(final_verdict),
        "files": {name: str(path.relative_to(bundle_dir)) for name, path in written_files.items()},
    }
    manifest_path = _write_json(bundle_dir / "manifest.json", manifest)

    return {
        "bundle_id": bundle.bundle_id,
        "output_dir": str(bundle_dir),
        "files": {
            **{name: str(path) for name, path in written_files.items()},
            "manifest": str(manifest_path),
        },
        "manifest": manifest,
    }


def _get_src_repro_dir(tracer: Any, bundle_id: str) -> Path:
    run_dir = Path(tracer.get_run_dir())
    return run_dir / "src_repro" / bundle_id


def _normalize_analysis(
    analysis: SrcReproAnalysis | dict[str, object] | str | None,
) -> dict[str, Any]:
    if analysis is None:
        return {}

    if isinstance(analysis, SrcReproAnalysis):
        return asdict(analysis)

    if isinstance(analysis, dict):
        return dict(analysis)

    if is_dataclass(analysis):
        return asdict(analysis)

    if isinstance(analysis, str):
        stripped = analysis.strip()
        if not stripped:
            return {}

        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError:
            parsed = parse_analysis(stripped)
            return asdict(parsed)
        else:
            if isinstance(payload, dict):
                return payload
            return {"raw_analysis": stripped}

    return {"raw_analysis": str(analysis)}


def _write_text(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    return path


def _write_json(path: Path, content: dict[str, Any]) -> Path:
    path.write_text(json.dumps(content, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _extract_verdict_label(final_verdict: str) -> str:
    match = _VERDICT_LINE_PATTERN.search(final_verdict)
    if match:
        normalized = _normalize_verdict_label(match.group(1))
        if normalized is not None:
            return normalized

    lowered = final_verdict.lower()
    if "still reproducible" in lowered:
        return "still reproducible"
    if "仍可复现" in final_verdict:
        return "still reproducible"
    if "fixed" in lowered:
        return "fixed"
    if "修复已验证" in final_verdict or "已修复" in final_verdict:
        return "fixed"
    if "not reproducible" in lowered:
        return "not reproducible"
    if "不可复现" in final_verdict:
        return "not reproducible"
    if "reproducible" in lowered:
        return "reproducible"
    if "可复现" in final_verdict:
        return "reproducible"
    if "blocked" in lowered:
        return "blocked"
    if "阻塞" in final_verdict:
        return "blocked"
    return "unknown"


def _normalize_verdict_label(value: str) -> str | None:
    normalized = value.strip().lower()
    if normalized in {
        "still reproducible",
        "fixed",
        "not reproducible",
        "reproducible",
        "blocked",
    }:
        return normalized
    return None


__all__ = ["save_src_repro_bundle", "_get_src_repro_dir"]
