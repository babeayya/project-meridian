"""Classic diagnostic scores: Altman Z, Piotroski F, Beneish M — each with a
full component trace. Returns None when required inputs are missing."""
from decimal import Decimal

from pydantic import BaseModel

from app.domain.calc.trace import CalcInput, CalcNode
from app.domain.statements.history import PeriodFinancials

Q4 = Decimal("0.0001")


class ScoreResult(BaseModel):
    score_type: str
    value: Decimal
    grade: str
    components: list[dict]
    trace: dict
    not_applicable_reason: str | None = None


def altman_z(p: PeriodFinancials, market_cap: Decimal | None,
             is_financial: bool, is_manufacturer: bool) -> ScoreResult | None:
    """Z (public manufacturer) or Z'' (non-manufacturer / emerging markets).
    Financials are out of model scope — asset structure breaks the ratios."""
    if is_financial:
        return ScoreResult(score_type="altman_z", value=Decimal(0), grade="n/a",
                           components=[], trace={},
                           not_applicable_reason="Altman Z is not defined for "
                           "banks/insurers (leverage is their business model).")
    vals = p.require("current_assets", "current_liabilities", "total_assets",
                     "retained_earnings", "operating_income", "total_liabilities")
    if vals is None:
        return None
    ca, cl, ta, re, ebit, tl = vals
    if ta == 0 or tl == 0:
        return None
    x1 = (ca - cl) / ta
    x2 = re / ta
    x3 = ebit / ta

    if is_manufacturer and market_cap is not None:
        rev = p.get("revenue")
        if rev is None:
            return None
        x4 = market_cap / tl
        x5 = rev / ta
        weights = [Decimal("1.2"), Decimal("1.4"), Decimal("3.3"),
                   Decimal("0.6"), Decimal("1.0")]
        xs = [x1, x2, x3, x4, x5]
        variant, formula = "Z (original, public manufacturer)", \
            "Z = 1.2·X1 + 1.4·X2 + 3.3·X3 + 0.6·X4 + 1.0·X5"
        zones = (Decimal("1.81"), Decimal("2.99"))
    else:
        bv_equity = p.get("total_equity")
        if bv_equity is None:
            return None
        x4 = bv_equity / tl
        weights = [Decimal("6.56"), Decimal("3.26"), Decimal("6.72"), Decimal("1.05")]
        xs = [x1, x2, x3, x4]
        variant, formula = "Z'' (non-manufacturer / EM)", \
            "Z'' = 6.56·X1 + 3.26·X2 + 6.72·X3 + 1.05·X4"
        zones = (Decimal("1.1"), Decimal("2.6"))

    z = sum(w * x for w, x in zip(weights, xs, strict=True))
    grade = ("distress" if z < zones[0]
             else "grey" if z < zones[1] else "safe")
    labels = ["X1 WC/TA", "X2 RE/TA", "X3 EBIT/TA", "X4", "X5 Sales/TA"][:len(xs)]
    node = CalcNode(
        key="score.altman_z", label=f"Altman {variant}", formula=formula,
        inputs=[CalcInput(name=lbl, symbol=lbl.split()[0], value=x.quantize(Q4))
                for lbl, x in zip(labels, xs, strict=True)],
        result=z.quantize(Q4),
        explanation=f"Variant selected: {variant}. Zones: distress < {zones[0]}, "
                    f"safe > {zones[1]}.",
    )
    return ScoreResult(
        score_type="altman_z", value=z.quantize(Q4), grade=grade,
        components=[{"name": lbl, "value": str(x.quantize(Q4)), "weight": str(w)}
                    for lbl, x, w in zip(labels, xs, weights, strict=True)],
        trace=node.to_dict(),
    )


def piotroski_f(p: PeriodFinancials, prior: PeriodFinancials | None) -> ScoreResult | None:
    if prior is None:
        return None
    checks: list[dict] = []

    def add(name: str, passed: bool | None, detail: str) -> int:
        if passed is None:
            checks.append({"name": name, "passed": None, "detail": f"{detail} (data missing)"})
            return 0
        checks.append({"name": name, "passed": passed, "detail": detail})
        return 1 if passed else 0

    def ratio(pd: PeriodFinancials, num: str, den: str) -> Decimal | None:
        n, d = pd.get(num), pd.get(den)
        return None if n is None or not d else n / d

    score = 0
    ni = p.get("net_income")
    roa = ratio(p, "net_income", "total_assets")
    roa_prior = ratio(prior, "net_income", "total_assets")
    ocf = p.get("operating_cash_flow")
    score += add("ROA positive", None if roa is None else roa > 0,
                 f"ROA = {roa}" if roa is not None else "")
    score += add("OCF positive", None if ocf is None else ocf > 0, f"OCF = {ocf}")
    score += add("ROA improving",
                 None if roa is None or roa_prior is None else roa > roa_prior,
                 f"{roa_prior} → {roa}")
    score += add("Accruals (OCF > NI)",
                 None if ocf is None or ni is None else ocf > ni,
                 f"OCF {ocf} vs NI {ni}")

    lev = ratio(p, "long_term_debt", "total_assets")
    lev_prior = ratio(prior, "long_term_debt", "total_assets")
    score += add("Leverage decreasing",
                 None if lev is None or lev_prior is None else lev <= lev_prior,
                 f"LTD/TA {lev_prior} → {lev}")
    cr = ratio(p, "current_assets", "current_liabilities")
    cr_prior = ratio(prior, "current_assets", "current_liabilities")
    score += add("Current ratio improving",
                 None if cr is None or cr_prior is None else cr > cr_prior,
                 f"{cr_prior} → {cr}")
    sh, sh_prior = p.get("shares_diluted"), prior.get("shares_diluted")
    score += add("No dilution",
                 None if sh is None or sh_prior is None else sh <= sh_prior * Decimal("1.02"),
                 f"shares {sh_prior} → {sh}")
    gm = ratio(p, "gross_profit", "revenue")
    gm_prior = ratio(prior, "gross_profit", "revenue")
    score += add("Gross margin improving",
                 None if gm is None or gm_prior is None else gm > gm_prior,
                 f"{gm_prior} → {gm}")
    at = ratio(p, "revenue", "total_assets")
    at_prior = ratio(prior, "revenue", "total_assets")
    score += add("Asset turnover improving",
                 None if at is None or at_prior is None else at > at_prior,
                 f"{at_prior} → {at}")

    grade = "strong" if score >= 7 else "moderate" if score >= 4 else "weak"
    node = CalcNode(
        key="score.piotroski_f", label="Piotroski F-Score",
        formula="F = Σ of 9 binary fundamental tests",
        result=Decimal(score),
        explanation="Profitability (4) + leverage/liquidity (3) + efficiency (2) tests "
                    "vs the prior fiscal year.",
    )
    return ScoreResult(score_type="piotroski_f", value=Decimal(score), grade=grade,
                       components=checks, trace=node.to_dict())


