from __future__ import annotations

import io
import os
import re
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from typing import Any, Callable

import pandas as pd


STATEMENT_ALIASES = {
    "revenue": {"revenue", "sales", "net sales", "total revenue"},
    "gross_profit": {"gross profit"},
    "operating_income": {"operating income", "ebit", "operating profit"},
    "net_income": {"net income", "net profit", "profit after tax", "pat"},
    "cash_from_operations": {"cash from operations", "operating cash flow", "cfo", "net cash from operating activities"},
    "accounts_receivable": {"accounts receivable", "trade receivables", "receivables"},
    "inventory": {"inventory", "inventories"},
    "current_assets": {"current assets"},
    "current_liabilities": {"current liabilities"},
    "total_assets": {"total assets"},
    "total_debt": {"total debt", "debt", "borrowings", "total borrowings"},
    "total_equity": {"total equity", "shareholders equity", "stockholders equity", "net worth"},
    "interest_expense": {"interest expense", "finance cost", "interest costs"},
}


@dataclass
class Fact:
    company: str
    metric: str
    period: str
    value: float
    statement: str
    source: str

    def citation(self) -> str:
        return f"[{self.company} | {self.statement} | {self.metric} | {self.period} | {self.source}]"


@dataclass
class AnalysisResult:
    company: str
    periods: list[str]
    facts: list[Fact]
    ratios: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    trends: list[dict[str, Any]] = field(default_factory=list)
    red_flags: list[dict[str, Any]] = field(default_factory=list)
    narrative: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "company": self.company,
            "periods": self.periods,
            "facts": [asdict(fact) | {"citation": fact.citation()} for fact in self.facts],
            "ratios": self.ratios,
            "trends": self.trends,
            "red_flags": self.red_flags,
            "narrative": self.narrative,
        }


def _clean_label(value: Any) -> str:
    return re.sub(r"[^a-z0-9 ]", "", str(value).lower()).strip()


def _number(value: Any) -> float | None:
    if pd.isna(value):
        return None
    text = str(value).replace(",", "").replace("$", "").replace("€", "").replace("£", "")
    text = text.replace("(", "-").replace(")", "").replace("%", "").strip()
    try:
        return float(text)
    except ValueError:
        return None


def _canonical_metric(label: str) -> str | None:
    normalized = _clean_label(label)
    for metric, aliases in STATEMENT_ALIASES.items():
        if normalized in aliases or any(alias in normalized for alias in aliases):
            return metric
    return None


def _read_table(data: bytes, filename: str) -> pd.DataFrame:
    suffix = filename.lower().rsplit(".", 1)[-1]
    if suffix in {"xlsx", "xls"}:
        return pd.read_excel(io.BytesIO(data))
    if suffix == "pdf":
        try:
            import pdfplumber
        except ImportError as exc:
            raise ValueError("PDF uploads require pdfplumber. Install the project requirements.") from exc
        rows: list[list[str]] = []
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            for page in pdf.pages:
                for table in page.extract_tables() or []:
                    rows.extend(table)
        if not rows:
            raise ValueError("No tabular data was found in the PDF.")
        return pd.DataFrame(rows[1:], columns=rows[0])
    return pd.read_csv(io.BytesIO(data))


def parse_facts(data: bytes, filename: str, company: str) -> list[Fact]:
    frame = _read_table(data, filename).dropna(how="all")
    if frame.shape[1] < 2:
        raise ValueError("The statement needs a metric column and at least one period column.")
    metric_column = frame.columns[0]
    periods = [str(column) for column in frame.columns[1:]]
    facts: list[Fact] = []
    statement = "Financial statements"
    if "balance" in filename.lower():
        statement = "Balance Sheet"
    elif "cash" in filename.lower():
        statement = "Cash Flow Statement"
    elif "income" in filename.lower() or "profit" in filename.lower():
        statement = "Income Statement"
    for _, row in frame.iterrows():
        metric = _canonical_metric(row[metric_column])
        if not metric:
            continue
        for period in periods:
            value = _number(row[period])
            if value is not None:
                facts.append(Fact(company, metric, period, value, statement, filename))
    if not facts:
        raise ValueError("No supported financial metrics were found. Use rows such as Revenue, Net Income, Current Assets, or Total Debt.")
    return facts


def _fact_map(facts: list[Fact]) -> dict[tuple[str, str], Fact]:
    return {(fact.metric, fact.period): fact for fact in facts}


def _ratio(name: str, numerator: str, denominator: str, facts: list[Fact], periods: list[str], scale: float = 1.0) -> list[dict[str, Any]]:
    lookup = _fact_map(facts)
    values = []
    for period in periods:
        top, bottom = lookup.get((numerator, period)), lookup.get((denominator, period))
        if top and bottom and bottom.value != 0:
            values.append({"period": period, "value": round(top.value / bottom.value * scale, 4), "citations": [top.citation(), bottom.citation()]})
    return values


