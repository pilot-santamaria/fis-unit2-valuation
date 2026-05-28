import sys
from pathlib import Path
import unittest

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from valuation import ValuationInputs, calculate_target_price, find_metric
from wisereport_scraper import TableRecord


def make_record(df: pd.DataFrame, page_key="investment_indicators", title="투자지표"):
    return TableRecord(
        page_key=page_key,
        page_label="투자지표",
        title=title,
        table_id="",
        order=0,
        dataframe=df,
    )


class ValuationTests(unittest.TestCase):
    def test_find_metric_row_metric_shape(self):
        df = pd.DataFrame(
            {
                "항목": ["EPS", "BPS", "CPS"],
                "2025/12 (IFRS연결)": ["1,000", "10,000", "2,000"],
                "2026/12(E)(IFRS연결)": ["1,500", "12,000", "2,500"],
            }
        )
        hit = find_metric([make_record(df)], "EPS", "2026/12")
        self.assertIsNotNone(hit)
        self.assertEqual(hit.value, 1500)

    def test_find_metric_period_row_shape(self):
        df = pd.DataFrame(
            {
                "재무연월": ["2025.12(A)", "2026.12(E)"],
                "EPS (원)": ["1,000", "1,500"],
                "BPS (원)": ["10,000", "12,000"],
            }
        )
        hit = find_metric([make_record(df, page_key="consensus", title="재무요약")], "BPS", "2026/12")
        self.assertIsNotNone(hit)
        self.assertEqual(hit.value, 12000)

    def test_calculate_weighted_target_price(self):
        df = pd.DataFrame(
            {
                "항목": ["EPS", "BPS", "CPS"],
                "2025/12": ["1,000", "10,000", "2,000"],
                "2026/12": ["1,500", "12,000", "2,500"],
            }
        )
        result = calculate_target_price(
            [make_record(df)],
            ValuationInputs(
                period="2026/12",
                start_period_for_growth="2025/12",
                current_price=10000,
                target_multiples={"PER": 10, "PBR": 1, "PCR": 5},
                weights={"PER": 50, "PBR": 50, "PCR": 0},
            ),
        )
        self.assertEqual(result.target_price, 13500)
        self.assertEqual(round(result.upside_pct or 0, 1), 35.0)


if __name__ == "__main__":
    unittest.main()