def beneish_m(p: PeriodFinancials, prior: PeriodFinancials | None) -> ScoreResult | None:
    """8-index earnings-manipulation model. M > −1.78 flags likely manipulation."""
    if prior is None:
        return None

    def g(pd: PeriodFinancials, key: str) -> Decimal | None:
        return pd.get(key)

    def idx(cur_n, cur_d, pri_n, pri_d) -> Decimal | None:
        if None in (cur_n, cur_d, pri_n, pri_d) or 0 in (cur_d, pri_d):
            return None
        cur, pri = cur_n / cur_d, pri_n / pri_d
        return None if pri == 0 else cur / pri

    rev, rev_p = g(p, "revenue"), g(prior, "revenue")
    ta, ta_p = g(p, "total_assets"), g(prior, "total_assets")
    if None in (rev, rev_p, ta, ta_p) or 0 in (rev, rev_p, ta, ta_p):
        return None

    dsri = idx(g(p, "receivables"), rev, g(prior, "receivables"), rev_p)
    gmi_cur = idx(g(prior, "gross_profit"), rev_p, g(p, "gross_profit"), rev)  # prior/current
    aqi = None
    ca, ppe = g(p, "current_assets"), g(p, "net_ppe")
    ca_p, ppe_p = g(prior, "current_assets"), g(prior, "net_ppe")
    if None not in (ca, ppe, ca_p, ppe_p):
        soft = 1 - (ca + ppe) / ta
        soft_p = 1 - (ca_p + ppe_p) / ta_p
        aqi = None if soft_p == 0 else soft / soft_p
    sgi = rev / rev_p
    depi = None
    da, da_p = g(p, "depreciation_amortization"), g(prior, "depreciation_amortization")
    if None not in (da, da_p, ppe, ppe_p) and (da + ppe) and (da_p + ppe_p):
        depi = (da_p / (da_p + ppe_p)) / (da / (da + ppe))
    sgai = idx(g(p, "sga_expense"), rev, g(prior, "sga_expense"), rev_p)
    lvgi = idx((g(p, "total_liabilities")), ta, (g(prior, "total_liabilities")), ta_p)
    tata = None
    ni, ocf = g(p, "net_income"), g(p, "operating_cash_flow")
    if None not in (ni, ocf):
        tata = (ni - ocf) / ta

    # Beneish (1999) coefficients; missing indices take neutral value 1 (0 for TATA)
    terms = [
        ("DSRI", dsri, Decimal("0.920")), ("GMI", gmi_cur, Decimal("0.528")),
        ("AQI", aqi, Decimal("0.404")), ("SGI", sgi, Decimal("0.892")),
        ("DEPI", depi, Decimal("0.115")), ("SGAI", sgai, Decimal("-0.172")),
        ("TATA", tata, Decimal("4.679")), ("LVGI", lvgi, Decimal("-0.327")),
    ]
    m = Decimal("-4.84")
    components = []
    missing = 0
    for name, val, coef in terms:
        neutral = Decimal(0) if name == "TATA" else Decimal(1)
        used = val if val is not None else neutral
        if val is None:
            missing += 1
        m += coef * used
        components.append({"index": name, "value": str(used.quantize(Q4)),
                           "coefficient": str(coef), "imputed": val is None})
    if missing >= 4:
        return None  # too sparse to be meaningful

    grade = "flag" if m > Decimal("-1.78") else "clean"
    node = CalcNode(
        key="score.beneish_m", label="Beneish M-Score",
        formula="M = −4.84 + 0.92·DSRI + 0.528·GMI + 0.404·AQI + 0.892·SGI "
                "+ 0.115·DEPI − 0.172·SGAI + 4.679·TATA − 0.327·LVGI",
        result=m.quantize(Q4),
        explanation="M > −1.78 suggests elevated probability of earnings "
                    "manipulation. Missing indices imputed at neutral values.",
        assumptions=[f"{missing} of 8 indices imputed neutral"] if missing else [],
    )
    return ScoreResult(score_type="beneish_m", value=m.quantize(Q4), grade=grade,
                       components=components, trace=node.to_dict())
