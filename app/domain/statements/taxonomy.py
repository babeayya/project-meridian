"""Canonical line-item taxonomy.

Every provider's statement payload is normalized to these keys before storage.
Values follow analyst conventions: outflows that are magnitudes by nature
(capex, dividends_paid, share_repurchase, debt_repaid) are stored POSITIVE;
signed flows (net_income, operating_cash_flow, change_in_working_capital)
keep their sign.
"""
from enum import StrEnum


class StatementType(StrEnum):
    INCOME = "income"
    BALANCE = "balance"
    CASHFLOW = "cashflow"


# canonical key → (statement, human label)
CANONICAL: dict[str, tuple[StatementType, str]] = {
    # income statement
    "revenue": (StatementType.INCOME, "Revenue"),
    "cost_of_revenue": (StatementType.INCOME, "Cost of Revenue"),
    "gross_profit": (StatementType.INCOME, "Gross Profit"),
    "rnd_expense": (StatementType.INCOME, "Research & Development"),
    "sga_expense": (StatementType.INCOME, "Selling, General & Administrative"),
    "operating_expense": (StatementType.INCOME, "Total Operating Expenses"),
    "operating_income": (StatementType.INCOME, "Operating Income (EBIT)"),
    "interest_expense": (StatementType.INCOME, "Interest Expense"),
    "pretax_income": (StatementType.INCOME, "Pre-tax Income"),
    "income_tax": (StatementType.INCOME, "Income Tax Expense"),
    "net_income": (StatementType.INCOME, "Net Income"),
    "eps_diluted": (StatementType.INCOME, "Diluted EPS"),
    "shares_diluted": (StatementType.INCOME, "Diluted Shares Outstanding"),
    # cash flow
    "depreciation_amortization": (StatementType.CASHFLOW, "Depreciation & Amortization"),
    "stock_compensation": (StatementType.CASHFLOW, "Stock-Based Compensation"),
    "change_in_working_capital": (StatementType.CASHFLOW, "Change in Working Capital"),
    "operating_cash_flow": (StatementType.CASHFLOW, "Operating Cash Flow"),
    "capex": (StatementType.CASHFLOW, "Capital Expenditure"),
    "dividends_paid": (StatementType.CASHFLOW, "Dividends Paid"),
    "share_repurchase": (StatementType.CASHFLOW, "Share Repurchases"),
    # balance sheet
    "cash_and_equivalents": (StatementType.BALANCE, "Cash & Equivalents"),
    "short_term_investments": (StatementType.BALANCE, "Short-Term Investments"),
    "receivables": (StatementType.BALANCE, "Accounts Receivable"),
    "inventory": (StatementType.BALANCE, "Inventory"),
    "current_assets": (StatementType.BALANCE, "Total Current Assets"),
    "net_ppe": (StatementType.BALANCE, "Net PP&E"),
    "goodwill": (StatementType.BALANCE, "Goodwill"),
    "intangibles": (StatementType.BALANCE, "Intangible Assets"),
    "total_assets": (StatementType.BALANCE, "Total Assets"),
    "accounts_payable": (StatementType.BALANCE, "Accounts Payable"),
    "short_term_debt": (StatementType.BALANCE, "Short-Term Debt"),
    "current_liabilities": (StatementType.BALANCE, "Total Current Liabilities"),
    "long_term_debt": (StatementType.BALANCE, "Long-Term Debt"),
    "total_liabilities": (StatementType.BALANCE, "Total Liabilities"),
    "total_equity": (StatementType.BALANCE, "Total Shareholders' Equity"),
    "retained_earnings": (StatementType.BALANCE, "Retained Earnings"),
    "minority_interest": (StatementType.BALANCE, "Minority Interest"),
}

# keys that are outflow magnitudes: providers reporting them negative are
# sign-flipped at normalization time
POSITIVE_MAGNITUDE_KEYS = frozenset(
    {"capex", "dividends_paid", "share_repurchase", "interest_expense"}
)


def statement_of(key: str) -> StatementType | None:
    entry = CANONICAL.get(key)
    return entry[0] if entry else None


def label_of(key: str) -> str:
    entry = CANONICAL.get(key)
    return entry[1] if entry else key
