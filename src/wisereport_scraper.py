from __future__ import annotations

from dataclasses import dataclass, field
from io import StringIO
import os
import re
import time
from typing import Iterable

import pandas as pd

try:
    import requests
except ModuleNotFoundError:  # pragma: no cover - handled at runtime for app usage.
    requests = None

try:
    from bs4 import BeautifulSoup, Tag
except ModuleNotFoundError:  # pragma: no cover - handled at runtime for app usage.
    BeautifulSoup = None

    class Tag:  # type: ignore[no-redef]
        pass


BASE_URL = "https://navercomp.wisereport.co.kr/v2/company/{page}.aspx?cmp_cd={code}&cn="
PEER_HEADER_URL = "https://navercomp.wisereport.co.kr/company/ajax/cF6001.aspx"
PEER_TABLE_URL = "https://navercomp.wisereport.co.kr/company/cF6002.aspx"

DEFAULT_PAGES: dict[str, str] = {
    "company_status": "c1010001",
    "company_overview": "c1020001",
    "financial_analysis": "c1030001",
    "investment_indicators": "c1040001",
    "consensus": "c1050001",
    "industry_analysis": "c1060001",
    "ownership": "c1070001",
    "sector_analysis": "c1090001",
}

PAGE_LABELS: dict[str, str] = {
    "company_status": "기업현황",
    "company_overview": "기업개요",
    "financial_analysis": "재무분석",
    "investment_indicators": "투자지표",
    "consensus": "컨센서스",
    "industry_analysis": "업종분석",
    "ownership": "지분현황",
    "sector_analysis": "섹터분석",
}

KNOWN_TABLE_TITLES: dict[str, str] = {
    "cTB511": "주가 & 컨센서스 재무요약",
    "cTB512": "컨센서스 추이",
    "cTB513": "어닝서프라이즈",
    "draggable-table-body": "재무계정산식 설명",
}

CONTROL_CLASS_TOKENS = {
    "schbox",
    "schtab",
    "chart-tooltip",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    ),
    "Referer": "https://finance.naver.com/",
}


@dataclass(slots=True)
class TableRecord:
    page_key: str
    page_label: str
    title: str
    table_id: str
    order: int
    dataframe: pd.DataFrame


@dataclass(slots=True)
class StockBundle:
    code: str
    company_name: str = ""
    metadata: dict[str, str] = field(default_factory=dict)
    headline_metrics: dict[str, str] = field(default_factory=dict)
    tables: list[TableRecord] = field(default_factory=list)
    errors: dict[str, str] = field(default_factory=dict)

    def table_map(self) -> dict[str, pd.DataFrame]:
        out: dict[str, pd.DataFrame] = {}
        seen: dict[str, int] = {}
        for record in self.tables:
            base = f"{record.page_label} - {record.title}"
            count = seen.get(base, 0) + 1
            seen[base] = count
            key = base if count == 1 else f"{base} ({count})"
            out[key] = record.dataframe
        return out


def normalize_code(code: str | int) -> str:
    digits = re.sub(r"\D", "", str(code))
    if not digits:
        raise ValueError("stock code must contain digits")
    return digits.zfill(6)[-6:]


def clean_text(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def flatten_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [
            " ".join(clean_text(part) for part in col if clean_text(part) and not str(part).startswith("Unnamed"))
            for col in df.columns
        ]
    else:
        df.columns = [clean_text(col) for col in df.columns]

    cleaned: list[str] = []
    seen: dict[str, int] = {}
    for i, col in enumerate(df.columns):
        name = col or f"col_{i + 1}"
        seen[name] = seen.get(name, 0) + 1
        cleaned.append(name if seen[name] == 1 else f"{name}_{seen[name]}")
    df.columns = cleaned

    for col in df.columns:
        if df[col].dtype == "object":
            df[col] = df[col].map(lambda x: clean_text(x).replace("\xa0", " ") if pd.notna(x) else x)
    return df


def table_to_dataframe(table: Tag) -> pd.DataFrame | None:
    try:
        dfs = pd.read_html(StringIO(str(table)), displayed_only=False)
    except ValueError:
        return None
    if not dfs:
        return None
    df = flatten_columns(dfs[0])
    df = df.dropna(how="all").reset_index(drop=True)
    if df.empty:
        return None
    return df


def fetch_html(session: requests.Session, url: str, timeout: int = 15) -> str:
    response = session.get(url, timeout=timeout)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding
    return response.text


def create_chrome_driver(headless: bool = True, chrome_binary: str | None = None, driver_path: str | None = None):
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError("Install browser dependencies with: pip install selenium webdriver-manager") from exc

    chrome_binary = chrome_binary or os.getenv("CHROME_BIN") or os.getenv("CHROME_BINARY")
    driver_path = driver_path or os.getenv("CHROMEDRIVER_PATH") or os.getenv("CHROME_DRIVER_PATH")

    options = Options()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1400,1600")
    if chrome_binary:
        options.binary_location = chrome_binary

    if driver_path:
        return webdriver.Chrome(service=Service(driver_path), options=options)

    try:
        return webdriver.Chrome(options=options)
    except Exception:
        try:
            from webdriver_manager.chrome import ChromeDriverManager
        except ModuleNotFoundError as exc:
            raise ModuleNotFoundError("Install webdriver-manager or pass an explicit driver_path") from exc
        return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)


