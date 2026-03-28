from __future__ import annotations

import json
from typing import Any

from strix.src_repro import SrcReproBundle, save_src_repro_bundle as persist_src_repro_bundle
from strix.tools.registry import register_tool


@register_tool(sandbox_execution=False)
def save_src_repro_bundle(
    source_report: str,
    analysis_json: str | None = None,
    reproduction_plan: str | None = None,
    execution_trace: str | None = None,
    final_verdict: str | None = None,
    source_label: str | None = None,
    bundle_id: str | None = None,
) -> dict[str, Any]:
    try:
        from strix.telemetry.tracer import get_global_tracer

        tracer = get_global_tracer()
        if tracer is None:
            return {
                "success": False,
                "message": "Current tracer not available - /src bundle not stored",
            }

        analysis_payload: dict[str, Any] | str | None
        if analysis_json and analysis_json.strip():
            try:
                parsed = json.loads(analysis_json)
            except json.JSONDecodeError:
                analysis_payload = analysis_json
            else:
                analysis_payload = parsed if isinstance(parsed, dict) else analysis_json
        else:
            analysis_payload = None

        bundle_kwargs = {
            "source_report": source_report,
            "source_label": (source_label or "inline").strip() or "inline",
            "analysis": analysis_payload,
            "reproduction_plan": reproduction_plan,
            "execution_trace": execution_trace,
            "final_verdict": (final_verdict or "").strip(),
        }
        if bundle_id and bundle_id.strip():
            bundle_kwargs["bundle_id"] = bundle_id.strip()

        bundle = SrcReproBundle(
            **bundle_kwargs,
        )

        saved = persist_src_repro_bundle(tracer, bundle)
    except Exception as e:  # noqa: BLE001
        return {
            "success": False,
            "message": f"Failed to save /src reproduction bundle: {e!s}",
        }
    else:
        return {
            "success": True,
            "message": "Saved /src reproduction bundle",
            **saved,
        }
