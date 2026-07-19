"""Financial ratio engine. Every ratio is a CalcNode; ratios whose inputs are
missing are omitted (never faked). Market ratios additionally take price data."""
from decimal import Decimal

from pydantic import BaseModel

from app.domain.calc.trace import CalcInput, CalcNode
from app.domain.statements import derived
from app.domain.statements.history import FinancialHistory, PeriodFinancials

ZERO = Decimal(0)
Q4 = Decimal("0.0001")


class MarketInputs(BaseModel):
    price: Decimal
    shares: Decimal            # diluted
    market_cap: Decimal


def _node(key: str, label: str, formula: str,
          inputs: list[tuple[str, str, Decimal, str]],
          result: Decimal, unit: str = "x", explanation: str = "") -> CalcNode:
    return CalcNode(
        key=key, label=label, formula=formula,
        inputs=[CalcInput(name=n, symbol=s, value=v, unit=u)
                for n, s, v, u in inputs],
        result=result.quantize(Q4), unit=unit, explanation=explanation,
    )


def _safe_div(a: Decimal | None, b: Decimal | None) -> Decimal | None:
    if a is None or b is None or b == 0:
        return None
    return a / b


def profitability(p: PeriodFinancials, prior: PeriodFinancials | None) -> dict[str, CalcNode]:
    out: dict[str, CalcNode] = {}
    rev = p.get("revenue")

    for key, label, num_key, sym in [
        ("gross_margin", "Gross Margin", "gross_profit", "Gross Profit"),
        ("operating_margin", "Operating Margin", "operating_income", "EBIT"),
        ("net_margin", "Net Margin", "net_income", "Net Income"),
    ]:
        num = p.get(num_key)
        r = _safe_div(num, rev)
        if r is not None:
            out[key] = _node(f"ratio.{key}", label, f"{label} = {sym} / Revenue",
                             [(num_key, sym, num, ""), ("revenue", "Revenue", rev, "")],
                             r, "%")

    ebitda_node = derived.ebitda(p)
    if ebitda_node and rev:
        r = ebitda_node.result / rev
        n = _node("ratio.ebitda_margin", "EBITDA Margin",
                  "EBITDA Margin = EBITDA / Revenue",
                  [("ebitda", "EBITDA", ebitda_node.result, ""),
                   ("revenue", "Revenue", rev, "")], r, "%")
        n.intermediates.append(ebitda_node)
        out["ebitda_margin"] = n

    ni, equity, assets = p.get("net_income"), p.get("total_equity"), p.get("total_assets")
    r = _safe_div(ni, equity)
    if r is not None:
        out["roe"] = _node("ratio.roe", "Return on Equity",
                           "ROE = Net Income / Total Equity",
                           [("net_income", "Net Income", ni, ""),
                            ("total_equity", "Total Equity", equity, "")], r, "%")
    r = _safe_div(ni, assets)
    if r is not None:
        out["roa"] = _node("ratio.roa", "Return on Assets",
                           "ROA = Net Income / Total Assets",
                           [("net_income", "Net Income", ni, ""),
                            ("total_assets", "Total Assets", assets, "")], r, "%")

    nopat_node, ic_node = derived.nopat(p), derived.invested_capital(p)
    if nopat_node and ic_node and ic_node.result != 0:
        r = nopat_node.result / ic_node.result
        n = _node("ratio.roic", "Return on Invested Capital",
                  "ROIC = NOPAT / IC",
                  [("nopat", "NOPAT", nopat_node.result, ""),
                   ("invested_capital", "IC", ic_node.result, "")], r, "%",
                  "The moat metric: spread over WACC indicates value creation.")
        n.intermediates += [nopat_node, ic_node]
        out["roic"] = n

    fcf_node = derived.free_cash_flow(p)
    if fcf_node and rev:
        out["fcf_margin"] = _node("ratio.fcf_margin", "FCF Margin",
                                  "FCF Margin = FCF / Revenue",
                                  [("fcf", "FCF", fcf_node.result, ""),
                                   ("revenue", "Revenue", rev, "")],
                                  fcf_node.result / rev, "%")
    return out


def liquidity(p: PeriodFinancials) -> dict[str, CalcNode]:
    out: dict[str, CalcNode] = {}
    ca, cl = p.get("current_assets"), p.get("current_liabilities")
    cash = p.get("cash_and_equivalents")
    inv = p.get("inventory")
    r = _safe_div(ca, cl)
    if r is not None:
        out["current_ratio"] = _node("ratio.current", "Current Ratio",
                                     "Current Ratio = Current Assets / Current Liabilities",
                                     [("current_assets", "CA", ca, ""),
                                      ("current_liabilities", "CL", cl, "")], r)
    if ca is not None and cl and inv is not None:
        out["quick_ratio"] = _node("ratio.quick", "Quick Ratio",
                                   "Quick Ratio = (CA − Inventory) / CL",
                                   [("current_assets", "CA", ca, ""),
                                    ("inventory", "Inventory", inv, ""),
                                    ("current_liabilities", "CL", cl, "")],
                                   (ca - inv) / cl)
    r = _safe_div(cash, cl)
    if r is not None:
        out["cash_ratio"] = _node("ratio.cash", "Cash Ratio",
                                  "Cash Ratio = Cash / CL",
                                  [("cash_and_equivalents", "Cash", cash, ""),
                                   ("current_liabilities", "CL", cl, "")], r)
    return out