def render_html(driver, url: str, wait_seconds: float = 2.0) -> str:
    driver.get(url)
    time.sleep(wait_seconds)
    return driver.page_source


def parse_company_header(soup: BeautifulSoup) -> tuple[dict[str, str], dict[str, str]]:
    metadata: dict[str, str] = {}
    metrics: dict[str, str] = {}
    table = soup.select_one("table.cmp-table")
    if not table:
        return metadata, metrics

    rows = [clean_text(row.get_text(" ")) for row in table.select("tr")]
    if rows:
        first = rows[0]
        code_match = re.search(r"\b(\d{6})\b", first)
        if code_match:
            metadata["code"] = code_match.group(1)
        if code_match:
            metadata["company_name"] = first[: code_match.start()].strip()
        market_match = re.search(r"KOSPI|KOSDAQ|KONEX", first, flags=re.I)
        if market_match:
            metadata["market"] = market_match.group(0).upper()
        wics_match = re.search(r"WICS\s*:\s*(.+)$", first)
        if wics_match:
            metadata["wics"] = wics_match.group(1).strip()

    metric_text = " ".join(rows[1:])
    for key in ["현재가", "EPS", "BPS", "PER", "업종PER", "PBR", "현금배당수익률"]:
        pattern = rf"{re.escape(key)}\s+([^\s]+)"
        match = re.search(pattern, metric_text)
        if match:
            metrics[key] = match.group(1)

    fiscal_match = re.search(r"(\d{1,2}월\s+결산)", metric_text)
    if fiscal_match:
        metadata["fiscal_year_end"] = fiscal_match.group(1)
    return metadata, metrics


def looks_like_control_table(table: Tag) -> bool:
    classes = set(table.get("class") or [])
    if classes & CONTROL_CLASS_TOKENS:
        return True
    if table.get("id") == "draggable-table-head":
        return True
    return False


def looks_like_placeholder(df: pd.DataFrame) -> bool:
    values = [clean_text(x) for x in df.astype(str).to_numpy().ravel()]
    non_empty = [v for v in values if v and v.lower() != "nan"]
    if not non_empty:
        return True
    repeated_4232 = sum(1 for v in non_empty if v.replace(",", "") == "4232")
    return repeated_4232 / max(len(non_empty), 1) > 0.8


def section_from_control_table(table: Tag) -> str:
    text = clean_text(table.get_text(" "))
    for label in [
        "투자분석",
        "가치분석",
        "재무분석",
        "재무상태표",
        "손익계산서",
        "현금흐름표",
        "컨센서스 추이",
        "밴드차트",
        "어닝서프라이즈",
    ]:
        if label in text:
            return label
    return ""


def infer_table_title(page_label: str, table: Tag, order: int, current_section: str) -> str:
    table_id = table.get("id") or ""
    if table_id in KNOWN_TABLE_TITLES:
        return KNOWN_TABLE_TITLES[table_id]
    if "data-list" in (table.get("class") or []):
        return current_section or f"{page_label} 데이터"
    if table_id:
        return table_id
    return f"{page_label} 표 {order + 1}"


def parse_useful_tables(soup: BeautifulSoup, page_key: str, page_label: str) -> list[TableRecord]:
    records: list[TableRecord] = []
    current_section = ""
    order = 0

    for table in soup.find_all("table"):
        if "cmp-table" in (table.get("class") or []):
            continue

        if looks_like_control_table(table):
            current_section = section_from_control_table(table) or current_section
            continue

        df = table_to_dataframe(table)
        if df is None or looks_like_placeholder(df):
            continue

        first_col = clean_text(df.columns[0] if len(df.columns) else "")
        first_cell = clean_text(df.iloc[0, 0] if not df.empty else "")
        has_table_shape = len(df) >= 2 and len(df.columns) >= 2
        if not has_table_shape:
            continue
        if first_col == first_cell and len(df) <= 2:
            continue

        title = infer_table_title(page_label, table, order, current_section)
        records.append(
            TableRecord(
                page_key=page_key,
                page_label=page_label,
                title=title,
                table_id=table.get("id") or "",
                order=order,
                dataframe=df,
            )
        )
        order += 1

    return records


