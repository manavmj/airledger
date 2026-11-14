"""Synthetic fixtures test calculations; they are never presented as civic observations."""

import io
import unittest
from pathlib import Path

from openpyxl import Workbook

from app.analysis import compare, normalize, normalize_unit, parse_time, summarize
from app.ingest import parse_table

FIXTURE = Path(__file__).parent / "fixtures" / "messy_readings.csv"
OPTIONS = {"pollutant": "", "unit": "", "date_order": "DMY"}


def analyzed(text):
    table = parse_table(text.encode(), "test.csv")
    clean = normalize(table, table["mapping"], OPTIONS)
    return clean, summarize(clean)


class IngestionTests(unittest.TestCase):
    def test_csv_semicolon_and_bom(self):
        table = parse_table(
            "\ufeffstation;timestamp;value\nTEST;2026-11-01;12".encode(), "source.csv"
        )
        self.assertEqual(table["columns"], ["station", "timestamp", "value"])
        self.assertEqual(table["rows"][0]["source_row"], 2)

    def test_tsv(self):
        self.assertEqual(len(parse_table(b"a\tb\nc\td", "test.tsv")["rows"]), 1)

    def test_multiline_csv_preserves_logical_row(self):
        table = parse_table(b'station,value\n"TEST\nNorth",12\nTEST,13', "test.csv")
        self.assertEqual(table["rows"][1]["source_row"], 3)

    def test_reject_duplicate_headers(self):
        with self.assertRaisesRegex(ValueError, "unique"):
            parse_table(b"a,a\n1,2", "test.csv")

    def test_reject_ragged_table(self):
        with self.assertRaises(ValueError):
            parse_table(b"a,b\n1,2\n3,4,5", "test.csv")

    def test_reject_empty_oversized_and_unsupported(self):
        for content, filename in [
            (b"", "x.csv"),
            (b"a" * (5 * 1024 * 1024 + 1), "x.csv"),
            (b"a,b\n1,2", "x.xls"),
        ]:
            with self.subTest(filename=filename, size=len(content)), self.assertRaises(ValueError):
                parse_table(content, filename)

    def test_reject_row_limit(self):
        with self.assertRaisesRegex(ValueError, "20,000"):
            parse_table(b"a,b\n" + b"1,2\n" * 20001, "x.csv")

    def test_workbook_values_and_formula_rejection(self):
        workbook = Workbook()
        sheet = workbook.active
        sheet.append(["station", "value"])
        sheet.append(["TEST", 10])
        buffer = io.BytesIO()
        workbook.save(buffer)
        self.assertEqual(
            parse_table(buffer.getvalue(), "test.xlsx")["rows"][0]["cells"]["value"], "10"
        )
        sheet["B2"] = "=1+1"
        buffer = io.BytesIO()
        workbook.save(buffer)
        with self.assertRaisesRegex(ValueError, "Formula"):
            parse_table(buffer.getvalue(), "test.xlsx")

    def test_multiple_sheets_rejected(self):
        workbook = Workbook()
        workbook.create_sheet("Other")
        buffer = io.BytesIO()
        workbook.save(buffer)
        with self.assertRaisesRegex(ValueError, "single worksheet"):
            parse_table(buffer.getvalue(), "test.xlsx")


