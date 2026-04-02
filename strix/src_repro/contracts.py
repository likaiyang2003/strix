from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import uuid4


@dataclass
class SrcReproAnalysis:
    can_reproduce: bool = False
    reason: str = ""
    missing_info: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class SrcReproTask:
    report_text: str
    source_label: str
    mode: str = "src_reproduction"
    requested_root_skill: str = "src_repro_root"
    original_message: str = ""
    skip_analysis: bool = False
    execution_stage: str = "reproduction"


def _generate_bundle_id() -> str:
    return f"src-repro-{uuid4().hex[:10]}"


@dataclass
class SrcReproBundle:
    source_report: str
    source_label: str
    final_verdict: str
    analysis: SrcReproAnalysis | dict[str, object] | str | None = None
    reproduction_plan: str | None = None
    execution_trace: str | None = None
    bundle_id: str = field(default_factory=_generate_bundle_id)
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


__all__ = ["SrcReproAnalysis", "SrcReproBundle", "SrcReproTask"]
