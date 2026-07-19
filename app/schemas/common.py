"""Shared response envelope: {"data": ..., "meta": {...}}."""
from typing import Any

from pydantic import BaseModel, Field

from app.domain.calc.trace import CalcInput, CalcNode, Provenance  # re-export

__all__ = ["Provenance", "CalcInput", "CalcNode", "Meta", "envelope"]


class Meta(BaseModel):
    sources: list[str] = Field(default_factory=list)
    freshness: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


def envelope(data: Any, *, sources: list[str] | None = None,
             freshness: dict[str, Any] | None = None,
             warnings: list[str] | None = None) -> dict[str, Any]:
    return {
        "data": data,
        "meta": Meta(
            sources=sources or [],
            freshness=freshness or {},
            warnings=warnings or [],
        ).model_dump(),
    }