class NormalizationTests(unittest.TestCase):
    def setUp(self):
        self.table = parse_table(FIXTURE.read_bytes(), "fixture.csv")
        self.clean = normalize(self.table, self.table["mapping"], OPTIONS)
        self.summary = summarize(self.clean)

    def test_mixed_units_and_traceability(self):
        first = self.clean["rows"][0]
        self.assertEqual(first["value"], 24)
        self.assertEqual(first["raw"]["Reading"], "0.024")
        self.assertEqual(first["id"], "R2")
        self.assertEqual(self.summary["included"], 4)
        self.assertEqual(self.summary["excluded"], 6)

    def test_duplicates_and_conflicts(self):
        self.assertIn("duplicate", self.clean["rows"][2]["flags"])
        for row in self.clean["rows"][-2:]:
            self.assertFalse(row["included"])
            self.assertIn("conflicting_reading", row["flags"])

    def test_statistics_and_within_pollutant_rank(self):
        north = next(s for s in self.summary["summaries"] if s["station"] == "TEST North")
        self.assertEqual(north["mean"], 27)
        self.assertEqual(north["p95"], 29.7)
        self.assertEqual(north["rank"], 1)
        self.assertEqual(north["evidence"], ["R2", "R3"])

    def test_guidelines_only_stated_24h(self):
        self.assertEqual(next(f for f in self.summary["facts"] if f["id"] == "G2")["threshold"], 15)
        _, summary = analyzed(
            "station,timestamp,pollutant,value,unit\nTEST,2026-11-01,PM2.5,90,ug/m3"
        )
        self.assertFalse(any(f["kind"] == "reference" for f in summary["facts"]))

    def test_daily_trend_has_both_endpoint_evidence(self):
        trend = next(f for f in self.summary["facts"] if f["kind"] == "trend")
        self.assertEqual(trend["delta"], 6)
        self.assertEqual(trend["evidence"], ["R2", "R3"])

    def test_date_order_is_explicit(self):
        self.assertEqual(parse_time("03/04/2026", "DMY").month, 4)
        self.assertEqual(parse_time("03/04/2026", "MDY").month, 3)
        self.assertEqual(parse_time("2026-01-01T02:00:00+02:00", "DMY").hour, 0)

    def test_no_silent_gas_or_decimal_conversion(self):
        self.assertIsNone(normalize_unit("ppb"))
        clean, _ = analyzed(
            'station,timestamp,pollutant,value,unit\nTEST,2026-11-01,PM2.5,"1,25",ug/m3'
        )
        self.assertFalse(clean["rows"][0]["included"])

    def test_no_infinite_negative_or_overflow_values(self):
        for value in ("NaN", "inf", "-1", "1e308"):
            clean, summary = analyzed(
                f"station,timestamp,pollutant,value,unit\nTEST,2026-11-01,PM2.5,{value},ug/m3"
            )
            self.assertEqual(summary["included"], 0)
            self.assertIsNone(clean["rows"][0]["value"])

    def test_missing_required_mapping_rejected(self):
        with self.assertRaisesRegex(ValueError, "Map location"):
            normalize(self.table, {}, OPTIONS)

    def test_duplicate_mapping_rejected(self):
        mapping = {**self.table["mapping"], "timestamp": "Location"}
        with self.assertRaisesRegex(ValueError, "different"):
            normalize(self.table, mapping, OPTIONS)

    def test_fixed_pollutant_and_units_are_explicit(self):
        table = parse_table(b"station,timestamp,value\nTEST,2026-11-01,0.02", "test.csv")
        with self.assertRaisesRegex(ValueError, "pollutant"):
            normalize(table, table["mapping"], OPTIONS)
        clean = normalize(
            table, table["mapping"], {**OPTIONS, "pollutant": "PM2.5", "unit": "mg/m3"}
        )
        self.assertEqual(clean["rows"][0]["value"], 20)

    def test_outlier_is_flagged_but_retained(self):
        text = "station,timestamp,pollutant,value,unit\n" + "\n".join(
            f"TEST,2026-11-0{i + 1},PM2.5,{v},ug/m3" for i, v in enumerate([10, 11, 12, 10, 1000])
        )
        clean, summary = analyzed(text)
        self.assertIn("statistical_outlier_retained", clean["rows"][-1]["flags"])
        self.assertEqual(summary["included"], 5)

    def test_comparison_zero_baseline_and_added_missing(self):
        _, first = analyzed(
            "station,timestamp,pollutant,value,unit\nTEST,2026-11-01,PM2.5,0,ug/m3\nOLD,2026-11-01,PM10,4,ug/m3"
        )
        _, second = analyzed(
            "station,timestamp,pollutant,value,unit\nTEST,2026-11-02,PM2.5,20,ug/m3\nNEW,2026-11-02,PM10,8,ug/m3"
        )
        result = compare(second, first)
        matched = next(c for c in result["changes"] if c["status"] == "matched")
        self.assertIsNone(matched["percent"])
        self.assertFalse(matched["same_duration"])
        self.assertEqual({c["status"] for c in result["changes"]}, {"matched", "added", "missing"})
        self.assertEqual(compare(first, None)["status"], "no_baseline")
