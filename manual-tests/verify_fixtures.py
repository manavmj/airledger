"""Check synthetic upload cases against the production parser and analysis; no DB or AI calls."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.analysis import compare, normalize, summarize  # noqa: E402
from app.ingest import parse_table  # noqa: E402


def main():
    folder = Path(__file__).resolve().parent
    manifest = json.loads((folder / "expected-results.json").read_text())
    assert manifest["synthetic"] is True
    analyses, cleaned = {}, {}
    for filename, expected in manifest["files"].items():
        content = (folder / filename).read_bytes()
        if "import_error" in expected:
            try:
                parse_table(content, filename)
            except ValueError as error:
                assert expected["import_error"] in str(error), (filename, str(error))
            else:
                raise AssertionError(f"{filename}: import should have been rejected")
        else:
            table = parse_table(content, filename)
            mapping = {**table["mapping"], **expected.get("mapping_overrides", {})}
            options = {"date_order": "DMY", **expected.get("options", {})}
            clean = normalize(table, mapping, options)
            analysis = summarize(clean)
            for key in ("total", "included", "excluded", "flagged", "stations"):
                assert analysis[key] == expected[key], (filename, key, analysis[key], expected[key])
            means = {
                f"{item['station']}|{item['pollutant']}": item["mean"]
                for item in analysis["summaries"]
            }
            for key, mean in expected["means"].items():
                assert means[key] == mean, (filename, key, means[key], mean)
            if expected.get("no_reference"):
                assert not any(f["kind"] == "reference" for f in analysis["facts"]), filename
            analyses[filename], cleaned[filename] = analysis, clean
        print(f"PASS {filename}")

    baseline = analyses["01_clean_baseline.csv"]
    refs = {f["station"]: f for f in baseline["facts"] if f["kind"] == "reference"}
    assert (refs["TEST North"]["count"], refs["TEST North"]["total"]) == (3, 3)
    assert (refs["TEST South"]["count"], refs["TEST South"]["total"]) == (1, 3)
    north = next(s for s in baseline["summaries"] if s["station"] == "TEST North")
    assert (north["rank"], north["median"], north["p95"], north["evidence"]) == (
        1,
        30,
        39,
        ["R2", "R3", "R4"],
    )
    changes = compare(analyses["02_comparison_next_period.csv"], baseline)["changes"]
    by_station = {change["station"]: change for change in changes}
    assert (by_station["TEST North"]["delta"], by_station["TEST North"]["percent"]) == (30, 100)
    assert (by_station["TEST South"]["delta"], by_station["TEST South"]["percent"]) == (0, 0)
    assert all(c["same_duration"] for c in changes)
    messy = cleaned["03_messy_readings.csv"]["rows"]
    assert messy[0]["value"] == 24 and messy[0]["raw"]["Reading"] == "0.024"
    assert cleaned["06_fixed_columns_and_dates.tsv"]["rows"][0]["timestamp"].startswith(
        "2026-04-03"
    )
    outlier = analyses["07_outlier_retained.csv"]["summaries"][0]
    assert (outlier["median"], outlier["p95"]) == (11, 802.4)
    assert "statistical_outlier_retained" in cleaned["07_outlier_retained.csv"]["rows"][-1]["flags"]
    assert analyses["11_clean_baseline.xlsx"]["summaries"] == baseline["summaries"]
    print(
        f"Verified all {len(manifest['files'])} upload cases, conversions, evidence, comparison, dates and reference checks."
    )


if __name__ == "__main__":
    main()