def scrape_stock(
    code: str | int,
    pages: Iterable[str] | None = None,
    session: requests.Session | None = None,
    render_js: bool = False,
    wait_seconds: float = 2.0,
    chrome_binary: str | None = None,
    driver_path: str | None = None,
) -> StockBundle:
    if requests is None or BeautifulSoup is None:
        raise ModuleNotFoundError("Install scraper dependencies with: pip install -r requirements.txt")

    normalized_code = normalize_code(code)
    owned_session = session is None
    session = session or requests.Session()
    session.headers.update(HEADERS)
    selected_pages = list(pages or DEFAULT_PAGES.keys())
    bundle = StockBundle(code=normalized_code)
    driver = None

    try:
        if render_js:
            driver = create_chrome_driver(
                headless=True,
                chrome_binary=chrome_binary,
                driver_path=driver_path,
            )

        for page_key in selected_pages:
            page_code = DEFAULT_PAGES[page_key]
            page_label = PAGE_LABELS.get(page_key, page_key)
            url = BASE_URL.format(page=page_code, code=normalized_code)
            try:
                html = render_html(driver, url, wait_seconds=wait_seconds) if render_js else fetch_html(session, url)
            except Exception as exc:
                bundle.errors[page_key] = str(exc)
                continue

            soup = BeautifulSoup(html, "html.parser")
            metadata, metrics = parse_company_header(soup)
            bundle.metadata.update({k: v for k, v in metadata.items() if v})
            bundle.headline_metrics.update({k: v for k, v in metrics.items() if v})
            if not bundle.company_name and metadata.get("company_name"):
                bundle.company_name = metadata["company_name"]

            bundle.tables.extend(parse_useful_tables(soup, page_key, page_label))
    finally:
        if driver is not None:
            driver.quit()
        if owned_session:
            session.close()

    return bundle


def fetch_peer_comparison(code: str | int, session: requests.Session | None = None) -> pd.DataFrame:
    if requests is None:
        raise ModuleNotFoundError("Install scraper dependencies with: pip install -r requirements.txt")

    normalized_code = normalize_code(code)
    owned_session = session is None
    session = session or requests.Session()
    session.headers.update(HEADERS)
    params = {
        "cmp_cd": normalized_code,
        "finGubun": "MAIN",
        "sec_cd": "FG000",
        "frq": "Y",
        "cmp_cd1": "",
        "cmp_cd2": "",
        "cmp_cd3": "",
        "cmp_cd4": "",
    }

    try:
        header_response = session.get(PEER_HEADER_URL, params=params, timeout=15)
        header_response.raise_for_status()
        header_items = header_response.json().get("oDt_header", [])
        headers = [
            {
                "code": clean_text(item.get("CMP_CD")),
                "name": clean_text(item.get("CMP_KOR")),
                "market_cap": item.get("MKT_VAL"),
            }
            for item in header_items
            if clean_text(item.get("CMP_CD")) and clean_text(item.get("CMP_KOR"))
        ]
        if not headers:
            return pd.DataFrame()

        table_response = session.get(
            PEER_TABLE_URL,
            params={"cmp_cd": normalized_code, "finGubun": "MAIN", "sec_cd": "FG000", "frq": "Y"},
            timeout=15,
        )
        table_response.raise_for_status()
        dfs = pd.read_html(StringIO(table_response.text), displayed_only=False)
        if not dfs:
            return pd.DataFrame()
        raw = flatten_columns(dfs[0])
    finally:
        if owned_session:
            session.close()

    value_cols = list(raw.columns[1 : 1 + len(headers)])

    def row_value(label: str, col: object) -> float | None:
        label_col = raw.columns[0]
        match = raw[raw[label_col].map(clean_text) == label]
        if match.empty:
            return None
        return pd.to_numeric(match.iloc[0][col], errors="coerce")

    rows: list[dict[str, object]] = []
    for header, col in zip(headers, value_cols):
        rows.append(
            {
                "기업명": header["name"],
                "종목코드": header["code"],
                "현재가": row_value("전일종가(원)", col),
                "PER": row_value("PER", col),
                "PBR": row_value("PBR", col),
                "시가총액": row_value("시가총액(억원)", col) or header["market_cap"],
                "출처": "업종분석",
            }
        )
    return pd.DataFrame(rows)
