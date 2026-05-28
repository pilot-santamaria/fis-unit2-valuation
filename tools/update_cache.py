from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import pickle
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from wisereport_scraper import fetch_peer_comparison, scrape_stock


DEFAULT_PAGES = ("investment_indicators", "consensus", "financial_analysis", "company_status", "industry_analysis")
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
    "LG화학": "051910",
    "삼성SDI": "006400",
    "셀트리온": "068270",
    "삼성바이오로직스": "207940",
    "오리온홀딩스": "001800",
    "오리온": "271560",
}


def cache_path(prefix: str, *parts: object) -> Path:
    raw = "|".join(str(part) for part in parts)
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:18]
    return ROOT / ".fis_cache" / f"{prefix}_{digest}.pkl"


def save_pickle(path: Path, value: object) -> None:
    path.parent.mkdir(exist_ok=True)
    with path.open("wb") as file:
        pickle.dump(value, file)


def normalize_lookup_name(value: object) -> str:
    import re

    return re.sub(r"[^0-9A-Z가-힣]", "", str(value or "").strip().upper())


def resolve_code(value: str) -> str:
    digits = "".join(ch for ch in value if ch.isdigit())
    if len(digits) >= 6:
        return digits.zfill(6)[-6:]
    lookup = normalize_lookup_name(value)
    for name, code in KNOWN_STOCK_CODES.items():
        if normalize_lookup_name(name) == lookup:
            return code
    raise SystemExit(f"Unknown company or stock code: {value}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Update local FIS1 cache.")
    parser.add_argument("codes", nargs="*", default=["005930"], help="Six-digit stock codes")
    parser.add_argument("--render-js", action="store_true", help="Use browser rendering for dynamic tables")
    args = parser.parse_args()

    for code in args.codes:
        normalized = resolve_code(code)
        bundle = scrape_stock(normalized, pages=DEFAULT_PAGES, render_js=args.render_js)
        stock_cache = cache_path("stock", normalized, ",".join(DEFAULT_PAGES), args.render_js)
        if bundle.tables:
            save_pickle(stock_cache, bundle)

        try:
            peer_df = fetch_peer_comparison(normalized)
        except Exception as exc:
            peer_df = None
            print(f"{normalized}: peer comparison skipped ({exc})")
        peer_cache = cache_path("peers", normalized)
        if peer_df is not None and not peer_df.empty:
            save_pickle(peer_cache, peer_df)

        peer_count = 0 if peer_df is None else len(peer_df)
        print(f"{normalized}: saved {len(bundle.tables)} tables, {peer_count} peer rows")


if __name__ == "__main__":
    main()