def leverage(p: PeriodFinancials) -> dict[str, CalcNode]:
    out: dict[str, CalcNode] = {}
    debt, equity = p.total_debt, p.get("total_equity")
    r = _safe_div(debt, equity)
    if r is not None:
        out["debt_to_equity"] = _node("ratio.de", "Debt / Equity",
                                      "D/E = Total Debt / Total Equity",
                                      [("total_debt", "Debt", debt, ""),
                                       ("total_equity", "Equity", equity, "")], r)
    nd, eb = derived.net_debt(p), derived.ebitda(p)
    if nd and eb and eb.result != 0:
        n = _node("ratio.net_debt_ebitda", "Net Debt / EBITDA",
                  "Net Debt / EBITDA",
                  [("net_debt", "Net Debt", nd.result, ""),
                   ("ebitda", "EBITDA", eb.result, "")], nd.result / eb.result)
        n.intermediates += [nd, eb]
        out["net_debt_to_ebitda"] = n
    ebit, interest = p.get("operating_income"), p.get("interest_expense")
    r = _safe_div(ebit, interest)
    if r is not None and interest and interest > 0:
        out["interest_coverage"] = _node("ratio.icov", "Interest Coverage",
                                         "Coverage = EBIT / Interest Expense",
                                         [("operating_income", "EBIT", ebit, ""),
                                          ("interest_expense", "Interest", interest, "")], r)
    liab, assets = p.get("total_liabilities"), p.get("total_assets")
    r = _safe_div(liab, assets)
    if r is not None:
        out["liabilities_to_assets"] = _node("ratio.la", "Liabilities / Assets",
                                             "L/A = Total Liabilities / Total Assets",
                                             [("total_liabilities", "L", liab, ""),
                                              ("total_assets", "A", assets, "")], r, "%")
    return out


def efficiency(p: PeriodFinancials) -> dict[str, CalcNode]:
    out: dict[str, CalcNode] = {}
    rev, assets = p.get("revenue"), p.get("total_assets")
    cogs = p.get("cost_of_revenue")
    r = _safe_div(rev, assets)
    if r is not None:
        out["asset_turnover"] = _node("ratio.at", "Asset Turnover",
                                      "Turnover = Revenue / Total Assets",
                                      [("revenue", "Revenue", rev, ""),
                                       ("total_assets", "Assets", assets, "")], r)
    days = Decimal(365)
    recv, inv, pay = p.get("receivables"), p.get("inventory"), p.get("accounts_payable")
    dso = _safe_div(recv * days if recv is not None else None, rev)
    dio = _safe_div(inv * days if inv is not None else None, cogs)
    dpo = _safe_div(pay * days if pay is not None else None, cogs)
    if dso is not None:
        out["dso"] = _node("ratio.dso", "Days Sales Outstanding",
                           "DSO = Receivables × 365 / Revenue",
                           [("receivables", "AR", recv, ""), ("revenue", "Rev", rev, "")],
                           dso, "days")
    if dio is not None:
        out["dio"] = _node("ratio.dio", "Days Inventory Outstanding",
                           "DIO = Inventory × 365 / COGS",
                           [("inventory", "Inv", inv, ""), ("cost_of_revenue", "COGS", cogs, "")],
                           dio, "days")
    if dpo is not None:
        out["dpo"] = _node("ratio.dpo", "Days Payables Outstanding",
                           "DPO = Payables × 365 / COGS",
                           [("accounts_payable", "AP", pay, ""),
                            ("cost_of_revenue", "COGS", cogs, "")], dpo, "days")
    if dso is not None and dio is not None and dpo is not None:
        out["cash_conversion_cycle"] = _node(
            "ratio.ccc", "Cash Conversion Cycle", "CCC = DSO + DIO − DPO",
            [("dso", "DSO", dso, "days"), ("dio", "DIO", dio, "days"),
             ("dpo", "DPO", dpo, "days")], dso + dio - dpo, "days")
    return out


