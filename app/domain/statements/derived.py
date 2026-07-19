"""Derived fundamentals — each returns a CalcNode (full audit trace) or None
when required inputs are missing. Pure functions."""
from decimal import Decimal

from app.domain.calc.trace import CalcInput, CalcNode
from app.domain.statements.history import PeriodFinancials

ZERO = Decimal(0)
ONE = Decimal(1)


def _inp(name: str, symbol: str, value: Decimal, unit: str = "") -> CalcInput:
    return CalcInput(name=name, symbol=symbol, value=value, unit=unit)


def ebitda(p: PeriodFinancials) -> CalcNode | None:
    vals = p.require("operating_income", "depreciation_amortization")
    if vals is None:
        return None
    ebit, da = vals
    return CalcNode(
        key="derived.ebitda", label="EBITDA", formula="EBITDA = EBIT + D&A",
        inputs=[_inp("operating_income", "EBIT", ebit),
                _inp("depreciation_amortization", "D&A", da)],
        result=ebit + da, unit=p.currency,
        explanation="Operating income before depreciation and amortization.",
    )


def effective_tax_rate(p: PeriodFinancials) -> CalcNode | None:
    vals = p.require("income_tax", "pretax_income")
    if vals is None or vals[1] == 0:
        return None
    tax, pretax = vals
    rate = tax / pretax
    clamped = min(max(rate, ZERO), Decimal("0.40"))
    node = CalcNode(
        key="derived.tax_rate", label="Effective Tax Rate",
        formula="t = Income Tax / Pre-tax Income",
        inputs=[_inp("income_tax", "Income Tax", tax),
                _inp("pretax_income", "Pre-tax Income", pretax)],
        result=clamped.quantize(Decimal("0.0001")), unit="%",
        explanation="Effective rate, clamped to [0%, 40%] to guard against "
                    "one-off items distorting forward assumptions.",
    )
    if clamped != rate:
        node.assumptions.append(
            f"raw rate {rate:.2%} clamped to {clamped:.2%} (one-off distortion guard)"
        )
    return node


def nopat(p: PeriodFinancials) -> CalcNode | None:
    ebit = p.get("operating_income")
    tax_node = effective_tax_rate(p)
    if ebit is None or tax_node is None:
        return None
    t = tax_node.result
    return CalcNode(
        key="derived.nopat", label="NOPAT", formula="NOPAT = EBIT × (1 − t)",
        inputs=[_inp("operating_income", "EBIT", ebit), _inp("tax_rate", "t", t, "%")],
        intermediates=[tax_node],
        result=(ebit * (ONE - t)).quantize(Decimal("0.01")), unit=p.currency,
        explanation="After-tax operating profit available to all capital providers.",
    )


def working_capital(p: PeriodFinancials) -> CalcNode | None:
    vals = p.require("current_assets", "current_liabilities")
    if vals is None:
        return None
    ca, cl = vals
    return CalcNode(
        key="derived.working_capital", label="Working Capital",
        formula="WC = Current Assets − Current Liabilities",
        inputs=[_inp("current_assets", "Current Assets", ca),
                _inp("current_liabilities", "Current Liabilities", cl)],
        result=ca - cl, unit=p.currency,
    )


def net_debt(p: PeriodFinancials) -> CalcNode | None:
    debt = p.total_debt
    cash = p.get("cash_and_equivalents")
    if debt is None or cash is None:
        return None
    sti = p.get("short_term_investments") or ZERO
    return CalcNode(
        key="derived.net_debt", label="Net Debt",
        formula="Net Debt = Total Debt − Cash − ST Investments",
        inputs=[_inp("total_debt", "Total Debt", debt),
                _inp("cash_and_equivalents", "Cash", cash),
                _inp("short_term_investments", "ST Investments", sti)],
        result=debt - cash - sti, unit=p.currency,
        explanation="Debt net of cash and liquid investments; used in the "
                    "EV-to-equity bridge.",
    )


def invested_capital(p: PeriodFinancials) -> CalcNode | None:
    equity = p.get("total_equity")
    debt = p.total_debt
    if equity is None or debt is None:
        return None
    cash = p.get("cash_and_equivalents") or ZERO
    return CalcNode(
        key="derived.invested_capital", label="Invested Capital",
        formula="IC = Total Equity + Total Debt − Cash",
        inputs=[_inp("total_equity", "Total Equity", equity),
                _inp("total_debt", "Total Debt", debt),
                _inp("cash_and_equivalents", "Cash", cash)],
        result=equity + debt - cash, unit=p.currency,
        explanation="Financing-side invested capital (operating cash netted out).",
    )


def fcff(p: PeriodFinancials) -> CalcNode | None:
    """FCFF = EBIT(1−t) + D&A − CapEx − ΔNWC (ΔNWC from the cash-flow statement,
    sign convention: positive change_in_working_capital = cash inflow)."""
    nopat_node = nopat(p)
    vals = p.require("depreciation_amortization", "capex")
    if nopat_node is None or vals is None:
        return None
    da, capex = vals
    dwc = p.get("change_in_working_capital") or ZERO
    result = nopat_node.result + da - capex + dwc
    node = CalcNode(
        key="derived.fcff", label="Free Cash Flow to Firm",
        formula="FCFF = NOPAT + D&A − CapEx + ΔWC(cash)",
        inputs=[_inp("nopat", "NOPAT", nopat_node.result),
                _inp("depreciation_amortization", "D&A", da),
                _inp("capex", "CapEx", capex),
                _inp("change_in_working_capital", "ΔWC(cash)", dwc)],
        intermediates=[nopat_node],
        result=result.quantize(Decimal("0.01")), unit=p.currency,
        explanation="Unlevered free cash flow: cash available to all capital "
                    "providers after reinvestment.",
    )
    if p.get("change_in_working_capital") is None:
        node.assumptions.append("ΔWC unavailable — assumed 0 for this period")
    return node


def fcfe(p: PeriodFinancials) -> CalcNode | None:
    """FCFE = FCFF − Interest×(1−t); net borrowing treated as 0 when debt
    issuance/repayment data is absent (stated in assumptions)."""
    fcff_node = fcff(p)
    tax_node = effective_tax_rate(p)
    if fcff_node is None or tax_node is None:
        return None
    interest = p.get("interest_expense") or ZERO
    t = tax_node.result
    result = fcff_node.result - interest * (ONE - t)
    node = CalcNode(
        key="derived.fcfe", label="Free Cash Flow to Equity",
        formula="FCFE = FCFF − Interest × (1 − t) + Net Borrowing",
        inputs=[_inp("fcff", "FCFF", fcff_node.result),
                _inp("interest_expense", "Interest", interest),
                _inp("tax_rate", "t", t, "%")],
        intermediates=[fcff_node],
        result=result.quantize(Decimal("0.01")), unit=p.currency,
        assumptions=["net borrowing assumed 0 (constant debt policy)"],
    )
    if p.get("interest_expense") is None:
        node.assumptions.append("interest expense unavailable — assumed 0")
    return node


def free_cash_flow(p: PeriodFinancials) -> CalcNode | None:
    """Simple FCF = OCF − CapEx (the equity analyst convention)."""
    vals = p.require("operating_cash_flow", "capex")
    if vals is None:
        return None
    ocf, capex = vals
    return CalcNode(
        key="derived.fcf", label="Free Cash Flow",
        formula="FCF = Operating Cash Flow − CapEx",
        inputs=[_inp("operating_cash_flow", "OCF", ocf), _inp("capex", "CapEx", capex)],
        result=ocf - capex, unit=p.currency,
    )
