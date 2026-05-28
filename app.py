from __future__ import annotations

import hashlib
from pathlib import Path
import html
import pickle
import re
import sys
import time
from urllib.parse import urljoin

import pandas as pd
import plotly.express as px
import requests
import streamlit as st
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from valuation import find_metric, to_float
from wisereport_scraper import (
    DEFAULT_PAGES,
    PAGE_LABELS,
    StockBundle,
    TableRecord,
    clean_text,
    fetch_peer_comparison,
    scrape_stock,
)


APP_TITLE = "FIS 1팀 Unit2(김다인 김인환 정시윤)"
CACHE_DIR = ROOT / ".fis_cache"
CACHE_TTL_SECONDS = 60 * 60 * 24 * 7
STOCK_UNIVERSE_TTL_SECONDS = 60 * 60 * 24 * 30
KNOWN_STOCK_CODES = {
    "삼성전자": "005930",
    "삼전": "005930",
    "SK하이닉스": "000660",
    "에스케이하이닉스": "000660",
    "하이닉스": "000660",
    "현대차": "005380",
    "현대자동차": "005380",
    "기아": "000270",
    "NAVER": "035420",
    "네이버": "035420",
    "카카오": "035720",
    "LG전자": "066570",
    "엘지전자": "066570",
    "LG화학": "051910",
    "엘지화학": "051910",
    "삼성SDI": "006400",
    "셀트리온": "068270",
    "삼성바이오로직스": "207940",
    "POSCO홀딩스": "005490",
    "포스코홀딩스": "005490",
    "현대모비스": "012330",
    "KB금융": "105560",
    "신한지주": "055550",
    "오리온홀딩스": "001800",
    "오리온": "271560",
}

st.set_page_config(page_title=APP_TITLE, layout="wide")