def market(p: PeriodFinancials, m: MarketInputs) -> dict[str, CalcNode]:
    out: dict[str, CalcNode] = {}
    ni, equity, rev = p.get("net_income"), p.get("total_equity"), p.get("revenue")
    eps = _safe_div(ni, m.shares)
    if eps and eps > 0:
        out["pe"] = _node("ratio.pe", "Price / Earnings", "P/E = Price / EPS",
                          [("price", "Price", m.price, ""), ("eps", "EPS", eps, "")],
                          m.price / eps)
    bvps = _safe_div(equity, m.shares)
    if bvps and bvps > 0:
        out["pb"] = _node("ratio.pb", "Price / Book", "P/B = Price / BVPS",
                          [("price", "Price", m.price, ""), ("bvps", "BVPS", bvps, "")],
                          m.price / bvps)
    r = _safe_div(m.market_cap, rev)
    if r is not None:
        out["ps"] = _node("ratio.ps", "Price / Sales", "P/S = Market Cap / Revenue",
                          [("market_cap", "MCap", m.market_cap, ""),
                           ("revenue", "Revenue", rev, "")], r)
    nd, eb = derived.net_debt(p), derived.ebitda(p)
    if nd and eb and eb.result > 0:
        ev = m.market_cap + nd.result
        n = _node("ratio.ev_ebitda", "EV / EBITDA", "EV/EBITDA = (MCap + Net Debt) / EBITDA",
                  [("market_cap", "MCap", m.market_cap, ""),
                   ("net_debt", "Net Debt", nd.result, ""),
                   ("ebitda", "EBITDA", eb.result, "")], ev / eb.result)
        n.intermediates += [nd, eb]
        out["ev_ebitda"] = n
        if rev:
            out["ev_sales"] = _node("ratio.ev_sales", "EV / Sales", "EV/Sales",
                                    [("ev", "EV", ev, ""), ("revenue", "Rev", rev, "")],
                                    ev / rev)
    fcf = derived.free_cash_flow(p)
    if fcf and m.market_cap > 0:
        out["fcf_yield"] = _node("ratio.fcf_yield", "FCF Yield",
                                 "FCF Yield = FCF / Market Cap",
                                 [("fcf", "FCF", fcf.result, ""),
                                  ("market_cap", "MCap", m.market_cap, "")],
                                 fcf.result / m.market_cap, "%")
    div = p.get("dividends_paid")
    if div and m.market_cap > 0:
        out["dividend_yield"] = _node("ratio.div_yield", "Dividend Yield",
                                      "Yield = Dividends Paid / Market Cap",
                                      [("dividends_paid", "Div", div, ""),
                                       ("market_cap", "MCap", m.market_cap, "")],
                                      div / m.market_cap, "%")
    return out


def all_ratios(p: PeriodFinancials, prior: PeriodFinancials | None,
               m: MarketInputs | None) -> dict[str, dict[str, CalcNode]]:
    groups = {
        "profitability": profitability(p, prior),
        "liquidity": liquidity(p),
        "leverage": leverage(p),
        "efficiency": efficiency(p),
    }
    if m is not None:
        groups["market"] = market(p, m)
    return groups


def dupont(history: FinancialHistory, levels: int = 5) -> CalcNode | None:
    """3-level: ROE = Net Margin × Asset Turnover × Leverage.
    5-level: ROE = Tax Burden × Interest Burden × EBIT Margin × Turnover × Leverage."""
    p = history.latest
    if p is None:
        return None
    vals = p.require("net_income", "revenue", "total_assets", "total_equity")
    if vals is None:
        return None
    ni, rev, assets, equity = vals
    if not all([rev, assets, equity]):
        return None
    if levels == 3:
        margin, turnover, lev = ni / rev, rev / assets, assets / equity
        return CalcNode(
            key="dupont.3", label="DuPont (3-level)",
            formula="ROE = Net Margin × Asset Turnover × Leverage",
            inputs=[CalcInput(name="net_margin", symbol="Net Margin",
                              value=margin.quantize(Q4), unit="%"),
                    CalcInput(name="asset_turnover", symbol="Asset Turnover",
                              value=turnover.quantize(Q4)),
                    CalcInput(name="leverage", symbol="Leverage",
                              value=lev.quantize(Q4))],
            result=(margin * turnover * lev).quantize(Q4), unit="%",
        )
    five = p.require("pretax_income", "operating_income")
    if five is None:
        return dupont(history, levels=3)
    pretax, ebit = five
    if not pretax or not ebit:
        return dupont(history, levels=3)
    tax_burden = ni / pretax
    interest_burden = pretax / ebit
    ebit_margin = ebit / rev
    turnover = rev / assets
    lev = assets / equity
    return CalcNode(
        key="dupont.5", label="DuPont (5-level)",
        formula="ROE = Tax Burden × Interest Burden × EBIT Margin × Turnover × Leverage",
        inputs=[
            CalcInput(name="tax_burden", symbol="Tax Burden",
                      value=tax_burden.quantize(Q4)),
            CalcInput(name="interest_burden", symbol="Interest Burden",
                      value=interest_burden.quantize(Q4)),
            CalcInput(name="ebit_margin", symbol="EBIT Margin",
                      value=ebit_margin.quantize(Q4), unit="%"),
            CalcInput(name="asset_turnover", symbol="Turnover",
                      value=turnover.quantize(Q4)),
            CalcInput(name="leverage", symbol="Leverage", value=lev.quantize(Q4)),
        ],
        result=(tax_burden * interest_burden * ebit_margin * turnover * lev).quantize(Q4),
        unit="%",
        explanation="Decomposes ROE into tax efficiency, financing cost drag, "
                    "operating profitability, asset productivity, and balance-sheet leverage.",
    )
