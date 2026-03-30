from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from strix.src_repro import SrcReproBundle, save_src_repro_bundle as persist_src_repro_bundle
from strix.tools.registry import register_tool


def _read_text_file(path: Path) -> str:
    read_attempts: tuple[str | None, ...] = ("utf-8", "utf-8-sig", None)
    last_error: UnicodeError | OSError | None = None

    for encoding in read_attempts:
        try:
            if encoding is None:
                return path.read_text()
            return path.read_text(encoding=encoding)
        except (UnicodeError, OSError) as exc:
            last_error = exc

    raise OSError(f"读取源报告失败: {last_error}") from last_error


@register_tool(sandbox_execution=False)
def load_src_report_source(
    source_label: str,
    max_chars: int = 12000,
) -> dict[str, Any]:
    normalized = (source_label or "").strip()
    if not normalized:
        return {
            "success": False,
            "message": "缺少 source_label，无法读取原始漏洞报告。",
        }

    if normalized == "inline":
        return {
            "success": False,
            "message": "当前 `/src` 输入来源为 inline，没有可回看的文件版原始报告。",
            "source_label": normalized,
        }

    path = Path(normalized)
    if not path.exists():
        return {
            "success": False,
            "message": f"原始漏洞报告文件不存在: {path}",
            "source_label": normalized,
        }
    if not path.is_file():
        return {
            "success": False,
            "message": f"原始漏洞报告路径不是文件: {path}",
            "source_label": normalized,
        }

    try:
        content = _read_text_file(path)
    except OSError as exc:
        return {
            "success": False,
            "message": str(exc),
            "source_label": normalized,
        }

    normalized_limit = max(1, int(max_chars))
    trimmed = content[:normalized_limit]
    return {
        "success": True,
        "message": "已读取原始漏洞报告文件。",
        "source_label": normalized,
        "source_path": str(path),
        "source_dir": str(path.parent),
        "source_name": path.name,
        "content": trimmed,
        "truncated": len(content) > normalized_limit,
        "total_chars": len(content),
        "returned_chars": len(trimmed),
    }


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
                "message": "当前 tracer 不可用，未保存 `/src` 产物",
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
            "message": f"保存 `/src` 产物失败：{e!s}",
        }
    else:
        return {
            "success": True,
            "message": "已保存 `/src` 复现产物",
            **saved,
        }
