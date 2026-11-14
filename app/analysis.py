"""Pure analysis functions: source-linked normalization, descriptive statistics, comparison.

No AQI inference, imputation, causal attribution, or forecasting from sparse readings.
"""

import math
import re
import statistics
from collections import defaultdict
from datetime import datetime, timezone

from .ingest import FIELDS

POLLUTANTS = {"pm25": "PM2.5", "pm10": "PM10", "no2": "NO2", "so2": "SO2", "o3": "O3", "co": "CO"}
WHO_24H = {"PM2.5": 15, "PM10": 45, "NO2": 25, "SO2": 40}
REFERENCE = "https://www.who.int/publications/i/item/9789240034228"


def parse_time(value: str, date_order: str) -> datetime:
    value = value.strip()
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        formats = ["%d/%m/%Y", "%d-%m-%Y"] if date_order == "DMY" else ["%m/%d/%Y", "%m-%d-%Y"]
        parsed = None
        for fmt in formats:
            for suffix in ("", " %H:%M", " %H:%M:%S"):
                try:
                    parsed = datetime.strptime(value, fmt + suffix)
                    break
                except ValueError:
                    continue
            if parsed:
                break
        if parsed is None:
            raise ValueError("Unrecognized timestamp")
    # Naive timestamps are explicitly treated as UTC by the confirmed import settings.
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def normalize_unit(unit: str) -> float | None:
    unit = unit.strip().lower().replace("μ", "u").replace("µ", "u")
    unit = unit.replace("³", "3").replace("^", "").replace(" ", "")
    return {"ug/m3": 1.0, "mg/m3": 1000.0}.get(unit)


def normalize(table: dict, mapping: dict, options: dict) -> dict:
    required = ("station", "timestamp", "value")
    if any(not mapping.get(field) for field in required):
        raise ValueError("Map location, timestamp, and concentration columns.")
    selected = [v for v in mapping.values() if v]
    if any(v not in table["columns"] for v in selected) or len(selected) != len(set(selected)):
        raise ValueError("Each mapped field must use a different existing column.")
    if set(mapping) - set(FIELDS):
        raise ValueError("Unknown mapped field.")
    if not mapping.get("pollutant") and not options.get("pollutant"):
        raise ValueError("Map a pollutant column or select a fixed pollutant.")
    if not mapping.get("unit") and not options.get("unit"):
        raise ValueError("Map a unit column or confirm a fixed unit.")
    rows, seen = [], {}
    for source in table["rows"]:
        cells = source["cells"]
        get = lambda field: str(cells.get(mapping.get(field), "")).strip()
        row = {
            "id": f"R{source['source_row']}",
            "source_row": source["source_row"],
            "raw": cells,
            "flags": [],
            "included": True,
            "value": None,
        }
        station = get("station")
        if not station:
            row["flags"].append("missing_location")
        row["station"] = station
        try:
            row["timestamp"] = parse_time(
                get("timestamp"), options.get("date_order", "DMY")
            ).isoformat()
        except ValueError:
            row["timestamp"] = None
            row["flags"].append("invalid_timestamp")
        pollutant = get("pollutant") if mapping.get("pollutant") else options.get("pollutant", "")
        row["pollutant"] = POLLUTANTS.get(re.sub(r"[^a-z0-9]", "", pollutant.lower()))
        if not row["pollutant"]:
            row["flags"].append("unsupported_pollutant")
        unit = get("unit") if mapping.get("unit") else options.get("unit", "")
        factor = normalize_unit(unit)
        if factor is None:
            row["flags"].append("unknown_unit")
        try:
            raw_value = get("value")
            # Commas are ambiguous (decimal vs thousands): do not silently interpret them.
            if "," in raw_value:
                raise ValueError
            value = float(raw_value)
            if not math.isfinite(value) or value < 0:
                raise ValueError
            if factor is not None:
                converted = value * factor
                if not math.isfinite(converted) or converted > 1_000_000_000:
                    raise ValueError
                row["value"] = converted
        except ValueError:
            row["flags"].append("invalid_or_missing_value")
        duration = get("duration_hours")
        row["duration_hours"] = None
        if duration:
            try:
                hours = float(duration)
                if not math.isfinite(hours) or hours <= 0 or hours > 8760:
                    raise ValueError
                row["duration_hours"] = hours
            except ValueError:
                row["flags"].append("invalid_duration")
        # Invalid duration does not invalidate a concentration, but blocks reference comparison.
        row["included"] = not any(f != "invalid_duration" for f in row["flags"])
        if row["included"]:
            identity = (
                station.casefold(),
                row["timestamp"],
                row["pollutant"],
                row["duration_hours"],
            )
            if identity in seen:
                original = seen[identity]
                if original["value"] == row["value"]:
                    row["flags"].append("duplicate")
                    row["included"] = False
                else:
                    row["flags"].append("conflicting_reading")
                    original["flags"].append("conflicting_reading")
                    row["included"] = original["included"] = False
            else:
                seen[identity] = row
        rows.append(row)
    groups = defaultdict(list)
    for row in rows:
        if row["included"]:
            groups[(row["station"].casefold(), row["pollutant"])].append(row)
    for group in groups.values():
        if len(group) >= 5:
            median = statistics.median(r["value"] for r in group)
            mad = statistics.median(abs(r["value"] - median) for r in group)
            for row in group:
                deviation = abs(row["value"] - median)
                if (mad > 0 and deviation / (1.4826 * mad) > 3.5) or (
                    mad == 0 and deviation > max(1, median * 0.5)
                ):
                    row["flags"].append("statistical_outlier_retained")
    return {"rows": rows, "options": options, "mapping": mapping}


