"""Auditable calculation framework.

Every number the platform produces is a CalcNode: formula, inputs with
provenance, the substituted expression, intermediate child calculations, the
result, and a confidence roll-up. Pure — no I/O anywhere in app.domain.
"""
from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field


class Provenance(BaseModel):
    provider: str                       # 'FRED', 'sec_edgar', 'computed', 'assumption'
    source_url: str | None = None
    series: str | None = None           # e.g. FRED series id
    method: str | None = None           # for computed values
    as_of: str | None = None            # ISO date the value refers to
    editable: bool = False              # true for user-overridable assumptions


class CalcInput(BaseModel):
    name: str                           # "risk_free_rate"
    symbol: str                         # "Rf" — token used in the formula string
    value: Decimal
    unit: str = ""                      # "%", "USD mn", "x", "shares"
    source: Provenance | None = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)

    def formatted(self) -> str:
        if self.unit == "%":
            return f"{self.value * 100:.2f}%"
        return f"{self.value:,f}".rstrip("0").rstrip(".") or "0"


class CalcNode(BaseModel):
    key: str                            # "wacc.cost_of_equity"
    label: str                          # "Cost of Equity (CAPM)"
    formula: str                        # "Ke = Rf + β × ERP"
    inputs: list[CalcInput] = Field(default_factory=list)
    intermediates: list[CalcNode] = Field(default_factory=list)
    result: Decimal
    unit: str = ""
    substitution: str = ""
    explanation: str = ""
    assumptions: list[str] = Field(default_factory=list)
    method_confidence: float = Field(default=1.0, ge=0.0, le=1.0)

    def model_post_init(self, __context: object) -> None:
        if not self.substitution:
            self.substitution = self._substitute()

    def _substitute(self) -> str:
        """Replace each input's symbol in the formula with its formatted value.

        Longest symbols first so 'ERP' is replaced before 'E'. Only the
        right-hand side is substituted; the '<lhs> =' prefix is preserved.
        """
        lhs, sep, rhs = self.formula.partition("=")
        target = rhs if sep else self.formula
        for inp in sorted(self.inputs, key=lambda i: len(i.symbol), reverse=True):
            target = target.replace(inp.symbol, inp.formatted())
        result_str = (
            f"{self.result * 100:.2f}%" if self.unit == "%" else f"{self.result:,f}"
        )
        prefix = f"{lhs.strip()} = " if sep else ""
        return f"{prefix}{target.strip()} = {result_str}"

    @property
    def confidence(self) -> float:
        """Roll-up: the chain is only as strong as its weakest input."""
        parts = [i.confidence for i in self.inputs]
        parts += [n.confidence for n in self.intermediates]
        base = min(parts) if parts else 1.0
        return round(base * self.method_confidence, 4)

    def to_dict(self) -> dict:
        data = self.model_dump(mode="json")
        data["confidence"] = self.confidence
        data["intermediates"] = [n.to_dict() for n in self.intermediates]
        return data

    def find(self, key: str) -> CalcNode | None:
        if self.key == key:
            return self
        for child in self.intermediates:
            hit = child.find(key)
            if hit:
                return hit
        return None
