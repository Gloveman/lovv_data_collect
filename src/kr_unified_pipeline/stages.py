"""Pipeline stage protocol and canonical stage ordering.

Defines the PipelineStage Protocol that all pipeline stages must implement,
and the canonical stage execution order for the unified preprocessing pipeline.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from kr_unified_pipeline.models import PipelineContext


class PipelineStage(Protocol):
    """통합 파이프라인의 개별 실행 단계.

    Each stage receives a PipelineContext, performs its processing,
    and returns an updated PipelineContext with accumulated results.
    """

    @property
    def name(self) -> str:
        """Stage identifier used for logging and configuration."""
        ...

    def execute(self, context: PipelineContext) -> PipelineContext:
        """컨텍스트를 입력받아 갱신된 컨텍스트를 반환한다."""
        ...


# Canonical stage execution order.
# When multiple stages are specified, the orchestrator executes them
# in this defined sequential order regardless of the order provided by the user.
STAGE_ORDER: list[str] = [
    "wikipedia",
    "tourapi-region",
    "tourapi-detail",
    "load",
    "vector-build",
]
