import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.valuation.base import ValuationOutcome
from app.models.valuation import AssumptionSetRow, ValuationRun


class ValuationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def save_assumptions(self, company_id: uuid.UUID, name: str,
                               assumptions: dict, derivation: dict | None) -> AssumptionSetRow:
        row = AssumptionSetRow(company_id=company_id, name=name,
                               assumptions=assumptions, derivation=derivation)
        self.session.add(row)
        await self.session.flush()
        return row

    async def get_assumptions(self, set_id: uuid.UUID) -> AssumptionSetRow | None:
        return await self.session.get(AssumptionSetRow, set_id)

    async def save_run(self, company_id: uuid.UUID, outcome: ValuationOutcome,
                       price: Decimal | None,
                       assumption_set_id: uuid.UUID | None,
                       engine_version: str) -> ValuationRun:
        upside = None
        if (price and price > 0 and outcome.fair_value_per_share
                and outcome.fair_value_per_share > 0):
            upside = float((outcome.fair_value_per_share / price - 1) * 100)
        run = ValuationRun(
            company_id=company_id, model=outcome.model, status=outcome.status,
            not_applicable_reason=outcome.not_applicable_reason,
            fair_value_per_share=outcome.fair_value_per_share,
            currency=outcome.currency, price_at_run=price, upside_pct=upside,
            low=outcome.low, high=outcome.high, confidence=outcome.confidence,
            assumption_set_id=assumption_set_id, outputs=outcome.outputs,
            trace=outcome.trace.to_dict() if outcome.trace else None,
            engine_version=engine_version,
        )
        self.session.add(run)
        await self.session.flush()
        return run

    async def get_run(self, run_id: uuid.UUID) -> ValuationRun | None:
        return await self.session.get(ValuationRun, run_id)

    async def latest_runs(self, company_id: uuid.UUID) -> list[ValuationRun]:
        """Most recent run per model."""
        stmt = (select(ValuationRun)
                .where(ValuationRun.company_id == company_id)
                .order_by(ValuationRun.created_at.desc()))
        rows = (await self.session.execute(stmt)).scalars().all()
        seen: dict[str, ValuationRun] = {}
        for r in rows:
            seen.setdefault(r.model, r)
        return list(seen.values())