def compute_analysis(facts: list[Fact], company: str) -> AnalysisResult:
    periods = list(dict.fromkeys(fact.period for fact in facts))
    result = AnalysisResult(company, periods, facts)
    result.ratios = {
        "current_ratio": _ratio("Current ratio", "current_assets", "current_liabilities", facts, periods),
        "debt_to_equity": _ratio("Debt to equity", "total_debt", "total_equity", facts, periods),
        "debt_ratio": _ratio("Debt ratio", "total_debt", "total_assets", facts, periods),
        "gross_margin_percent": _ratio("Gross margin", "gross_profit", "revenue", facts, periods, 100),
        "operating_margin_percent": _ratio("Operating margin", "operating_income", "revenue", facts, periods, 100),
        "net_margin_percent": _ratio("Net margin", "net_income", "revenue", facts, periods, 100),
        "dso_days": _ratio("Days sales outstanding", "accounts_receivable", "revenue", facts, periods, 365),
        "inventory_to_revenue": _ratio("Inventory to revenue", "inventory", "revenue", facts, periods),
        "cfo_to_net_income": _ratio("CFO to net income", "cash_from_operations", "net_income", facts, periods),
        "return_on_assets_percent": _ratio("Return on assets", "net_income", "total_assets", facts, periods, 100),
        "return_on_equity_percent": _ratio("Return on equity", "net_income", "total_equity", facts, periods, 100),
    }
    for name, points in result.ratios.items():
        if len(points) >= 2:
            first, last = points[0], points[-1]
            direction = "increased" if last["value"] > first["value"] else "decreased" if last["value"] < first["value"] else "was flat"
            delta = round(last["value"] - first["value"], 4)
            percent_change = round(delta / first["value"] * 100, 4) if first["value"] else None
            result.trends.append({
                "metric": name,
                "from": first,
                "to": last,
                "direction": direction,
                "delta": delta,
                "percent_change": percent_change,
            })

    def flag(name: str, severity: str, message: str, ratio_name: str) -> None:
        points = result.ratios.get(ratio_name, [])
        if len(points) >= 2:
            result.red_flags.append({"name": name, "severity": severity, "message": message, "evidence": points[-2:], "citations": sum((point["citations"] for point in points[-2:]), [])})

    cfo = result.ratios["cfo_to_net_income"]
    if cfo and cfo[-1]["value"] < 0.8:
        flag("Accrual-quality gap", "high", "Cash generated from operations is below net income, which can indicate earnings are not converting into cash.", "cfo_to_net_income")
    dso = result.ratios["dso_days"]
    if len(dso) >= 2 and dso[-1]["value"] > dso[-2]["value"]:
        flag("DSO climbing", "medium", "Receivables are taking longer to convert into cash.", "dso_days")
    margins = result.ratios["operating_margin_percent"]
    if len(margins) >= 2 and margins[-1]["value"] < margins[-2]["value"]:
        flag("Margin compression", "medium", "Operating margin has declined across the available periods.", "operating_margin_percent")
    leverage = result.ratios["debt_to_equity"]
    if leverage and leverage[-1]["value"] > 1:
        flag("Leverage stress", "high", "Debt is greater than equity in the latest available period.", "debt_to_equity")
    inventory = result.ratios["inventory_to_revenue"]
    if len(inventory) >= 2 and inventory[-1]["value"] > inventory[-2]["value"]:
        flag("Inventory build-up", "medium", "Inventory is growing faster than revenue.", "inventory_to_revenue")
    liquidity = result.ratios["current_ratio"]
    if liquidity and liquidity[-1]["value"] < 1:
        flag("Liquidity deterioration", "high", "Current assets do not cover current liabilities in the latest available period.", "current_ratio")
    result.narrative = build_narrative(result)
    return result


def build_narrative(result: AnalysisResult) -> str:
    if not result.trends and not result.red_flags:
        return f"{result.company}: the uploaded statements contain limited comparable data. Ask about a specific metric for a cited answer."
    parts = [f"{result.company} covers {', '.join(result.periods)}."]
    if result.red_flags:
        parts.append("Key watch areas: " + ", ".join(flag["name"] for flag in result.red_flags) + ".")
    if result.trends:
        notable = [trend for trend in result.trends if trend["metric"] in {"current_ratio", "debt_to_equity", "operating_margin_percent", "dso_days"}]
        if notable:
            parts.append("Notable movements: " + "; ".join(f"{item['metric']} {item['direction']}" for item in notable) + ".")
    return " ".join(parts)


def analyze_upload(data: bytes, filename: str, company: str) -> AnalysisResult:
    return compute_analysis(parse_facts(data, filename, company), company)


def answer_question(
    result: AnalysisResult,
    question: str,
    answerer: Callable[[AnalysisResult, str], dict[str, Any] | None] | None = None,
) -> dict[str, Any]:
    """Answer from uploaded facts, optionally through an injected provider."""
    words = set(re.findall(r"[a-z0-9]+", question.lower()))
    candidates = sorted(result.facts, key=lambda fact: len(words & set(fact.metric.replace("_", " ").split())), reverse=True)
    candidates = [fact for fact in candidates if words & set(fact.metric.replace("_", " ").split()) or any(term in question.lower() for term in fact.metric.split("_"))][:6]

    if answerer:
        try:
            response = answerer(result, question)
        except Exception:
            response = None
        if response:
            return response

    if not candidates:
        return {"answer": "I don't have that information in the uploaded statements.", "citations": []}
    lines = [f"{fact.metric.replace('_', ' ').title()} was {fact.value:g} in {fact.period}." for fact in candidates[:3]]
    return {"answer": " ".join(lines), "citations": [fact.citation() for fact in candidates[:3]]}


def compare_results(left: AnalysisResult, right: AnalysisResult) -> dict[str, Any]:
    warnings = []
    if left.periods != right.periods:
        warnings.append("Fiscal periods differ; compare directionally rather than as a like-for-like year pair.")
    rows = []
    for metric in sorted(set(left.ratios) & set(right.ratios)):
        left_latest = left.ratios[metric][-1] if left.ratios[metric] else None
        right_latest = right.ratios[metric][-1] if right.ratios[metric] else None
        if left_latest and right_latest:
            rows.append({"metric": metric, left.company: left_latest, right.company: right_latest})
    return {"companies": [left.company, right.company], "warnings": warnings, "rows": rows}