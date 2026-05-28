from __future__ import annotations

from dataclasses import dataclass
import math
import re
from typing import Iterable

import pandas as pd

from wisereport_scraper import TableRecord, clean_text


def to_float(value: object) -> float | None:
    text = clean_text(value)
    if not text or text.lower() in {"nan", "n/a", "na", "-"}:
        return None
    text = text.replace(",", "").replace("%", "")
    text = re.sub(r"[^0-9.\-]", "", text)
    if text in {"", ".", "-", "-."}:
        return None
    try:
        number = float(text)
    except ValueError:
        return None
    if math.isnan(number):
        return None
    return number


def normalize_metric_name(value: object) -> str:
    text = clean_text(value)
    text = text.replace("펼치기", "").strip()
    text = re.sub(r"＜.*?＞", "", text)
    text = re.sub(r"\(.*?\)", "", text)
    return clean_text(text).upper()


def period_tokens(period: str) -> set[str]:
    text = clean_text(period)
    years = re.findall(r"(20\d{2})", text)
    months = re.findall(r"(?:20\d{2})[./-]?(\d{2})?", text)
    tokens = {text, text.replace(".", "/"), text.replace("/", ".")}
    for year in years:
        tokens.add(year)
        for month in months:
            if month:
                tokens.add(f"{year}/{month}")
                tokens.add(f"{year}.{month}")
    return {token for token in tokens if token}


def label_matches_period(label: object, period: str) -> bool:
    text = clean_text(label).replace(" ", "")
    for token in period_tokens(period):
        token = token.replace(" ", "")
        if token and token in text:
            return True
    return False


@dataclass(slots=True)
class MetricHit:
    metric: str
    period: str
    value: float
    raw_value: str
    source: str


def _source_name(record: TableRecord) -> str:
    return f"{record.page_label} - {record.title}"


def find_metric(
    tables: Iterable[TableRecord],
    metric: str,
    period: str,
    preferred_pages: Iterable[str] | None = None,
) -> MetricHit | None:
    target = normalize_metric_name(metric)
    preferred = set(preferred_pages or [])
    ordered = sorted(
        list(tables),
        key=lambda r: 0 if r.page_key in preferred else 1,
    )

    for record in ordered:
        df = record.dataframe
        if df.empty or len(df.columns) < 2:
            continue

        # Shape A: first column is period, columns are metrics.
        first_col = df.columns[0]
        if any(label_matches_period(v, period) for v in df[first_col].head(20)):
            metric_cols = [col for col in df.columns if target == normalize_metric_name(col)]
            if not metric_cols:
                metric_cols = [col for col in df.columns if target in normalize_metric_name(col)]
            for _, row in df.iterrows():
                if not label_matches_period(row[first_col], period):
                    continue
                for col in metric_cols:
                    value = to_float(row[col])
                    if value is not None:
                        return MetricHit(metric, period, value, clean_text(row[col]), _source_name(record))

        # Shape B: first column is metric, columns are periods.
        first_col = df.columns[0]
        period_cols = [col for col in df.columns if label_matches_period(col, period)]
        if not period_cols:
            continue
        for _, row in df.iterrows():
            row_name = normalize_metric_name(row[first_col])
            if row_name != target and not row_name.startswith(target):
                continue
            for col in period_cols:
                value = to_float(row[col])
                if value is not None:
                    return MetricHit(metric, period, value, clean_text(row[col]), _source_name(record))
    return None


def cagr(start: float | None, end: float | None, years: float) -> float | None:
    if start is None or end is None or years <= 0:
        return None
    if start <= 0 or end <= 0:
        return None
    return (end / start) ** (1 / years) - 1


def years_between(start_period: str, end_period: str) -> float:
    years = [int(x) for x in re.findall(r"20\d{2}", f"{start_period} {end_period}")]
    if len(years) >= 2:
        return max(years[-1] - years[0], 1)
    return 1


@dataclass(slots=True)
class ValuationInputs:
    period: str
    weights: dict[str, float]
    target_multiples: dict[str, float]
    start_period_for_growth: str | None = None
    current_price: float | None = None


@dataclass(slots=True)
class ValuationResult:
    target_price: float | None
    upside_pct: float | None
    detail: pd.DataFrame
    metric_sources: list[MetricHit]


def calculate_target_price(tables: Iterable[TableRecord], inputs: ValuationInputs) -> ValuationResult:
    table_list = list(tables)
    metric_sources: list[MetricHit] = []
    rows: list[dict[str, object]] = []

    def add_hit(hit: MetricHit | None) -> MetricHit | None:
        if hit is not None:
            metric_sources.append(hit)
        return hit

    eps = add_hit(find_metric(table_list, "EPS", inputs.period, ["investment_indicators", "consensus"]))
    bps = add_hit(find_metric(table_list, "BPS", inputs.period, ["investment_indicators", "consensus"]))
    cps = add_hit(find_metric(table_list, "CPS", inputs.period, ["investment_indicators"]))

    method_price: dict[str, float] = {}
    method_basis: dict[str, str] = {}

    if eps and inputs.target_multiples.get("PER"):
        method_price["PER"] = eps.value * inputs.target_multiples["PER"]
        method_basis["PER"] = f"EPS {eps.value:g} x PER {inputs.target_multiples['PER']:g}"

    if bps and inputs.target_multiples.get("PBR"):
        method_price["PBR"] = bps.value * inputs.target_multiples["PBR"]
        method_basis["PBR"] = f"BPS {bps.value:g} x PBR {inputs.target_multiples['PBR']:g}"

    if cps and inputs.target_multiples.get("PCR"):
        method_price["PCR"] = cps.value * inputs.target_multiples["PCR"]
        method_basis["PCR"] = f"CPS {cps.value:g} x PCR {inputs.target_multiples['PCR']:g}"

    weighted_sum = 0.0
    weight_sum = 0.0
    for method, price in method_price.items():
        weight = max(float(inputs.weights.get(method, 0.0)), 0.0)
        if weight <= 0:
            continue
        weighted_sum += price * weight
        weight_sum += weight
        rows.append(
            {
                "method": method,
                "weight": weight,
                "target_price": round(price, 2),
                "basis": method_basis.get(method, ""),
            }
        )

    target = weighted_sum / weight_sum if weight_sum else None
    upside = None
    if target is not None and inputs.current_price and inputs.current_price > 0:
        upside = (target / inputs.current_price - 1) * 100

    detail = pd.DataFrame(rows, columns=["method", "weight", "target_price", "basis"])
    return ValuationResult(target, upside, detail, metric_sources)
