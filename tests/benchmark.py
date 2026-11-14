"""Local benchmark using explicitly synthetic, generated observations; never loaded into the app."""

import json
import time
from datetime import datetime, timedelta

from app.analysis import normalize, summarize
from app.ingest import parse_table


def main():
    start_date = datetime(2026, 1, 1)
    lines = ["station,timestamp,pollutant,value,unit,duration_hours"]
    for index in range(20_000):
        timestamp = (start_date + timedelta(hours=index // 50)).isoformat()
        lines.append(f"TEST {index % 50},{timestamp},PM2.5,{10 + index % 31},ug/m3,1")
    content = "\n".join(lines).encode()
    start = time.perf_counter()
    table = parse_table(content, "SYNTHETIC-benchmark.csv")
    parsed = time.perf_counter()
    clean = normalize(table, table["mapping"], {"date_order": "DMY"})
    normalized = time.perf_counter()
    analysis = summarize(clean)
    end = time.perf_counter()
    assert analysis["included"] == 20_000
    print(
        json.dumps(
            {
                "synthetic": True,
                "rows": 20_000,
                "source_bytes": len(content),
                "locations": analysis["stations"],
                "parse_seconds": round(parsed - start, 4),
                "normalize_seconds": round(normalized - parsed, 4),
                "summarize_seconds": round(end - normalized, 4),
                "total_seconds": round(end - start, 4),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