def percentile(values: list[float], fraction: float) -> float:
    values = sorted(values)
    index = (len(values) - 1) * fraction
    lower, upper = math.floor(index), math.ceil(index)
    return values[lower] + (values[upper] - values[lower]) * (index - lower)


def summarize(clean: dict) -> dict:
    rows = clean["rows"]
    valid = [r for r in rows if r["included"]]
    groups, daily = defaultdict(list), defaultdict(list)
    for row in valid:
        groups[(row["station"].casefold(), row["pollutant"])].append(row)
        daily[(row["timestamp"][:10], row["pollutant"])].append(row)
    summaries, facts = [], []
    for number, (_, group) in enumerate(sorted(groups.items()), 1):
        station, pollutant = group[0]["station"], group[0]["pollutant"]
        values = [r["value"] for r in group]
        stats = {
            "station": station,
            "pollutant": pollutant,
            "count": len(values),
            "mean": round(statistics.mean(values), 3),
            "median": round(statistics.median(values), 3),
            "p95": round(percentile(values, 0.95), 3),
            "min": min(values),
            "max": max(values),
            "evidence": [r["id"] for r in group],
            "fact_id": f"F{number}",
            "start": min(r["timestamp"] for r in group),
            "end": max(r["timestamp"] for r in group),
            "durations": sorted(
                {r["duration_hours"] for r in group if r["duration_hours"] is not None}
            ),
            "unknown_duration_count": sum(r["duration_hours"] is None for r in group),
        }
        summaries.append(stats)
        facts.append({"id": stats["fact_id"], "kind": "summary", **stats})
        days = defaultdict(list)
        for row in group:
            days[row["timestamp"][:10]].append(row)
        if len(days) > 1:
            first_day, last_day = min(days), max(days)
            first, last = days[first_day], days[last_day]
            first_mean = round(statistics.mean(r["value"] for r in first), 3)
            last_mean = round(statistics.mean(r["value"] for r in last), 3)
            facts.append(
                {
                    "id": f"T{number}",
                    "kind": "trend",
                    "station": station,
                    "pollutant": pollutant,
                    "first_date": first_day,
                    "last_date": last_day,
                    "first_mean": first_mean,
                    "last_mean": last_mean,
                    "first_count": len(first),
                    "last_count": len(last),
                    "delta": round(last_mean - first_mean, 3),
                    "evidence": [r["id"] for r in first + last],
                }
            )
        reference_rows = [r for r in group if r["duration_hours"] == 24]
        if reference_rows and pollutant in WHO_24H:
            exceeded = [r for r in reference_rows if r["value"] > WHO_24H[pollutant]]
            facts.append(
                {
                    "id": f"G{number}",
                    "kind": "reference",
                    "station": station,
                    "pollutant": pollutant,
                    "count": len(exceeded),
                    "total": len(reference_rows),
                    "threshold": WHO_24H[pollutant],
                    "evidence": [r["id"] for r in reference_rows],
                }
            )
    # Rank within each pollutant; concentrations of different pollutants are never pooled.
    for pollutant in sorted({s["pollutant"] for s in summaries}):
        ranked = sorted(
            [s for s in summaries if s["pollutant"] == pollutant],
            key=lambda s: (-s["mean"], s["station"]),
        )
        for rank, summary in enumerate(ranked, 1):
            summary["rank"] = rank
    trends = [
        {
            "date": day,
            "pollutant": pollutant,
            "mean": round(statistics.mean(r["value"] for r in group), 3),
            "count": len(group),
            "evidence": [r["id"] for r in group],
        }
        for (day, pollutant), group in sorted(daily.items())
    ]
    flags = defaultdict(int)
    for row in rows:
        for flag in set(row["flags"]):
            flags[flag] += 1
    timestamps = sorted({r["timestamp"] for r in valid})
    return {
        "total": len(rows),
        "included": len(valid),
        "excluded": len(rows) - len(valid),
        "flagged": sum(bool(r["flags"]) for r in rows),
        "flags": dict(flags),
        "stations": len({r["station"].casefold() for r in valid}),
        "start": timestamps[0] if timestamps else None,
        "end": timestamps[-1] if timestamps else None,
        "summaries": summaries,
        "facts": facts,
        "trends": trends,
        "limitations": [
            "Concentrations describe the supplied monitors and observation periods only.",
            "Missing readings are not imputed. Sampling coverage is unknown without an expected schedule.",
            "Ranks compare observed means within each pollutant; unequal sampling can affect rank.",
            "No pollution source, health outcome, forecast, or official AQI is inferred.",
            "WHO comparisons use only rows explicitly marked as 24-hour averages; source accuracy is unverified.",
            "Naive timestamps use UTC. Dates follow the confirmed import date order.",
        ],
        "reference_url": REFERENCE,
    }


