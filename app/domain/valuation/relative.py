"""Relative valuation.

`historical_multiples`: mean-reversion to the company's own multiple history
(always computable from ingested data). `peer_comps`: cross-sectional peer
multiples — used when peer fundamentals exist in the local universe.
"""
from decimal import Decimal
from statistics import median

from pydantic import BaseModel

from app.domain.calc.trace import CalcInput, CalcNode
from app.domain.statements import derived
from app.domain.statements.history import FinancialHistory
from app.domain.valuation.base import AssumptionSet, ValuationOutcome

Q2 = Decimal("0.01")
Q4 = Decimal("0.0001")


class YearEndPrice(BaseModel):
    fiscal_year: int
    price: Decimal


def historical_multiples(history: FinancialHistory, a: AssumptionSet,
                         price: Decimal | None,
                         year_end_prices: list[YearEndPrice]) -> ValuationOutcome:
    model = "multiples"
    currency = history.currency
    if price is None:
        return ValuationOutcome.na(model, "no current price", currency)
    price_by_fy = {p.fiscal_year: p.price for p in year_end_prices}

    pe_hist: list[Decimal] = []
    pb_hist: list[Decimal] = []
    ps_hist: list[Decimal] = []
    for p in history.annual:
        px = price_by_fy.get(p.fiscal_year)
        sh = p.get("shares_diluted")
        if px is None or not sh:
            continue
        ni, eq, rev = p.get("net_income"), p.get("total_equity"), p.get("revenue")
        if ni and ni > 0:
            pe_hist.append(px / (ni / sh))
        if eq and eq > 0:
            pb_hist.append(px / (eq / sh))
        if rev and rev > 0:
            ps_hist.append(px / (rev / sh))

    latest = history.latest
    if latest is None or a.shares_diluted <= 0:
        return ValuationOutcome.na(model, "no fundamentals ingested", currency)

    implied: list[tuple[str, Decimal, Decimal, Decimal]] = []  # name, mult, metric/share, value
    ni, eq, rev = latest.get("net_income"), latest.get("total_equity"), latest.get("revenue")
    if len(pe_hist) >= 3 and ni and ni > 0:
        m = Decimal(str(round(float(median(pe_hist)), 4)))
        eps = ni / a.shares_diluted
        implied.append(("P/E", m, eps, m * eps))
    if len(pb_hist) >= 3 and eq and eq > 0:
        m = Decimal(str(round(float(median(pb_hist)), 4)))
        bvps = eq / a.shares_diluted
        implied.append(("P/B", m, bvps, m * bvps))
    if len(ps_hist) >= 3 and rev and rev > 0:
        m = Decimal(str(round(float(median(ps_hist)), 4)))
        sps = rev / a.shares_diluted
        implied.append(("P/S", m, sps, m * sps))

    if not implied:
        return ValuationOutcome.na(
            model, "needs ≥3 years of overlapping price + fundamentals history "
                   "to build multiple history", currency)

    values = [v for _, _, _, v in implied]
    fair = Decimal(str(round(float(median(values)), 2)))
    node = CalcNode(
        key="multiples.historical", label="Historical Multiples (mean reversion)",
        formula="Value = median over multiples of (historical-median multiple × current metric)",
        inputs=[CalcInput(name=f"implied_{n.lower().replace('/', '')}", symbol=n,
                          value=v.quantize(Q2)) for n, _, _, v in implied],
        result=fair, unit=f"{currency}/share",
        explanation="Assumes reversion to the company's own historical valuation; "
                    "silent on whether history itself was fairly priced — treat as "
                    "a cross-check, not a primary model.",
        method_confidence=0.65,
    )
    return ValuationOutcome(
        model=model, fair_value_per_share=fair, currency=currency,
        low=min(values).quantize(Q2), high=max(values).quantize(Q2),
        confidence=node.confidence,
        outputs={"multiples": [
            {"name": n, "historical_median": str(m.quantize(Q4)),
             "current_metric_per_share": str(x.quantize(Q4)),
             "implied_value": str(v.quantize(Q2))} for n, m, x, v in implied]},
        trace=node,
    )


class PeerMetrics(BaseModel):
    name: str
    pe: Decimal | None = None
    ev_ebitda: Decimal | None = None
    pb: Decimal | None = None
    ps: Decimal | None = None


def peer_comps(history: FinancialHistory, a: AssumptionSet,
               price: Decimal | None, peers: list[PeerMetrics]) -> ValuationOutcome:
    model = "comps"
    currency = history.currency
    latest = history.latest
    if latest is None or a.shares_diluted <= 0:
        return ValuationOutcome.na(model, "no fundamentals ingested", currency)
    if len(peers) < 3:
        return ValuationOutcome.na(
            model, f"needs ≥3 peers with metrics in the local universe "
                   f"(have {len(peers)}) — ingest peers first", currency)

    def med(vals: list[Decimal]) -> Decimal | None:
        clean = sorted(v for v in vals if v is not None and v > 0)
        if len(clean) < 3:
            return None
        # IQR outlier trim
        q1, q3 = clean[len(clean) // 4], clean[(3 * len(clean)) // 4]
        iqr = q3 - q1
        trimmed = [v for v in clean if q1 - Decimal("1.5") * iqr <= v <= q3 + Decimal("1.5") * iqr]
        return Decimal(str(round(float(median(trimmed or clean)), 4)))

    implied = []
    ni, eq, rev = latest.get("net_income"), latest.get("total_equity"), latest.get("revenue")
    pe_m = med([p.pe for p in peers if p.pe])
    if pe_m and ni and ni > 0:
        implied.append(("peer P/E", pe_m, pe_m * ni / a.shares_diluted))
    pb_m = med([p.pb for p in peers if p.pb])
    if pb_m and eq and eq > 0:
        implied.append(("peer P/B", pb_m, pb_m * eq / a.shares_diluted))
    ps_m = med([p.ps for p in peers if p.ps])
    if ps_m and rev and rev > 0:
        implied.append(("peer P/S", ps_m, ps_m * rev / a.shares_diluted))
    ev_m = med([p.ev_ebitda for p in peers if p.ev_ebitda])
    eb = derived.ebitda(latest)
    if ev_m and eb and eb.result > 0:
        equity_val = ev_m * eb.result - a.net_debt
        implied.append(("peer EV/EBITDA", ev_m, equity_val / a.shares_diluted))

    if not implied:
        return ValuationOutcome.na(model, "no usable peer multiples", currency)
    values = [v for _, _, v in implied]
    fair = Decimal(str(round(float(median(values)), 2)))
    node = CalcNode(
        key="comps", label="Comparable Company Analysis",
        formula="Value = median of (peer-median multiple × target metric)",
        inputs=[CalcInput(name=n.replace(" ", "_"), symbol=n, value=v.quantize(Q2))
                for n, _, v in implied],
        result=fair, unit=f"{currency}/share",
        explanation=f"{len(peers)} peers, IQR-trimmed medians.",
        method_confidence=0.75,
    )
    return ValuationOutcome(
        model=model, fair_value_per_share=fair, currency=currency,
        low=min(values).quantize(Q2), high=max(values).quantize(Q2),
        confidence=node.confidence,
        outputs={"peer_count": len(peers),
                 "implied": [{"basis": n, "multiple": str(m), "value": str(v.quantize(Q2))}
                             for n, m, v in implied]},
        trace=node,
    )