st.markdown(
    """
    <style>
    :root {
        --fis-bg: #050914;
        --fis-panel: #0b1220;
        --fis-panel-soft: #0e1a2c;
        --fis-border: rgba(78, 221, 194, 0.22);
        --fis-border-strong: rgba(25, 230, 195, 0.42);
        --fis-text: #eef7ff;
        --fis-muted: #92a6bb;
        --fis-mint: #19e6c3;
        --fis-cyan: #2bb7ff;
        --fis-warn: #f7c948;
    }

    .stApp {
        background:
            radial-gradient(circle at 16% 14%, rgba(25, 230, 195, 0.14), transparent 28%),
            radial-gradient(circle at 82% 18%, rgba(43, 183, 255, 0.10), transparent 24%),
            linear-gradient(135deg, #050914 0%, #07111f 42%, #050914 100%);
        color: var(--fis-text);
    }

    header[data-testid="stHeader"],
    div[data-testid="stToolbar"],
    #MainMenu,
    footer {
        display: none;
    }

    .block-container {
        max-width: none;
        padding-left: 1.5rem;
        padding-right: 1.5rem;
        padding-top: 1.1rem;
        padding-bottom: 3rem;
    }

    [data-testid="stMarkdownContainer"] h1,
    [data-testid="stMarkdownContainer"] h2,
    [data-testid="stMarkdownContainer"] h3 {
        letter-spacing: 0;
    }

    .fis-topbar {
        display: flex;
        align-items: center;
        gap: 14px;
        min-height: 76px;
        padding: 14px 0;
        overflow: visible;
    }

    .fis-logo {
        width: 56px;
        min-width: 56px;
        height: 56px;
        border-radius: 16px;
        display: grid;
        place-items: center;
        font-weight: 900;
        color: #04111c;
        background: linear-gradient(135deg, var(--fis-mint), var(--fis-cyan));
        box-shadow: 0 0 24px rgba(25, 230, 195, 0.38);
        overflow: visible;
        line-height: 1;
    }

    .fis-brand-title {
        font-size: clamp(16px, 1.8vw, 22px);
        font-weight: 900;
        color: var(--fis-text);
        line-height: 1.34;
        padding-top: 2px;
        word-break: keep-all;
        overflow: visible;
    }

    .fis-brand-subtitle {
        margin-top: 5px;
        color: var(--fis-muted);
        font-size: 12px;
        letter-spacing: 1.6px;
        text-transform: uppercase;
    }

    .fis-hero {
        margin: 18px 0 20px;
        padding: clamp(26px, 4vw, 40px);
        border: 1px solid var(--fis-border);
        border-radius: 22px;
        background:
            linear-gradient(120deg, rgba(15, 118, 110, 0.34), rgba(8, 15, 31, 0.88) 48%),
            linear-gradient(160deg, rgba(16, 29, 47, 0.96), rgba(5, 9, 20, 0.92));
        box-shadow: 0 18px 50px rgba(0, 0, 0, 0.34);
        overflow: visible;
    }

    .fis-eyebrow {
        color: var(--fis-mint);
        font-size: 12px;
        font-weight: 900;
        letter-spacing: 2.2px;
        text-transform: uppercase;
        margin-bottom: 14px;
    }

    .fis-hero-title {
        font-size: clamp(34px, 5vw, 56px);
        line-height: 1.08;
        font-weight: 950;
        color: var(--fis-text);
        max-width: 780px;
        overflow: visible;
    }

    .fis-hero-copy {
        color: #c7d5e6;
        max-width: 770px;
        line-height: 1.72;
        margin-top: 22px;
        font-size: 15px;
    }

    .fis-live {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        color: var(--fis-muted);
        font-size: 12px;
        letter-spacing: 1.4px;
        text-transform: uppercase;
        margin-top: 22px;
    }

    .fis-live-dot {
        width: 8px;
        height: 8px;
        border-radius: 999px;
        background: var(--fis-mint);
        box-shadow: 0 0 14px var(--fis-mint);
    }

    .fis-chip-row {
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
        margin-top: 24px;
    }

    .fis-chip {
        border: 1px solid rgba(25, 230, 195, 0.26);
        background: rgba(25, 230, 195, 0.08);
        color: #bffcf0;
        border-radius: 999px;
        padding: 8px 14px;
        font-size: 12px;
        font-weight: 800;
        white-space: nowrap;
    }

    .fis-summary {
        margin: 18px 0 16px;
        border: 1px solid rgba(25, 230, 195, 0.20);
        border-radius: 16px;
        background: rgba(7, 13, 27, 0.82);
        padding: 22px 24px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 18px;
        overflow: visible;
    }

    .fis-company-line {
        display: flex;
        align-items: center;
        flex-wrap: wrap;
        gap: 12px;
    }

    .fis-company-name {
        color: var(--fis-text);
        font-size: clamp(24px, 2.4vw, 34px);
        line-height: 1.18;
        font-weight: 950;
    }

    .fis-price {
        color: var(--fis-mint);
        font-size: 18px;
        font-weight: 950;
    }

    .fis-target {
        color: var(--fis-mint);
        font-size: clamp(18px, 1.9vw, 26px);
        font-weight: 950;
        text-align: right;
        white-space: nowrap;
    }

    .fis-pill {
        border: 1px solid rgba(25, 230, 195, 0.32);
        background: rgba(25, 230, 195, 0.10);
        color: #c9fff3;
        border-radius: 999px;
        padding: 6px 10px;
        font-size: 12px;
        font-weight: 900;
    }

    .fis-panel {
        border: 1px solid rgba(146, 166, 187, 0.16);
        border-radius: 16px;
        background: rgba(14, 26, 44, 0.64);
        padding: 20px;
        min-height: 100%;
    }

    .fis-panel-title {
        color: var(--fis-text);
        font-size: 16px;
        font-weight: 950;
        margin-bottom: 14px;
    }

    .fis-dot-title {
        display: flex;
        gap: 10px;
        align-items: center;
        color: var(--fis-text);
        font-weight: 950;
        margin-bottom: 12px;
    }

    .fis-dot-title::before {
        content: "";
        width: 8px;
        height: 8px;
        border-radius: 999px;
        background: var(--fis-mint);
        box-shadow: 0 0 12px var(--fis-mint);
    }

    .fis-note {
        color: var(--fis-muted);
        font-size: 12px;
        line-height: 1.6;
    }

    .fis-table {
        width: 100%;
        border-collapse: collapse;
        overflow: hidden;
        border-radius: 14px;
        background: rgba(8, 15, 31, 0.72);
        color: #cfe8ff;
        font-size: 14px;
    }

    .fis-table th {
        background: rgba(25, 39, 65, 0.86);
        color: #9fc0ee;
        font-weight: 800;
        padding: 12px 14px;
        text-align: right;
        border-bottom: 1px solid rgba(146, 166, 187, 0.18);
    }

    .fis-table th:first-child,
    .fis-table td:first-child {
        text-align: left;
    }

    .fis-table td {
        padding: 12px 14px;
        border-bottom: 1px solid rgba(146, 166, 187, 0.08);
        text-align: right;
    }

    .fis-table tr:nth-child(even) td {
        background: rgba(25, 230, 195, 0.035);
    }

    .fis-table strong {
        color: var(--fis-mint);
    }

    .fis-card {
        border: 1px solid rgba(146, 166, 187, 0.16);
        border-radius: 16px;
        background: rgba(14, 26, 44, 0.76);
        padding: 18px;
        min-height: 100%;
        overflow: visible;
    }

    .fis-card-title {
        color: var(--fis-muted);
        font-size: 12px;
        font-weight: 800;
        letter-spacing: 1.2px;
        text-transform: uppercase;
        margin-bottom: 10px;
    }

    .fis-card-main {
        color: var(--fis-text);
        font-size: clamp(20px, 2.3vw, 30px);
        line-height: 1.18;
        font-weight: 900;
        overflow-wrap: anywhere;
        overflow: visible;
    }

    .fis-card-sub {
        margin-top: 8px;
        color: var(--fis-muted);
        font-size: 13px;
        line-height: 1.5;
        overflow-wrap: anywhere;
    }

    .fis-stat-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
        gap: 12px;
        margin: 12px 0 18px;
        overflow: visible;
    }

    .fis-stat {
        border: 1px solid rgba(146, 166, 187, 0.16);
        border-radius: 14px;
        background: rgba(14, 26, 44, 0.76);
        padding: 14px 16px;
        min-height: 88px;
        overflow: visible;
    }

    .fis-stat-label {
        color: var(--fis-muted);
        font-size: 12px;
        font-weight: 800;
        letter-spacing: 0.8px;
        margin-bottom: 8px;
        white-space: normal;
    }

    .fis-stat-value {
        color: var(--fis-text);
        font-size: clamp(19px, 2vw, 28px);
        line-height: 1.16;
        font-weight: 900;
        overflow-wrap: anywhere;
        overflow: visible;
    }

    .fis-stat-note {
        color: var(--fis-muted);
        font-size: 12px;
        margin-top: 6px;
        line-height: 1.35;
    }

    .fis-section-label {
        color: var(--fis-mint);
        font-size: 12px;
        font-weight: 900;
        letter-spacing: 1.8px;
        text-transform: uppercase;
        margin: 12px 0 8px;
    }

    div[data-testid="stTextInput"] input,
    div[data-testid="stNumberInput"] input,
    div[data-baseweb="select"] > div {
        background-color: rgba(8, 15, 31, 0.88);
        color: var(--fis-text);
        border-color: rgba(146, 166, 187, 0.22);
    }

    .stButton > button {
        border-radius: 14px;
        border: 1px solid rgba(25, 230, 195, 0.4);
        background: linear-gradient(135deg, var(--fis-mint), var(--fis-cyan));
        color: #04111c;
        font-weight: 900;
        min-height: 46px;
    }

    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        flex-wrap: wrap;
    }

    .stTabs [data-baseweb="tab"] {
        background: rgba(14, 26, 44, 0.72);
        border: 1px solid rgba(146, 166, 187, 0.14);
        border-radius: 12px;
        color: var(--fis-muted);
        padding: 10px 14px;
    }

    .stTabs [aria-selected="true"] {
        color: var(--fis-text);
        border-color: var(--fis-border-strong);
        background: rgba(25, 230, 195, 0.12);
    }

    div[data-testid="stMetric"] {
        overflow: visible;
    }

    div[data-testid="stMetricValue"] {
        font-size: clamp(18px, 2vw, 28px);
        line-height: 1.18;
        overflow-wrap: anywhere;
        overflow: visible;
        white-space: normal;
    }

    div[data-testid="stDataFrame"] {
        border-radius: 14px;
        overflow: hidden;
    }

    .fis-news-list {
        display: grid;
        grid-template-columns: minmax(0, 1fr);
        gap: 12px;
    }

    .fis-news-card {
        display: block;
        padding: 18px 20px;
        border: 1px solid rgba(120, 150, 190, 0.22);
        border-radius: 14px;
        background: rgba(10, 17, 32, 0.86);
        color: var(--fis-text) !important;
        text-decoration: none !important;
        transition: border-color 0.15s ease, transform 0.15s ease, background 0.15s ease;
    }

    .fis-news-card:hover {
        border-color: var(--fis-border-strong);
        background: rgba(12, 25, 43, 0.96);
        transform: translateY(-1px);
    }

    .fis-news-title {
        font-size: 15px;
        font-weight: 800;
        line-height: 1.45;
        overflow-wrap: anywhere;
    }

    .fis-news-meta {
        margin-top: 9px;
        color: var(--fis-muted);
        font-size: 12px;
        letter-spacing: 0;
    }

    @media (max-width: 760px) {
        .block-container {
            padding-top: 0.9rem;
        }
        .fis-topbar {
            align-items: flex-start;
        }
        .fis-brand-title {
            font-size: 15px;
        }
        .fis-chip {
            white-space: normal;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(show_spinner=False, ttl=60 * 30)
def cached_scrape_stock(code: str, pages: tuple[str, ...], render_js: bool) -> StockBundle:
    return scrape_stock(code, pages=pages, render_js=render_js)


@st.cache_data(show_spinner=False, ttl=60 * 30)
def cached_peer_comparison_table(code: str) -> pd.DataFrame:
    return fetch_peer_comparison(code)


@st.cache_data(show_spinner=False, ttl=60 * 5)
def fetch_related_news(code: str, limit: int = 12) -> tuple[pd.DataFrame, str | None]:
    try:
        response = requests.get(
            "https://finance.naver.com/item/news_news.naver",
            params={"code": code, "page": 1, "sm": "title_entity_id.basic"},
            headers={"User-Agent": "Mozilla/5.0", "Referer": "https://finance.naver.com/"},
            timeout=12,
        )
        response.raise_for_status()
        response.encoding = "euc-kr"
    except Exception as exc:
        return pd.DataFrame(), str(exc)

    soup = BeautifulSoup(response.text, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for row in soup.select("table.type5 tr"):
        link = row.select_one("td.title a")
        if not link:
            continue
        title = clean_text(link.get_text())
        href = urljoin("https://finance.naver.com", link.get("href", ""))
        publisher = clean_text(row.select_one("td.info").get_text() if row.select_one("td.info") else "")
        published_at = clean_text(row.select_one("td.date").get_text() if row.select_one("td.date") else "")
        if not title or href in seen:
            continue
        seen.add(href)
        rows.append({"제목": title, "언론사": publisher, "날짜": published_at, "링크": href})
        if len(rows) >= limit:
            break
    return pd.DataFrame(rows), None


def cache_path(prefix: str, *parts: object) -> Path:
    CACHE_DIR.mkdir(exist_ok=True)
    raw = "|".join(str(part) for part in parts)
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:18]
    return CACHE_DIR / f"{prefix}_{digest}.pkl"


def load_pickle_cache(path: Path, ttl_seconds: int = CACHE_TTL_SECONDS):
    if not path.exists():
        return None
    if time.time() - path.stat().st_mtime > ttl_seconds:
        return None
    try:
        with path.open("rb") as file:
            return pickle.load(file)
    except Exception:
        return None


def save_pickle_cache(path: Path, value: object) -> None:
    path.parent.mkdir(exist_ok=True)
    with path.open("wb") as file:
        pickle.dump(value, file)


def normalize_lookup_name(value: object) -> str:
    return re.sub(r"[^0-9A-Z가-힣]", "", clean_text(value).upper())


def fetch_stock_universe() -> list[dict[str, str]]:
    cached = load_pickle_cache(cache_path("stock_universe", "naver_market_sum"), ttl_seconds=STOCK_UNIVERSE_TTL_SECONDS)
    if cached:
        return cached

    rows: list[dict[str, str]] = []
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    for market_id, market_name in (("0", "KOSPI"), ("1", "KOSDAQ")):
        for page in range(1, 90):
            response = requests.get(
                "https://finance.naver.com/sise/sise_market_sum.naver",
                params={"sosok": market_id, "page": page},
                headers=headers,
                timeout=12,
            )
            response.raise_for_status()
            response.encoding = response.apparent_encoding or response.encoding
            soup = BeautifulSoup(response.text, "html.parser")
            anchors = soup.select("a.tltle")
            if not anchors:
                break
            for anchor in anchors:
                match = re.search(r"code=(\d{6})", anchor.get("href", ""))
                name = clean_text(anchor.get_text())
                if match and name:
                    rows.append({"name": name, "code": match.group(1), "market": market_name})

    if rows:
        save_pickle_cache(cache_path("stock_universe", "naver_market_sum"), rows)
    return rows


def lookup_stock_code_from_name(value: str) -> tuple[str | None, str]:
    lookup = normalize_lookup_name(value)
    if not lookup:
        return None, "미확인"
    try:
        rows = fetch_stock_universe()
    except Exception:
        return None, "검색 실패"

    for row in rows:
        if normalize_lookup_name(row.get("name")) == lookup:
            return row["code"], "기업명 검색"
    for row in rows:
        row_name = normalize_lookup_name(row.get("name"))
        if lookup in row_name or row_name in lookup:
            return row["code"], "기업명 검색"
    return None, "미확인"


def resolve_stock_code(value: str, allow_online_lookup: bool = False) -> tuple[str | None, str]:
    text = clean_text(value)
    digits = re.sub(r"\D", "", text)
    if len(digits) >= 6:
        return digits.zfill(6)[-6:], "종목코드"

    lookup = normalize_lookup_name(text)
    for name, code in KNOWN_STOCK_CODES.items():
        if normalize_lookup_name(name) == lookup:
            return code, "종목명"
    if allow_online_lookup:
        return lookup_stock_code_from_name(text)
    return None, "미확인"


def load_stock_bundle(
    code: str,
    pages: tuple[str, ...],
    render_js: bool,
    use_saved_data: bool,
    force_refresh: bool,
) -> tuple[StockBundle, str]:
    stock_cache = cache_path("stock", code, ",".join(pages), render_js)
    rich_cache = cache_path("stock", code, ",".join(pages), True)
    fallback_cache = cache_path("stock", code, ",".join(pages), False)
    candidates = [rich_cache, stock_cache, fallback_cache]

    def read_saved_bundle() -> StockBundle | None:
        seen_candidates: set[Path] = set()
        for candidate in candidates:
            if candidate in seen_candidates:
                continue
            seen_candidates.add(candidate)
            cached = load_pickle_cache(candidate)
            if cached is not None and getattr(cached, "tables", None):
                return cached
        return None

    if use_saved_data and not force_refresh:
        cached = read_saved_bundle()
        if cached is not None:
            return cached, "저장 데이터"

    mode = "신규 수집"
    scrape_error: Exception | None = None
    try:
        bundle = scrape_stock(code, pages=pages, render_js=render_js)
    except Exception as exc:
        scrape_error = exc
        if render_js:
            try:
                bundle = scrape_stock(code, pages=pages, render_js=False)
                bundle.errors["dynamic_tables"] = "동적 표 수집 권한 문제로 일반 수집으로 전환했습니다."
                mode = "일반 수집 전환"
            except Exception as fallback_exc:
                scrape_error = fallback_exc
                bundle = StockBundle(code=code)
                bundle.errors["network"] = str(fallback_exc)
        else:
            bundle = StockBundle(code=code)
            bundle.errors["network"] = str(exc)

    if use_saved_data and not getattr(bundle, "tables", None):
        cached = read_saved_bundle()
        if cached is not None:
            return cached, "저장 데이터(새 수집 실패 후 사용)"
        if scrape_error is not None:
            bundle.errors["latest_collection"] = str(scrape_error)

    if use_saved_data and bundle.tables:
        save_pickle_cache(stock_cache if render_js else fallback_cache, bundle)
    return bundle, mode


def load_peer_comparison(code: str, use_saved_data: bool, force_refresh: bool) -> tuple[pd.DataFrame, str]:
    peer_cache = cache_path("peers", code)
    cached = load_pickle_cache(peer_cache) if use_saved_data else None
    if cached is not None and not cached.empty and not force_refresh:
        return cached, "저장 데이터"

    try:
        df = fetch_peer_comparison(code)
    except Exception:
        if cached is not None and not cached.empty:
            return cached, "저장 데이터(새 수집 실패 후 사용)"
        raise
    if df.empty and cached is not None and not cached.empty:
        return cached, "저장 데이터(새 수집 실패 후 사용)"
    if use_saved_data and not df.empty:
        save_pickle_cache(peer_cache, df)
    return df, "신규 수집"


def esc(value: object) -> str:
    return html.escape(str(value if value is not None else ""))


def format_value(value: object, suffix: str = "") -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        if abs(value) >= 100:
            return f"{value:,.0f}{suffix}"
        return f"{value:,.2f}{suffix}"
    text = str(value).strip()
    return f"{text}{suffix}" if text else "-"


def render_stat_cards(items: list[tuple[str, object, str]]) -> None:
    if not items:
        return
    cards = []
    for label, value, note in items:
        cards.append(
            "<div class='fis-stat'>"
            f"<div class='fis-stat-label'>{esc(label)}</div>"
            f"<div class='fis-stat-value'>{esc(value)}</div>"
            f"<div class='fis-stat-note'>{esc(note)}</div>"
            "</div>"
        )
    st.markdown(f"<div class='fis-stat-grid'>{''.join(cards)}</div>", unsafe_allow_html=True)


def render_info_card(title: str, main: object, sub: str = "") -> None:
    st.markdown(
        "<div class='fis-card'>"
        f"<div class='fis-card-title'>{esc(title)}</div>"
        f"<div class='fis-card-main'>{esc(main)}</div>"
        f"<div class='fis-card-sub'>{esc(sub)}</div>"
        "</div>",
        unsafe_allow_html=True,
    )


def numeric_plot_frame(df: pd.DataFrame, row_label_col: str, selected_rows: list[str]) -> pd.DataFrame:
    rows = df[df[row_label_col].astype(str).isin(selected_rows)].copy()
    if rows.empty:
        return pd.DataFrame()
    long = rows.melt(id_vars=[row_label_col], var_name="period", value_name="value")
    long["value"] = long["value"].map(to_float)
    return long.dropna(subset=["value"])


def first_table(bundle: StockBundle, *keywords: str) -> TableRecord | None:
    lowered = [keyword.lower() for keyword in keywords]
    for record in bundle.tables:
        haystack = f"{record.page_label} {record.title} {record.table_id}".lower()
        if all(keyword in haystack for keyword in lowered):
            return record
    return None


def page_tables(bundle: StockBundle, page_key: str) -> list[TableRecord]:
    return [record for record in bundle.tables if record.page_key == page_key]


def find_consensus_summary(bundle: StockBundle) -> TableRecord | None:
    for record in page_tables(bundle, "consensus"):
        df = record.dataframe
        if record.table_id == "cTB511" or "컨센서스 재무요약" in record.title:
            return record
        if df.empty or len(df.columns) < 4:
            continue
        cols = " ".join(clean_text(col) for col in df.columns)
        if "재무연월" in cols and "매출액" in cols and "영업이익" in cols:
            return record
    return None


def find_consensus_trend(bundle: StockBundle) -> TableRecord | None:
    for record in page_tables(bundle, "consensus"):
        if record.table_id == "cTB512" or "컨센서스 추이" in record.title:
            return record
    return None


def find_financial_record(bundle: StockBundle) -> TableRecord | None:
    required = ("매출액", "영업이익")
    preferred_pages = ("financial_analysis", "company_status", "consensus")
    for page_key in preferred_pages:
        for record in page_tables(bundle, page_key):
            df = record.dataframe
            if df.empty or len(df.columns) < 2:
                continue
            first_col = df.columns[0]
            labels = " ".join(clean_text(value) for value in df[first_col].head(80))
            if all(keyword in labels for keyword in required):
                return record
            cols = " ".join(clean_text(col) for col in df.columns)
            if all(keyword in cols for keyword in required):
                return record
    return first_table(bundle, "재무요약") or first_table(bundle, "컨센서스")


def metric_hit(bundle: StockBundle, metric: str, period: str):
    return find_metric(bundle.tables, metric, period, ["investment_indicators", "consensus"])


VALUATION_INDICATORS = [
    "매출총이익률",
    "영업이익률",
    "순이익률",
    "EBITDA마진율",
    "ROE",
    "ROA",
    "ROIC",
    "현금배당수익률",
    "현금배당성향",
]


def normalize_indicator_name(value: object) -> str:
    text = clean_text(value)
    text = text.replace("펼치기", "").strip()
    text = re.sub(r"\(.*?\)", "", text)
    text = text.replace(" ", "")
    return text.upper()


def extract_wisereport_indicators(bundle: StockBundle) -> pd.DataFrame:
    rows_by_indicator: dict[str, dict[str, object]] = {}
    targets = {normalize_indicator_name(indicator): indicator for indicator in VALUATION_INDICATORS}

    for record in page_tables(bundle, "investment_indicators"):
        df = record.dataframe
        if df.empty or len(df.columns) < 2:
            continue
        label_col = df.columns[0]
        for _, row in df.iterrows():
            source_name = normalize_indicator_name(row[label_col])
            target = targets.get(source_name)
            if target is None:
                continue
            if target in rows_by_indicator:
                continue

            extracted: dict[str, object] = {"지표": target}
            for col in df.columns[1:]:
                col_name = clean_text(col)
                if not col_name or "전년대비" in col_name:
                    continue
                extracted[col_name] = row[col]
            extracted["출처"] = record.title
            rows_by_indicator[target] = extracted

    rows = [rows_by_indicator.get(indicator, {"지표": indicator, "출처": "-"}) for indicator in VALUATION_INDICATORS]
    return pd.DataFrame(rows)


def indicator_period_columns(indicator_df: pd.DataFrame) -> list[str]:
    return [col for col in indicator_df.columns if col not in {"지표", "출처"}]


def indicator_value(indicator_df: pd.DataFrame, indicator: str, period: str) -> float | None:
    if indicator_df.empty or period not in indicator_df.columns:
        return None
    row = indicator_df[indicator_df["지표"] == indicator]
    if row.empty:
        return None
    return to_float(row.iloc[0][period])


def parse_codes(text: str) -> list[str]:
    codes: list[str] = []
    for token in text.replace("\n", ",").replace(" ", ",").split(","):
        digits = "".join(ch for ch in token if ch.isdigit())
        if digits:
            code = digits.zfill(6)[-6:]
            if code not in codes:
                codes.append(code)
    return codes


@st.cache_data(show_spinner=False, ttl=60 * 30)
def cached_peer_indicators(codes: tuple[str, ...], period_pages: tuple[str, ...], render_js: bool) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for code in codes:
        peer_bundle = scrape_stock(code, pages=period_pages, render_js=render_js)
        peer_df = extract_wisereport_indicators(peer_bundle)
        rows.append(
            {
                "code": code,
                "name": peer_bundle.company_name or code,
                "bundle": peer_bundle,
                "indicators": peer_df,
            }
        )
    return rows


def forward_valuation_rows(
    bundle: StockBundle,
    period: str,
    per_multiple: float,
    pbr_multiple: float,
    ev_ebitda_multiple: float,
    ebitda_per_share: float,
    net_debt_per_share: float,
    dcf_target: float,
    weights: dict[str, float],
) -> tuple[pd.DataFrame, float | None, float]:
    eps_hit = metric_hit(bundle, "EPS", period)
    bps_hit = metric_hit(bundle, "BPS", period)
    rows: list[dict[str, object]] = []

    def add_row(method: str, basis: str, value: float | None, multiplier: object, target: float | None, formula: str) -> None:
        rows.append(
            {
                "방식": method,
                "기준 지표": basis,
                "지표값": value,
                "적용 값": multiplier,
                "목표주가": None if target is None else round(target, 2),
                "비중(%)": weights.get(method, 0.0),
                "산식": formula,
            }
        )

    per_target = eps_hit.value * per_multiple if eps_hit and per_multiple > 0 else None
    add_row("PER", "EPS", eps_hit.value if eps_hit else None, per_multiple, per_target, "EPS x PER")

    pbr_target = bps_hit.value * pbr_multiple if bps_hit and pbr_multiple > 0 else None
    add_row("PBR", "BPS", bps_hit.value if bps_hit else None, pbr_multiple, pbr_target, "BPS x PBR")

    ev_ebitda_target = None
    if ebitda_per_share > 0 and ev_ebitda_multiple > 0:
        ev_ebitda_target = ebitda_per_share * ev_ebitda_multiple - net_debt_per_share
    add_row(
        "EV/EBITDA",
        "EBITDA/주",
        ebitda_per_share if ebitda_per_share > 0 else None,
        ev_ebitda_multiple,
        ev_ebitda_target,
        "EBITDA/주 x EV/EBITDA - 순차입금/주",
    )

    add_row("DCF", "DCF 목표주가", dcf_target if dcf_target > 0 else None, "직접/모델", dcf_target if dcf_target > 0 else None, "DCF 산출값")

    weighted_sum = 0.0
    weight_sum = 0.0
    for row in rows:
        target = to_float(row["목표주가"])
        weight = max(float(row["비중(%)"] or 0.0), 0.0)
        if target is None or weight <= 0:
            continue
        weighted_sum += target * weight
        weight_sum += weight

    target_price = weighted_sum / weight_sum if weight_sum else None
    return pd.DataFrame(rows), target_price, weight_sum


def dcf_value(cash_flow: float | None, growth_pct: float, discount_pct: float, terminal_growth_pct: float, years: int):
    if cash_flow is None or cash_flow <= 0:
        return None, pd.DataFrame(), {}
    growth = growth_pct / 100
    discount = discount_pct / 100
    terminal_growth = terminal_growth_pct / 100
    if discount <= terminal_growth:
        return None, pd.DataFrame(), {}

    rows = []
    forecast_pv = 0.0
    current_cf = cash_flow
    for year in range(1, years + 1):
        current_cf *= 1 + growth
        discount_factor = 1 / ((1 + discount) ** year)
        discounted = current_cf * discount_factor
        forecast_pv += discounted
        rows.append(
            {
                "구분": "예측 FCF",
                "연도": f"{year}년",
                "FCF/주": current_cf,
                "할인계수": discount_factor,
                "현재가치": discounted,
            }
        )

    terminal_value = current_cf * (1 + terminal_growth) / (discount - terminal_growth)
    terminal_pv = terminal_value / ((1 + discount) ** years)
    present_value = forecast_pv + terminal_pv
    rows.append(
        {
            "구분": "Terminal Value",
            "연도": "Terminal",
            "FCF/주": terminal_value,
            "할인계수": 1 / ((1 + discount) ** years),
            "현재가치": terminal_pv,
        }
    )
    return present_value, pd.DataFrame(rows), {
        "forecast_pv": forecast_pv,
        "terminal_value": terminal_value,
        "terminal_pv": terminal_pv,
    }


def dcf_sensitivity(cash_flow: float | None, growth_pct: float, discount_pct: float, terminal_growth_pct: float, years: int) -> pd.DataFrame:
    if cash_flow is None or cash_flow <= 0:
        return pd.DataFrame()
    discount_cases = [discount_pct - 1.0, discount_pct, discount_pct + 1.0]
    growth_cases = [terminal_growth_pct - 0.5, terminal_growth_pct, terminal_growth_pct + 0.5]
    rows = []
    for discount_case in discount_cases:
        row: dict[str, object] = {"WACC": f"{discount_case:.1f}%"}
        for growth_case in growth_cases:
            value, _, _ = dcf_value(cash_flow, growth_pct, discount_case, growth_case, years)
            row[f"g {growth_case:.1f}%"] = None if value is None else round(value, 0)
        rows.append(row)
    return pd.DataFrame(rows)


def html_table(df: pd.DataFrame) -> None:
    safe_df = df.copy()
    if not safe_df.empty and len(safe_df.columns) > 1:
        check = safe_df.replace({"": pd.NA, "-": pd.NA, "nan": pd.NA, "NaN": pd.NA})
        data_cols = list(safe_df.columns[1:])
        keep_rows = check[data_cols].notna().any(axis=1)
        safe_df = safe_df.loc[keep_rows].copy()
        keep_cols = [safe_df.columns[0]]
        for col in data_cols:
            if safe_df[col].replace({"": pd.NA, "-": pd.NA, "nan": pd.NA, "NaN": pd.NA}).notna().any():
                keep_cols.append(col)
        safe_df = safe_df[keep_cols]
    safe_df = safe_df.fillna("-")
    st.markdown(safe_df.to_html(index=False, escape=True, classes="fis-table"), unsafe_allow_html=True)


def source_note(text: str) -> None:
    st.caption(f"데이터 기준: {text}")


def format_money(value: float | None, unit: str = "원") -> str:
    if value is None:
        return "-"
    return f"{value:,.0f}{unit}"


def format_pct(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value:,.1f}%"


def row_values(record: TableRecord | None, *keywords: str) -> dict[str, float]:
    if record is None or record.dataframe.empty:
        return {}
    df = record.dataframe
    label_col = df.columns[0]
    targets = [normalize_indicator_name(keyword) for keyword in keywords]

    metric_cols = [
        col
        for col in df.columns[1:]
        if any(target and target in normalize_indicator_name(col) for target in targets)
    ]
    if metric_cols:
        metric_col = metric_cols[0]
        return {
            clean_text(row[label_col]): to_float(row[metric_col])
            for _, row in df.iterrows()
            if clean_text(row[label_col])
        }

    for _, row in df.iterrows():
        label = normalize_indicator_name(row[label_col])
        if any(target and target in label for target in targets):
            return {clean_text(col): to_float(row[col]) for col in df.columns[1:]}
    return {}


def latest_number(values: dict[str, float]) -> float | None:
    for value in reversed(list(values.values())):
        if value is not None:
            return value
    return None


def period_label(value: object) -> str:
    text = clean_text(value)
    match = re.search(r"(20\d{2})[./-]?\d{0,2}.*?\(([AE])\)", text)
    if match:
        return f"{match.group(1)}{match.group(2)}"
    match = re.search(r"(20\d{2})", text)
    return match.group(1) if match else text


def summary_metric_table(
    record: TableRecord | None,
    metrics: list[tuple[str, tuple[str, ...], str]],
    include_kind: str = "all",
) -> pd.DataFrame:
    if record is None or record.dataframe.empty:
        return pd.DataFrame()
    df = record.dataframe
    period_col = df.columns[0]
    period_rows = []
    for idx, row in df.iterrows():
        raw_period = clean_text(row[period_col])
        if include_kind == "actual" and "(A)" not in raw_period:
            continue
        if include_kind == "estimate" and "(E)" not in raw_period:
            continue
        if not raw_period:
            continue
        period_rows.append((idx, period_label(raw_period)))

    rows = []
    for display, keywords, kind in metrics:
        metric_col = None
        targets = [normalize_indicator_name(keyword) for keyword in keywords]
        for col in df.columns[1:]:
            col_name = normalize_indicator_name(col)
            if any(target and target in col_name for target in targets):
                metric_col = col
                break
        if metric_col is None:
            continue
        row_out = {"항목": display}
        has_value = False
        for idx, label in period_rows:
            value = to_float(df.loc[idx, metric_col])
            if value is None:
                row_out[label] = "-"
            elif kind == "pct":
                row_out[label] = f"{value:,.1f}%"
                has_value = True
            elif kind == "multiple":
                row_out[label] = f"{value:,.2f}x"
                has_value = True
            elif kind == "won":
                row_out[label] = f"{value:,.0f}"
                has_value = True
            else:
                row_out[label] = f"{value:,.0f}" if abs(value) >= 100 else f"{value:,.1f}"
                has_value = True
        if has_value:
            rows.append(row_out)
    return pd.DataFrame(rows)


def consensus_trend_table(record: TableRecord | None) -> pd.DataFrame:
    if record is None or record.dataframe.empty:
        return pd.DataFrame()
    df = record.dataframe.copy()
    if len(df.columns) < 3:
        return pd.DataFrame()
    first_col = df.columns[0]
    keep = df[first_col].astype(str).str.contains("매출액|영업이익|순이익|EPS|목표주가|투자의견", regex=True, na=False)
    df = df.loc[keep].copy()
    if df.empty:
        return pd.DataFrame()
    df = df.rename(columns={first_col: "항목"})
    return df


def current_price_from_bundle(bundle: StockBundle) -> float | None:
    for record in page_tables(bundle, "company_status"):
        df = record.dataframe
        if df.empty or len(df.columns) < 2:
            continue
        first_col = df.columns[0]
        for _, row in df.iterrows():
            if "주가" not in clean_text(row[first_col]):
                continue
            value = to_float(clean_text(row[df.columns[1]]).split("/")[0])
            if value is not None:
                return value
    return to_float(bundle.headline_metrics.get("현재가"))


def latest_indicator_value(indicator_df: pd.DataFrame, indicator: str) -> float | None:
    if indicator_df.empty:
        return None
    row = indicator_df[indicator_df["지표"] == indicator]
    if row.empty:
        return None
    for col in reversed(indicator_period_columns(indicator_df)):
        value = to_float(row.iloc[0].get(col))
        if value is not None:
            return value
    return None


def growth_pct_from_values(values: dict[str, float]) -> float | None:
    valid = [value for value in values.values() if value is not None and value > 0]
    if len(valid) < 2:
        return None
    previous = valid[-2]
    latest = valid[-1]
    if previous == 0:
        return None
    return (latest / previous - 1) * 100


def find_earnings_date(bundle: StockBundle) -> str | None:
    keywords = ("실적발표", "발표일", "발표 예정", "IR일정", "컨퍼런스콜", "Earnings")
    date_pattern = re.compile(
        r"(20\d{2}[./-]\s*\d{1,2}[./-]\s*\d{1,2}|20\d{2}\s*년\s*\d{1,2}\s*월\s*\d{1,2}\s*일|\d{1,2}\s*월\s*\d{1,2}\s*일)"
    )
    for record in bundle.tables:
        df = record.dataframe
        if df.empty:
            continue
        for _, row in df.iterrows():
            row_text = " ".join(clean_text(value) for value in row.to_list())
            if not any(keyword.lower() in row_text.lower() for keyword in keywords):
                continue
            match = date_pattern.search(row_text)
            if match:
                return clean_text(match.group(1))
            return row_text[:80]
    return None


def valuation_gap(current_price: float, fair_price: float | None) -> tuple[float | None, str]:
    if not current_price or not fair_price:
        return None, "판단 보류"
    gap = (fair_price / current_price - 1) * 100
    if gap >= 20:
        return gap, "저평가"
    if gap >= 5:
        return gap, "소폭 저평가"
    if gap > -5:
        return gap, "적정 범위"
    if gap > -20:
        return gap, "소폭 고평가"
    return gap, "고평가"


def decision_opinion(
    gap_pct: float | None,
    roic: float | None,
    wacc: float | None,
    peg: float | None,
    eva: float | None,
    fcf_yield: float | None,
) -> tuple[str, list[str], int]:
    score = 0
    reasons: list[str] = []
    if gap_pct is not None:
        if gap_pct >= 20:
            score += 2
            reasons.append("현재가 대비 적정주가 여력이 큽니다.")
        elif gap_pct >= 5:
            score += 1
            reasons.append("현재가 대비 적정주가 여력이 있습니다.")
        elif gap_pct <= -20:
            score -= 2
            reasons.append("현재가가 적정주가보다 크게 높습니다.")
        elif gap_pct <= -5:
            score -= 1
            reasons.append("현재가가 적정주가보다 다소 높습니다.")

    if roic is not None and wacc is not None:
        if roic > wacc:
            score += 1
            reasons.append("ROIC가 WACC를 웃돌아 자본효율이 양호합니다.")
        else:
            score -= 1
            reasons.append("ROIC가 WACC보다 낮아 자본효율 확인이 필요합니다.")

    if peg is not None:
        if 0 < peg <= 1:
            score += 1
            reasons.append("PEG가 1배 이하로 성장 대비 밸류에이션 부담이 낮습니다.")
        elif peg > 2:
            score -= 1
            reasons.append("PEG가 2배를 넘어 성장 대비 밸류에이션 부담이 있습니다.")

    if eva is not None:
        if eva > 0:
            score += 1
            reasons.append("EVA가 양수로 경제적 부가가치를 만들고 있습니다.")
        else:
            score -= 1
            reasons.append("EVA가 음수로 자본비용을 넘는 이익 창출이 필요합니다.")

    if fcf_yield is not None and wacc is not None:
        if fcf_yield > wacc:
            score += 1
            reasons.append("FCF Yield가 WACC보다 높아 현금수익률이 매력적입니다.")
        elif fcf_yield < max(wacc * 0.5, 1):
            score -= 1
            reasons.append("FCF Yield가 낮아 현금흐름 매력은 제한적입니다.")

    if score >= 4:
        return "매수 검토", reasons, score
    if score >= 2:
        return "긍정 / 분할매수", reasons, score
    if score >= 0:
        return "보유 / 관찰", reasons, score
    return "관망 / 축소 검토", reasons, score


def render_decision_dashboard(
    slot,
    company_name: str,
    current_price: float,
    fair_price: float | None,
    dcf_target: float | None,
    per_target: float | None,
    pbr_target: float | None,
    ev_ebitda_target: float | None,
    wacc: float,
    cost_of_equity: float,
    ebitda: float | None,
    peg: float | None,
    roic: float | None,
    eva: float | None,
    fcf_yield: float | None,
    earnings_date: str | None,
    stock_key: str,
) -> None:
    gap_pct, gap_label = valuation_gap(current_price, fair_price)
    opinion, reasons, score = decision_opinion(gap_pct, roic, wacc, peg, eva, fcf_yield)
    with slot.container():
        st.markdown("<div class='fis-section-label'>VALUATION SIGNAL</div>", unsafe_allow_html=True)
        render_stat_cards(
            [
                ("현재가", format_money(current_price), company_name),
                ("적정주가", format_money(fair_price), f"{gap_label}{'' if gap_pct is None else f' · {gap_pct:+.1f}%'}"),
                ("모델 의견", opinion, f"판단 점수 {score:+d}"),
                ("실적 발표일", earnings_date or "확인 필요", "수집 데이터 기준"),
            ]
        )
        manual_date = st.text_input(
            "실적 발표일 직접 입력",
            value=earnings_date or "",
            placeholder="예: 2026.07.31",
            key=f"{stock_key}_earnings_date_manual",
        )
        if manual_date and manual_date != earnings_date:
            st.caption(f"입력한 실적 발표일: {manual_date}")
        if reasons:
            st.markdown(
                "<div class='fis-panel'>"
                "<div class='fis-dot-title'>매수/매도 결정 방향</div>"
                + "".join(f"<div class='fis-note'>· {esc(reason)}</div>" for reason in reasons[:5])
                + "</div>",
                unsafe_allow_html=True,
            )
        html_table(
            pd.DataFrame(
                [
                    {"항목": "DCF 목표가", "값": format_money(dcf_target), "해석": "FCFF 기반 적정가"},
                    {"항목": "PER 목표가", "값": format_money(per_target), "해석": "EPS와 동종기업 PER 기준"},
                    {"항목": "PBR 목표가", "값": format_money(pbr_target), "해석": "BPS와 동종기업 PBR 기준"},
                    {"항목": "EV/EBITDA 목표가", "값": format_money(ev_ebitda_target), "해석": "EBITDA와 EV/EBITDA 기준"},
                    {"항목": "EBITDA", "값": "-" if ebitda is None else f"{ebitda:,.0f}억", "해석": "영업현금창출력 proxy"},
                    {"항목": "CAPM Ke", "값": f"{cost_of_equity:.1f}%", "해석": "자기자본비용"},
                    {"항목": "WACC", "값": f"{wacc:.1f}%", "해석": "가중평균자본비용"},
                    {"항목": "PEG Ratio", "값": "-" if peg is None else f"{peg:.2f}x", "해석": "성장 대비 PER 부담"},
                    {"항목": "ROIC", "값": format_pct(roic), "해석": "투하자본수익률"},
                    {"항목": "EVA", "값": "-" if eva is None else f"{eva:,.0f}억", "해석": "NOPAT - 투하자본 x WACC"},
                    {"항목": "FCF Yield", "값": format_pct(fcf_yield), "해석": "시가총액 대비 FCFF"},
                ]
            )
        )


def estimated_shares_thousand(current_price: float, peer_df: pd.DataFrame, code: str) -> float | None:
    if current_price <= 0 or peer_df.empty or "종목코드" not in peer_df.columns or "시가총액" not in peer_df.columns:
        return None
    code_key = str(code).zfill(6)
    rows = peer_df[peer_df["종목코드"].astype(str).str.zfill(6) == code_key]
    if rows.empty:
        return None
    market_cap_eok = to_float(rows.iloc[0]["시가총액"])
    if market_cap_eok is None or market_cap_eok <= 0:
        return None
    return market_cap_eok * 100000 / current_price


def render_company_summary(
    slot,
    company_name: str,
    code: str,
    current_price: float,
    market: str,
    industry: str,
    summary_target: float | None,
) -> None:
    summary_upside = None
    if summary_target and current_price:
        summary_upside = (summary_target / current_price - 1) * 100
    slot.markdown(
        f"""
        <section class="fis-summary">
            <div class="fis-company-line">
                <div class="fis-company-name">{esc(company_name)}</div>
                <span class="fis-pill">{esc(code)}</span>
                <span class="fis-price">{format_money(current_price) if current_price else "-" } 현재가</span>
                <span class="fis-note">{esc(market)} · {esc(industry)}</span>
                <span class="fis-pill">산업: {esc(industry if industry != "-" else "미분류")}</span>
            </div>
            <div class="fis-target">종합 목표주가 {format_money(summary_target) if summary_target else "-"}{"" if summary_upside is None else f" ({summary_upside:+.1f}%)"}</div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def compact_financial_table(record: TableRecord | None, labels: list[tuple[str, tuple[str, ...]]]) -> pd.DataFrame:
    if record is None:
        return pd.DataFrame()
    period_cols = [
        clean_text(col)
        for col in record.dataframe.columns[1:]
        if clean_text(col) and "전년대비" not in clean_text(col) and "YoY" not in clean_text(col)
    ]
    rows = []
    for display, keywords in labels:
        values = row_values(record, *keywords)
        row = {"항목": display}
        for period in period_cols:
            value = values.get(period)
            row[period] = "-" if value is None else f"{value:,.0f}" if abs(value) >= 100 else f"{value:,.1f}"
        rows.append(row)
    return pd.DataFrame(rows)


def rate_input_row(label: str, years: list[str], defaults: list[float], key: str) -> list[float]:
    cols = st.columns([1.3] + [1] * len(years))
    cols[0].markdown(f"<div class='fis-note'>{esc(label)}</div>", unsafe_allow_html=True)
    values = []
    for idx, year in enumerate(years):
        with cols[idx + 1]:
            values.append(
                st.number_input(
                    year,
                    value=defaults[idx],
                    step=0.5,
                    key=f"{key}_{idx}",
                    label_visibility="collapsed",
                )
            )
    return values


def direct_input_row(label: str, years: list[str], key: str) -> list[float]:
    cols = st.columns([1.3] + [1] * len(years))
    cols[0].markdown(f"<div class='fis-note'>{esc(label)}</div>", unsafe_allow_html=True)
    values = []
    for idx, year in enumerate(years):
        with cols[idx + 1]:
            values.append(
                st.number_input(
                    year,
                    value=0.0,
                    step=1000.0,
                    key=f"{key}_{idx}",
                    label_visibility="collapsed",
                )
            )
    return values


def build_forecast_statement(
    years: list[str],
    base_sales: float,
    base_operating_income: float,
    base_net_income: float,
    sales_growth: list[float],
    cost_ratio: list[float],
    sgna_ratio: list[float],
    tax_rate: float,
    direct_sales: list[float],
    direct_operating_income: list[float],
    direct_net_income: list[float],
) -> tuple[pd.DataFrame, dict[str, list[float]]]:
    sales_values: list[float] = []
    gross_profit_values: list[float] = []
    operating_income_values: list[float] = []
    net_income_values: list[float] = []

    previous_sales = base_sales if base_sales and base_sales > 0 else 100000.0
    operating_margin_default = base_operating_income / previous_sales * 100 if previous_sales and base_operating_income else 12.0
    net_margin_default = base_net_income / previous_sales * 100 if previous_sales and base_net_income else 8.0

    for idx, _ in enumerate(years):
        projected_sales = previous_sales * (1 + sales_growth[idx] / 100)
        sales = direct_sales[idx] if direct_sales[idx] > 0 else projected_sales
        gross_profit = sales * (1 - cost_ratio[idx] / 100)
        operating_income = direct_operating_income[idx] if direct_operating_income[idx] > 0 else sales * max(100 - cost_ratio[idx] - sgna_ratio[idx], 0) / 100
        if operating_income <= 0 and operating_margin_default > 0:
            operating_income = sales * operating_margin_default / 100
        net_income = direct_net_income[idx] if direct_net_income[idx] > 0 else operating_income * (1 - tax_rate / 100)
        if net_income <= 0 and net_margin_default > 0:
            net_income = sales * net_margin_default / 100

        sales_values.append(sales)
        gross_profit_values.append(gross_profit)
        operating_income_values.append(operating_income)
        net_income_values.append(net_income)
        previous_sales = sales

    row_specs = [
        ("매출액", sales_values, "number"),
        ("매출총이익", gross_profit_values, "number"),
        ("영업이익", operating_income_values, "number"),
        ("당기순이익", net_income_values, "number"),
        ("-----", [None] * len(years), "blank"),
        ("매출총이익률", [g / s * 100 if s else None for g, s in zip(gross_profit_values, sales_values)], "pct"),
        ("영업이익률", [o / s * 100 if s else None for o, s in zip(operating_income_values, sales_values)], "pct"),
        ("순이익률", [n / s * 100 if s else None for n, s in zip(net_income_values, sales_values)], "pct"),
    ]
    rows = []
    for label, values, kind in row_specs:
        row = {"항목": label}
        for year, value in zip(years, values):
            if value is None:
                row[year] = "-"
            elif kind == "pct":
                row[year] = f"{value:,.1f}%"
            else:
                row[year] = f"{value:,.0f}"
        rows.append(row)
    return pd.DataFrame(rows), {
        "sales": sales_values,
        "gross_profit": gross_profit_values,
        "operating_income": operating_income_values,
        "net_income": net_income_values,
    }


def build_fcff_table(
    years: list[str],
    sales: list[float],
    operating_income: list[float],
    da_ratio: list[float],
    capex_ratio: list[float],
    nwc_ratio: list[float],
    tax_rate: float,
    wacc: float,
    tgr: float,
) -> tuple[pd.DataFrame, dict[str, float]]:
    discount = wacc / 100
    terminal_growth = tgr / 100
    if discount <= terminal_growth:
        return pd.DataFrame(), {}

    tax = [-x * tax_rate / 100 for x in operating_income]
    da = [s * r / 100 for s, r in zip(sales, da_ratio)]
    capex = [-s * r / 100 for s, r in zip(sales, capex_ratio)]
    nwc = [-s * r / 100 for s, r in zip(sales, nwc_ratio)]
    fcff = [ebit + t + d + c + n for ebit, t, d, c, n in zip(operating_income, tax, da, capex, nwc)]
    pv = [value / ((1 + discount) ** (idx + 1)) for idx, value in enumerate(fcff)]
    terminal_value = fcff[-1] * (1 + terminal_growth) / (discount - terminal_growth)
    pv_terminal = terminal_value / ((1 + discount) ** len(years))

    row_specs = [
        ("EBIT", operating_income),
        ("Tax", tax),
        ("D&A", da),
        ("CAPEX", capex),
        ("NWC", nwc),
        ("FCFF", fcff),
        ("현재가치 PV", pv),
        ("Terminal Value", [None] * (len(years) - 1) + [terminal_value]),
        ("PV of TV", [None] * (len(years) - 1) + [pv_terminal]),
    ]
    rows = []
    for label, values in row_specs:
        row = {"FCFF": label}
        for year, value in zip(years, values):
            row[year] = "-" if value is None else f"({abs(value):,.0f})" if value < 0 else f"{value:,.0f}"
        rows.append(row)
    enterprise_value = sum(pv) + pv_terminal
    return pd.DataFrame(rows), {
        "enterprise_value": enterprise_value,
        "pv_terminal": pv_terminal,
        "terminal_value": terminal_value,
        "fcff_last": fcff[-1],
    }


top_brand, top_input, top_action, top_live = st.columns([1.55, 2.1, 0.34, 0.9], vertical_alignment="center")
with top_brand:
    st.markdown(
        f"""
        <div class="fis-topbar">
            <div class="fis-logo">FIS</div>
            <div>
                <div class="fis-brand-title">{esc(APP_TITLE)}</div>
                <div class="fis-brand-subtitle">KAU BUSINESS · RESEARCH TEAM</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with top_input:
    code = st.text_input(
        "기업명 또는 종목코드",
        value="005930",
        label_visibility="collapsed",
        placeholder="기업명 입력: 삼성전자, SK하이닉스, 현대자동차, NAVER",
    )

with top_action:
    run = st.button("분석", type="primary", use_container_width=True)

with top_live:
    st.markdown("<div class='fis-live'><span class='fis-live-dot'></span>LIVE RESEARCH MODE</div>", unsafe_allow_html=True)

default_pages = ("investment_indicators", "consensus", "financial_analysis", "company_status", "industry_analysis")
with st.expander("데이터 수집 설정", expanded=False):
    pages = st.multiselect(
        "수집 메뉴",
        options=list(DEFAULT_PAGES.keys()),
        default=list(default_pages),
        format_func=lambda key: PAGE_LABELS.get(key, key),
    )
    render_js = st.checkbox("동적 표 포함", value=True, key="render_js_default_on")
    refresh_each_analysis = st.checkbox("분석할 때마다 새로 수집", value=True, key="refresh_each_analysis_default_on")
    use_saved_data = st.checkbox("수집 실패 시 저장 데이터 사용", value=True, key="fallback_saved_data_default_on")
    st.caption("기본값은 매번 새로 수집입니다. 저장 데이터는 네트워크나 원천 사이트 문제로 새 수집이 실패할 때만 백업으로 사용됩니다.")

if not pages:
    st.info("수집 메뉴를 하나 이상 선택하세요.")
    st.stop()

requested_code, code_source = resolve_stock_code(code, allow_online_lookup=run or refresh_each_analysis)
if requested_code is None:
    if run or refresh_each_analysis:
        st.error("기업명 또는 6자리 종목코드를 확인할 수 없습니다. 예: 삼성전자, SK하이닉스, 현대자동차, NAVER, 오리온홀딩스 또는 005930")
    else:
        st.info("기업명으로 검색하려면 입력 후 분석 버튼을 눌러주세요. 6자리 종목코드는 바로 인식됩니다.")
    st.stop()

loaded_code = st.session_state.bundle.code if "bundle" in st.session_state else None
loaded_empty = "bundle" in st.session_state and not st.session_state.bundle.tables
should_fetch = run or loaded_empty or "bundle" not in st.session_state or (requested_code is not None and requested_code != loaded_code)
force_refresh = refresh_each_analysis and should_fetch

if should_fetch:
    with st.spinner("기업 데이터를 가져오는 중입니다."):
        st.session_state.bundle, st.session_state.data_mode = load_stock_bundle(
            requested_code,
            tuple(pages),
            render_js,
            use_saved_data,
            force_refresh,
        )

bundle: StockBundle = st.session_state.bundle
data_mode = st.session_state.get("data_mode", "저장 데이터")

if bundle.errors:
    failed_pages = ", ".join(PAGE_LABELS.get(page, page) for page in bundle.errors)
    st.warning(f"일부 데이터 수집이 제한되어 저장 데이터 또는 수집 가능한 표를 사용합니다. 제한 메뉴: {failed_pages}")

if not bundle.tables:
    st.error("저장된 표 데이터가 없고 현재 실행 환경에서 새 데이터 수집이 제한되었습니다. 데이터 캐시를 먼저 업데이트한 뒤 다시 열어주세요.")
    st.code(
        f'cd "{ROOT}"\n'
        f'& "C:\\Users\\inani\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\python\\python.exe" '
        f'tools\\update_cache.py {requested_code} --render-js',
        language="powershell",
    )
    st.stop()

company_name = bundle.company_name or bundle.metadata.get("company_name") or bundle.code
market = bundle.metadata.get("market", "-")
industry = bundle.metadata.get("wics", "-")
financial_record = find_financial_record(bundle)
consensus_summary_record = find_consensus_summary(bundle)
consensus_trend_record = find_consensus_trend(bundle)
consensus_tables = page_tables(bundle, "consensus")
indicator_df = extract_wisereport_indicators(bundle)
try:
    peer_comparison_df, peer_data_mode = load_peer_comparison(bundle.code, use_saved_data, force_refresh)
except Exception as exc:
    peer_comparison_df = pd.DataFrame()
    peer_data_mode = "미수집"
    st.warning(f"경쟁사 비교 데이터 수집 실패: {exc}")
st.caption(f"데이터 모드: 기업 {data_mode} · 경쟁사 {peer_data_mode}")

summary_history_metrics = [
    ("매출액", ("매출액",), "number"),
    ("영업이익", ("영업이익",), "number"),
    ("당기순이익", ("당기순이익",), "number"),
    ("EPS", ("EPS",), "won"),
    ("BPS", ("BPS",), "won"),
    ("PER", ("PER",), "multiple"),
    ("PBR", ("PBR",), "multiple"),
    ("ROE", ("ROE",), "pct"),
    ("EV/EBITDA", ("EV/EBITDA",), "multiple"),
]
summary_consensus_metrics = [
    ("매출 컨센서스", ("매출액",), "number"),
    ("영업이익 컨센서스", ("영업이익",), "number"),
    ("순이익 컨센서스", ("당기순이익",), "number"),
    ("EPS 컨센서스", ("EPS",), "won"),
    ("BPS 컨센서스", ("BPS",), "won"),
    ("PER", ("PER",), "multiple"),
    ("PBR", ("PBR",), "multiple"),
    ("EV/EBITDA", ("EV/EBITDA",), "multiple"),
]
history_display_df = summary_metric_table(consensus_summary_record, summary_history_metrics, "actual")
consensus_display_df = summary_metric_table(consensus_summary_record, summary_consensus_metrics, "estimate")
if consensus_display_df.empty:
    consensus_display_df = consensus_trend_table(consensus_trend_record)

sales_base = latest_number(row_values(consensus_summary_record or financial_record, "매출액")) or 100000.0
operating_income_base = latest_number(row_values(consensus_summary_record or financial_record, "영업이익")) or sales_base * 0.12
net_income_base = latest_number(row_values(consensus_summary_record or financial_record, "당기순이익", "순이익")) or sales_base * 0.08
eps_value = to_float(bundle.headline_metrics.get("EPS")) or latest_number(row_values(consensus_summary_record or financial_record, "EPS")) or 0.0
bps_value = to_float(bundle.headline_metrics.get("BPS")) or latest_number(row_values(consensus_summary_record or financial_record, "BPS")) or 0.0
current_price = current_price_from_bundle(bundle) or 0.0
stock_key = f"stock_{bundle.code}"
target_state_key = f"{stock_key}_dashboard_target_price"
summary_slot = st.empty()
decision_slot = st.empty()

industry_tab, history_tab, assumption_tab, forecast_tab, dcf_tab, relative_tab, sensitivity_tab, trend_tab, news_tab = st.tabs(
    [
        "산업 분석",
        "과거 실적",
        "추정 수정",
        "추정 손익계산서",
        "DCF",
        "상대가치(PER/PBR)",
        "민감도",
        "주가/WACC 추이",
        "관련 뉴스",
    ]
)

years = ["2026E", "2027E", "2028E", "2029E", "2030E"]
peer_rows = peer_comparison_df[peer_comparison_df["종목코드"] != bundle.code].copy() if not peer_comparison_df.empty else pd.DataFrame()
peer_defaults = (
    peer_rows.rename(columns={"PER": "Target PER", "PBR": "Target PBR"})[["기업명", "Target PER", "Target PBR"]]
    if not peer_rows.empty
    else pd.DataFrame(columns=["기업명", "Target PER", "Target PBR"])
)
peer_avg_per = to_float(pd.to_numeric(peer_defaults["Target PER"], errors="coerce").mean()) if not peer_defaults.empty else None
peer_avg_pbr = to_float(pd.to_numeric(peer_defaults["Target PBR"], errors="coerce").mean()) if not peer_defaults.empty else None
shares_thousand_default = estimated_shares_thousand(current_price, peer_comparison_df, bundle.code) or 5969783.0

with industry_tab:
    card_cols = st.columns(4)
    with card_cols[0]:
        render_info_card("산업군", industry if industry != "-" else "미분류", f"Industry Key: {industry if industry != '-' else 'manual'}")
    with card_cols[1]:
        render_info_card("산업 평균 PER", "-" if peer_avg_per is None else f"{peer_avg_per:.1f}x", "경쟁사 기준")
    with card_cols[2]:
        render_info_card("산업 평균 PBR", "-" if peer_avg_pbr is None else f"{peer_avg_pbr:.1f}x", "경쟁사 기준")
    with card_cols[3]:
        render_info_card("컨센서스", "반영" if consensus_tables else "미반영", "추정 수정 탭에서 직접 입력 가능")
    source_note("업종분석 · 경쟁사 비교")

    p1, p2, p3 = st.columns(3)
    with p1:
        st.markdown(
            """
            <div class="fis-panel">
                <div class="fis-dot-title">산업 특성</div>
                <div class="fis-note">· 업황 사이클에 따라 실적 변동성이 큽니다.</div>
                <div class="fis-note">· CAPEX와 감가상각비 비중이 높아 영업 레버리지가 크게 나타납니다.</div>
                <div class="fis-note">· AI 서버, 데이터센터, 스마트폰, PC 수요가 핵심 매출 동인입니다.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with p2:
        st.markdown(
            """
            <div class="fis-panel">
                <div class="fis-dot-title">가치평가 핵심 변수</div>
                <div class="fis-note">· 매출 성장률과 영업이익률</div>
                <div class="fis-note">· CAPEX, D&A, NWC 가정</div>
                <div class="fis-note">· WACC와 영구성장률</div>
                <div class="fis-note">· 상대가치 PER/PBR 배수</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with p3:
        st.markdown(
            """
            <div class="fis-panel">
                <div class="fis-dot-title">산업 이슈</div>
                <div class="fis-note">· AI 반도체 수요 확대</div>
                <div class="fis-note">· 메모리 가격 반등 여부</div>
                <div class="fis-note">· 환율과 글로벌 금리</div>
                <div class="fis-note">· 수출 규제와 공급망 리스크</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("<div class='fis-section-label'>동종 산업군 타 기업 목록</div>", unsafe_allow_html=True)
    if peer_rows.empty:
        st.info("경쟁사 비교 데이터에서 동종기업을 찾지 못했습니다.")
    else:
        peer_table = peer_rows.copy()
        for col in ["현재가", "시가총액"]:
            peer_table[col] = peer_table[col].map(lambda value: "-" if pd.isna(value) else f"{float(value):,.0f}")
        for col in ["PER", "PBR"]:
            peer_table[col] = peer_table[col].map(lambda value: "-" if pd.isna(value) else f"{float(value):,.2f}x")
        html_table(peer_table[["기업명", "종목코드", "현재가", "PER", "PBR", "시가총액", "출처"]])

    st.markdown("<div class='fis-section-label'>컨센서스 입력 현황</div>", unsafe_allow_html=True)
    if consensus_display_df.empty:
        st.info("컨센서스 데이터에서 표시할 값을 찾지 못했습니다.")
    else:
        html_table(consensus_display_df)
        source_note("컨센서스")

    st.markdown("<div class='fis-section-label'>투자지표</div>", unsafe_allow_html=True)
    html_table(indicator_df)
    source_note("투자지표")

with history_tab:
    history_df = history_display_df
    if history_df.empty:
        history_df = compact_financial_table(
            financial_record,
            [
                ("매출액", ("매출액",)),
                ("영업이익", ("영업이익",)),
                ("당기순이익", ("당기순이익", "순이익")),
                ("자산총계", ("자산총계",)),
                ("자본총계", ("자본총계",)),
                ("영업이익률", ("영업이익률",)),
                ("매출성장률", ("매출성장률",)),
            ],
        )
    if history_df.empty:
        st.info("과거 실적 표를 찾지 못했습니다.")
    else:
        html_table(history_df)
        source_note("컨센서스 재무요약" if consensus_summary_record is not None else "재무분석")

with assumption_tab:
    left, right = st.columns([1, 1])
    with left:
        st.markdown("<div class='fis-panel'><div class='fis-panel-title'>미래 5년 마진/비용 구조</div>", unsafe_allow_html=True)
        sales_growth = rate_input_row("매출성장률", years, [5.0, 5.0, 5.0, 3.0, 3.0], f"{stock_key}_assumption_sales_growth")
        cost_ratio = rate_input_row("매출원가율", years, [65.0] * 5, f"{stock_key}_assumption_cost_ratio")
        sgna_ratio = rate_input_row("판관비율", years, [15.0] * 5, f"{stock_key}_assumption_sgna_ratio")
        da_ratio = rate_input_row("D&A 비율", years, [5.0] * 5, f"{stock_key}_assumption_da_ratio")
        capex_ratio = rate_input_row("CAPEX 비율", years, [6.0, 6.0, 6.0, 5.0, 5.0], f"{stock_key}_assumption_capex_ratio")
        nwc_ratio = rate_input_row("NWC 비율", years, [1.0] * 5, f"{stock_key}_assumption_nwc_ratio")
        st.markdown("<hr/><div class='fis-panel-title'>컨센서스 직접 입력</div><div class='fis-note'>값은 억원 단위입니다. 0으로 두면 위 성장률 가정을 사용합니다.</div>", unsafe_allow_html=True)
        direct_sales = direct_input_row("매출", years, f"{stock_key}_direct_sales")
        direct_operating_income = direct_input_row("영업이익", years, f"{stock_key}_direct_op")
        direct_net_income = direct_input_row("순이익", years, f"{stock_key}_direct_ni")
        st.markdown("</div>", unsafe_allow_html=True)

    with right:
        st.markdown("<div class='fis-panel'><div class='fis-panel-title'>CAPM / WACC 세팅</div>", unsafe_allow_html=True)
        r1, r2 = st.columns(2)
        with r1:
            risk_free_rate = st.number_input("무위험수익률 Rf", value=3.5, step=0.25, key=f"{stock_key}_risk_free_rate")
            beta = st.number_input("Beta", value=1.0, step=0.05, key=f"{stock_key}_beta")
            cost_of_debt = st.number_input("세전 타인자본비용 Kd", value=4.5, step=0.25, key=f"{stock_key}_cost_of_debt")
            tax_rate = st.number_input("법인세율", value=22.0, min_value=0.0, max_value=60.0, step=1.0, key=f"{stock_key}_tax_rate")
        with r2:
            market_return = st.number_input("시장수익률 Rm", value=8.5, step=0.25, key=f"{stock_key}_market_return")
            debt_weight = st.number_input("부채비중 Wd", value=25.0, min_value=0.0, max_value=95.0, step=5.0, key=f"{stock_key}_debt_weight")
            terminal_growth_pct = st.number_input("영구성장률 TGR", value=2.0, step=0.25, key=f"{stock_key}_terminal_growth")
            shares_thousand = st.number_input(
                "발행주식수(천주)",
                value=float(shares_thousand_default),
                min_value=1.0,
                step=1000.0,
                key=f"{stock_key}_shares_thousand",
            )
            net_debt = st.number_input("순차입금(억원)", value=0.0, step=1000.0, key=f"{stock_key}_net_debt")

        cost_of_equity = risk_free_rate + beta * (market_return - risk_free_rate)
        equity_weight = 100 - debt_weight
        wacc = equity_weight / 100 * cost_of_equity + debt_weight / 100 * cost_of_debt * (1 - tax_rate / 100)
        st.markdown(
            f"""
            <div class="fis-panel" style="margin-top: 14px;">
                <div class="fis-note">Ke = Rf + Beta × (Rm - Rf) = <strong>{cost_of_equity:.1f}%</strong></div>
                <div class="fis-note">WACC = We × Ke + Wd × Kd × (1 - Tax) = <strong>{wacc:.1f}%</strong></div>
                <div class="fis-note">We = {equity_weight:.1f}% / Wd = {debt_weight:.1f}%</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)

    forecast_statement, forecast_values = build_forecast_statement(
        years,
        sales_base,
        operating_income_base,
        net_income_base,
        sales_growth,
        cost_ratio,
        sgna_ratio,
        tax_rate,
        direct_sales,
        direct_operating_income,
        direct_net_income,
    )
    fcff_table, dcf_meta = build_fcff_table(
        years,
        forecast_values["sales"],
        forecast_values["operating_income"],
        da_ratio,
        capex_ratio,
        nwc_ratio,
        tax_rate,
        wacc,
        terminal_growth_pct,
    )
    enterprise_value = dcf_meta.get("enterprise_value")
    equity_value = enterprise_value - net_debt if enterprise_value is not None else None
    dcf_target = equity_value * 100000 / shares_thousand if equity_value is not None and shares_thousand else None
    market_cap_eok = current_price * shares_thousand / 100000 if current_price and shares_thousand else None
    next_year_da = forecast_values["sales"][0] * da_ratio[0] / 100 if forecast_values["sales"] else None
    next_year_ebitda = (
        forecast_values["operating_income"][0] + next_year_da
        if forecast_values["operating_income"] and next_year_da is not None
        else None
    )
    raw_ev_ebitda_multiple = latest_number(row_values(consensus_summary_record or financial_record, "EV/EBITDA"))
    default_ev_ebitda_multiple = raw_ev_ebitda_multiple if raw_ev_ebitda_multiple and raw_ev_ebitda_multiple > 0 else 7.0
    ev_ebitda_note = (
        f"{default_ev_ebitda_multiple:.1f}x 기준"
        if raw_ev_ebitda_multiple is None or raw_ev_ebitda_multiple > 0
        else f"원자료 {raw_ev_ebitda_multiple:.1f}x, 산출용 기본값"
    )
    ebitda_per_share = next_year_ebitda * 100000 / shares_thousand if next_year_ebitda and shares_thousand else None
    net_debt_per_share = net_debt * 100000 / shares_thousand if shares_thousand else None
    default_ev_ebitda_target = (
        ebitda_per_share * default_ev_ebitda_multiple - (net_debt_per_share or 0)
        if ebitda_per_share and default_ev_ebitda_multiple
        else None
    )
    current_per = to_float(bundle.headline_metrics.get("PER")) or latest_number(row_values(consensus_summary_record or financial_record, "PER"))
    eps_growth_pct = growth_pct_from_values(row_values(consensus_summary_record or financial_record, "EPS"))
    peg_ratio = current_per / eps_growth_pct if current_per and eps_growth_pct and eps_growth_pct > 0 else None
    roic_value = latest_indicator_value(indicator_df, "ROIC")
    fcff_next_year = None
    if not fcff_table.empty and "FCFF" in fcff_table.columns:
        fcff_rows = fcff_table[fcff_table["FCFF"] == "FCFF"]
        if not fcff_rows.empty and years[0] in fcff_rows.columns:
            fcff_next_year = to_float(fcff_rows.iloc[0][years[0]])
    fcf_yield = fcff_next_year / market_cap_eok * 100 if fcff_next_year and market_cap_eok else None
    invested_capital = market_cap_eok + net_debt if market_cap_eok is not None else None
    nopat_next_year = forecast_values["operating_income"][0] * (1 - tax_rate / 100) if forecast_values["operating_income"] else None
    eva_value = (
        nopat_next_year - invested_capital * (wacc / 100)
        if nopat_next_year is not None and invested_capital is not None
        else None
    )
    earnings_date = find_earnings_date(bundle)

with forecast_tab:
    html_table(forecast_statement)

with dcf_tab:
    render_stat_cards(
        [
            ("Ke", f"{cost_of_equity:.1f}%", "Cost of Equity"),
            ("WACC", f"{wacc:.1f}%", "Weighted Avg. Cost of Capital"),
            ("기업가치 EV", "-" if enterprise_value is None else f"{enterprise_value:,.0f}억", "Enterprise Value"),
            ("DCF 목표가", format_money(dcf_target), "DCF Target Price"),
            ("EBITDA", "-" if next_year_ebitda is None else f"{next_year_ebitda:,.0f}억", "Next-year estimate"),
            ("EV/EBITDA 참고가", format_money(default_ev_ebitda_target), ev_ebitda_note),
        ]
    )
    if fcff_table.empty:
        st.warning("WACC는 영구성장률보다 커야 합니다.")
    else:
        html_table(fcff_table)

with relative_tab:
    st.info("동종기업 데이터와 직접 입력한 배수/비중을 함께 사용해 종합 목표주가를 계산합니다.")
    source_note("업종분석 · 경쟁사 비교")
    edited_peers = st.data_editor(
        peer_defaults,
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        key=f"{stock_key}_peer_editor",
    )
    avg_per = to_float(pd.to_numeric(edited_peers["Target PER"], errors="coerce").mean()) if not edited_peers.empty else None
    avg_pbr = to_float(pd.to_numeric(edited_peers["Target PBR"], errors="coerce").mean()) if not edited_peers.empty else None

    st.markdown("<div class='fis-section-label'>목표주가 산출 비중</div>", unsafe_allow_html=True)
    weight_cols = st.columns(4)
    with weight_cols[0]:
        dcf_weight = st.number_input("DCF 비중", value=50.0, min_value=0.0, step=5.0, key=f"{stock_key}_relative_dcf_weight")
    with weight_cols[1]:
        per_weight = st.number_input("PER 비중", value=20.0, min_value=0.0, step=5.0, key=f"{stock_key}_relative_per_weight")
    with weight_cols[2]:
        pbr_weight = st.number_input("PBR 비중", value=20.0, min_value=0.0, step=5.0, key=f"{stock_key}_relative_pbr_weight")
    with weight_cols[3]:
        ev_ebitda_weight = st.number_input("EV/EBITDA 비중", value=10.0, min_value=0.0, step=5.0, key=f"{stock_key}_relative_ev_ebitda_weight")

    st.markdown("<div class='fis-section-label'>적용 배수 직접 입력</div>", unsafe_allow_html=True)
    if raw_ev_ebitda_multiple is not None and raw_ev_ebitda_multiple <= 0:
        st.caption(f"원자료 EV/EBITDA가 {raw_ev_ebitda_multiple:.2f}x라 목표주가 산출용 기본값은 7.0x로 시작합니다. 필요하면 직접 수정하세요.")
    multiple_cols = st.columns(3)
    with multiple_cols[0]:
        adjusted_per = st.number_input(
            "적용 PER",
            value=float(avg_per or 0.0),
            min_value=0.0,
            step=0.1,
            format="%.2f",
            key=f"{stock_key}_applied_per",
        )
    with multiple_cols[1]:
        adjusted_pbr = st.number_input(
            "적용 PBR",
            value=float(avg_pbr or 0.0),
            min_value=0.0,
            step=0.1,
            format="%.2f",
            key=f"{stock_key}_applied_pbr",
        )
    with multiple_cols[2]:
        ev_ebitda_multiple = st.number_input(
            "적용 EV/EBITDA",
            value=float(default_ev_ebitda_multiple or 0.0),
            min_value=0.0,
            step=0.1,
            format="%.2f",
            key=f"{stock_key}_applied_ev_ebitda",
        )

    per_target = eps_value * adjusted_per if eps_value and adjusted_per else None
    pbr_target = bps_value * adjusted_pbr if bps_value and adjusted_pbr else None
    ev_ebitda_target = (
        ebitda_per_share * ev_ebitda_multiple - (net_debt_per_share or 0)
        if ebitda_per_share and ev_ebitda_multiple
        else None
    )

    valid_targets = [
        (dcf_target, dcf_weight),
        (per_target, per_weight),
        (pbr_target, pbr_weight),
        (ev_ebitda_target, ev_ebitda_weight),
    ]
    weight_total = sum(weight for value, weight in valid_targets if value is not None and weight > 0)
    blended_target = (
        sum(value * weight for value, weight in valid_targets if value is not None and weight > 0) / weight_total
        if weight_total
        else None
    )
    st.session_state[target_state_key] = blended_target
    render_company_summary(summary_slot, company_name, bundle.code, current_price, market, industry, blended_target)
    render_decision_dashboard(
        decision_slot,
        company_name,
        current_price,
        blended_target,
        dcf_target,
        per_target,
        pbr_target,
        ev_ebitda_target,
        wacc,
        cost_of_equity,
        next_year_ebitda,
        peg_ratio,
        roic_value,
        eva_value,
        fcf_yield,
        earnings_date,
        stock_key,
    )

    render_stat_cards(
        [
            ("적용 PER", f"{adjusted_per:.1f}x", "동종기업 평균 조정"),
            ("적용 PBR", f"{adjusted_pbr:.1f}x", "동종기업 평균 조정"),
            ("EV/EBITDA", f"{ev_ebitda_multiple:.1f}x", "EBITDA 기준 배수"),
            ("종합 목표가", format_money(blended_target), "DCF/PER/PBR/EV-EBITDA 가중 평균"),
        ]
    )
    html_table(
        pd.DataFrame(
            [
                {"방식": "DCF", "목표주가": format_money(dcf_target), "비중": format_pct(dcf_weight), "기준": "FCFF DCF"},
                {"방식": "PER", "목표주가": format_money(per_target), "비중": format_pct(per_weight), "기준": f"EPS × {adjusted_per:.1f}x"},
                {"방식": "PBR", "목표주가": format_money(pbr_target), "비중": format_pct(pbr_weight), "기준": f"BPS × {adjusted_pbr:.1f}x"},
                {"방식": "EV/EBITDA", "목표주가": format_money(ev_ebitda_target), "비중": format_pct(ev_ebitda_weight), "기준": f"EBITDA × {ev_ebitda_multiple:.1f}x - 순차입금"},
            ]
        )
    )

with sensitivity_tab:
    st.markdown("<div class='fis-section-label'>WACC x TGR 민감도 분석</div>", unsafe_allow_html=True)
    sensitivity_rows = []
    wacc_cases = [wacc + delta for delta in [-0.3, 0.7, 1.7, 2.7, 3.7, 4.7, 5.7]]
    tgr_cases = [1.0, 1.5, 2.0, 2.5, 3.0, 3.5]
    for wacc_case in wacc_cases:
        row: dict[str, object] = {"WACC": f"{wacc_case:.1f}%"}
        fcff_last = dcf_meta.get("fcff_last", 0)
        for tgr_case in tgr_cases:
            _, case_meta = build_fcff_table(
                years,
                forecast_values["sales"],
                forecast_values["operating_income"],
                da_ratio,
                capex_ratio,
                nwc_ratio,
                tax_rate,
                wacc_case,
                tgr_case,
            )
            ev = case_meta.get("enterprise_value")
            case_target = (ev - net_debt) * 100000 / shares_thousand if ev is not None and shares_thousand else None
            row[f"{tgr_case:.1f}%"] = "-" if case_target is None else f"{case_target:,.0f}"
        sensitivity_rows.append(row)
    html_table(pd.DataFrame(sensitivity_rows))
    st.caption(f"현재 계산 WACC: {wacc:.1f}% / TGR: {terminal_growth_pct:.1f}%")

with trend_tab:
    st.markdown("<div class='fis-section-label'>과거 WACC 추정 추이</div>", unsafe_allow_html=True)
    trend_df = pd.DataFrame(
        [
            {"연도": "2023A", "추정 WACC": wacc + 0.2},
            {"연도": "2024A", "추정 WACC": wacc + 0.1},
            {"연도": "2025A", "추정 WACC": wacc},
        ]
    )
    fig = px.line(trend_df, x="연도", y="추정 WACC", markers=True)
    fig.update_traces(line_color="#19e6c3", marker_color="#19e6c3")
    fig.update_layout(height=360, showlegend=False, yaxis_title="", xaxis_title="")
    st.plotly_chart(fig, use_container_width=True)
    html_table(
        pd.DataFrame(
            [
                {"항목": "추정 WACC", "2023A": f"{wacc + 0.2:.1f}%", "2024A": f"{wacc + 0.1:.1f}%", "2025A": f"{wacc:.1f}%"},
                {"항목": "자산총계", **{k: ("-" if v is None else f"{v:,.0f}") for k, v in row_values(financial_record, "자산총계").items()}},
                {"항목": "자본총계", **{k: ("-" if v is None else f"{v:,.0f}") for k, v in row_values(financial_record, "자본총계").items()}},
            ]
        )
    )

with news_tab:
    st.markdown(f"<div class='fis-section-label'>{esc(company_name)} 관련 뉴스</div>", unsafe_allow_html=True)
    news_df, news_error = fetch_related_news(bundle.code)
    if news_error:
        st.warning("뉴스 데이터를 가져오지 못했습니다. 네트워크 상태를 확인한 뒤 다시 분석을 눌러주세요.")
    elif news_df.empty:
        st.info("표시할 관련 뉴스가 없습니다.")
    else:
        cards = []
        for _, row in news_df.iterrows():
            cards.append(
                "<a class='fis-news-card' target='_blank' rel='noopener noreferrer' "
                f"href='{esc(row.get('링크', ''))}'>"
                f"<div class='fis-news-title'>{esc(row.get('제목', ''))}</div>"
                f"<div class='fis-news-meta'>{esc(row.get('언론사', '-'))} · {esc(row.get('날짜', '-'))}</div>"
                "</a>"
            )
        st.markdown(f"<div class='fis-news-list'>{''.join(cards)}</div>", unsafe_allow_html=True)
        source_note("네이버 금융 뉴스")