def compare(current: dict, previous: dict | None) -> dict:
    if previous is None:
        return {
            "status": "no_baseline",
            "changes": [],
            "message": "Save a brief to establish a baseline.",
        }
    before = {(s["station"].casefold(), s["pollutant"]): s for s in previous["summaries"]}
    after = {(s["station"].casefold(), s["pollutant"]): s for s in current["summaries"]}
    changes = []
    for identity in sorted(set(before) | set(after)):
        old, new = before.get(identity), after.get(identity)
        item = {
            "station": (new or old)["station"],
            "pollutant": identity[1],
            "status": "matched" if old and new else "added" if new else "missing",
        }
        if old and new:
            same_duration = (
                old.get("durations") == new.get("durations")
                and old.get("unknown_duration_count", 0) == 0
                and new.get("unknown_duration_count", 0) == 0
            )
            item.update(
                {
                    "before": old["mean"],
                    "after": new["mean"],
                    "delta": round(new["mean"] - old["mean"], 3),
                    "percent": round((new["mean"] - old["mean"]) / old["mean"] * 100, 1)
                    if old["mean"]
                    else None,
                    "before_count": old["count"],
                    "after_count": new["count"],
                    "evidence": new["evidence"],
                    "previous_evidence": old["evidence"],
                    "same_duration": same_duration,
                }
            )
        changes.append(item)
    return {
        "status": "compared",
        "changes": changes,
        "message": "Descriptive snapshot comparison, not a causal or controlled trend. Check dates, averaging periods, and sample counts.",
    }
