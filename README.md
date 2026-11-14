# AirLedger

**A clearer case for local action.** An evidence-first Civic Air Quality Briefing Studio for the PromptWars warm-up challenge.

AirLedger turns uploaded readings into a reviewed source ledger, descriptive analysis, role-specific proposed interventions, and internal/citizen briefs. Its visual direction is a civic field desk: paper, forest ink, terracotta annotations, editorial type, and numbered evidence receipts. There are no seeded monitors, invented measurements, or fake live dashboards.

## Run locally

Python **3.11+** is required; Python 3.12 is recommended.

**Windows:** copy/download the project to your own computer, extract it completely, then double-click `start_windows.bat`. It creates a local Python environment, installs dependencies, starts AirLedger and opens your default browser at **http://127.0.0.1:8765** once the server is ready. Keep its terminal window open while using the app. This launcher needs Python installed and an internet connection for the initial dependency download. Do not run the batch file from inside a ZIP viewer.

`127.0.0.1` always means **the computer running your browser**. A server running inside a remote Codex workspace is not reachable through your computer's localhost without a supported forwarding connection. The commands below must run on the same computer as Chrome when no forwarding is available.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open **http://127.0.0.1:8000**. On Windows, activate with `.venv\Scripts\activate` instead. No frontend build, database setup, Node installation, external fonts, or CDN is needed. The machine-readable API schema is at `/openapi.json`. The dependency constraints in `requirements.lock` reproduce the verified clean Python environment.

### Connect Gemini

For exact Windows commands and connection checks, see [docs/API_KEYS.md](docs/API_KEYS.md). For ready-to-upload synthetic CSV/TSV/XLSX files with expected results, see [manual-tests/README.md](manual-tests/README.md).

In the same shell, **before starting the server**, set `GEMINI_API_KEY` to your own Google Gemini API key. Set `GEMINI_MODEL` if you need a different compatible model; the default is `gemini-2.5-flash`. `.env.example` documents the available settings; `.env` files are **not automatically loaded**. Use your shell or a secret manager, never client JavaScript or a committed file.

The header reports whether a key is configured, not whether provider authentication has been verified. A live request may fail because of an invalid key, model access, quota, or network conditions. Failed AI calls do not save a brief and do not silently fall back to rules. An explicitly labelled rules-based mode remains available without credentials.

No live Gemini call was verified in the build environment because it has no API key. Provider boundary and invalid-output behavior are covered with isolated test doubles, labelled as such in the test code.

## Judge walkthrough

1. Upload your CSV, TSV, TXT, or single-sheet XLSX, or paste a table with headers.
2. Review the column mapping. AI mapping, when connected, is a suggestion requiring confirmation. Confirm units, pollutant and slash-date order; timezone-free timestamps use UTC.
3. Analyse. Inspect the included/excluded counts, quality flags, pollutant-specific location ranks and daily sample means. Open a source receipt to see untouched input cells.
4. Choose a ward officer, housing society or school audience. Choose English, Hindi or Marathi, and easy or standard reading.
5. Compose a brief. AI mode prioritizes verified findings and allowed actions; rules mode is explicitly labelled. Both create an internal note and citizen advisory, including extra care for vulnerable people.
6. Download the cleaned CSV and the JSON evidence pack, or print the brief. The pack includes the source fingerprint, raw row snapshots, calculations, selected evidence, proposed actions, and previous-brief comparison.
7. Upload a new period and compose for the **same audience**. The comparison matches location and pollutant, shows sample counts and deltas, and warns when averaging periods are unknown or differ. Prior snapshots remain immutable.

`tests/fixtures/messy_readings.csv` is **synthetic test data only**, intentionally labelled `TEST`. You may upload it to exercise the workflow, but it is not a real civic dataset. No supplied real dataset accompanied the challenge image.

## Input contract

| Field | Required | Treatment |
| --- | --- | --- |
| Location / monitor | Yes | Text; case-insensitive grouping, original label retained |
| Timestamp | Yes | ISO 8601, or explicitly selected DMY/MDY dates; UTC normalization |
| Concentration | Yes | Finite nonnegative number, decimal point; no silent comma interpretation |
| Pollutant | Column or fixed selection | PM2.5, PM10, NO2, SO2, O3, CO |
| Unit | Column or fixed selection | µg/m³ / ug/m3 and mg/m³; per-row conversion supported |
| Averaging period, hours | Optional | Required to qualify a row for a 24-hour WHO reference comparison |

Fixed units/pollutants only apply when the respective column is **not mapped**. An empty cell in a mapped unit column is not filled from the fixed-unit control. Wide tables work by mapping one concentration column and choosing its fixed pollutant; reshape to long form for multiple pollutants in one import. XLSX workbooks must have one sheet and no formulas. Dates with month names, multirow headers, merged layouts, PDFs, and images are outside this version's input contract.

Limits: 5 MB source, 20,000 rows, 50 columns, 500 characters per cell, 30 MB expanded XLSX. Concentrations above 1 billion µg/m³ are excluded by a numerical safety bound, not a scientific plausibility threshold. Gas ppb/ppm values are excluded because conversion requires documented conditions. Unknown units, negative/nonfinite readings, missing required values, conflicting readings and exact duplicates remain visible but are excluded from statistics.

## Data science pipeline

1. **Ingestion:** detect supported delimiters; validate shape/headers; hash source bytes; preserve logical source-row IDs and raw cells.
2. **Schema review:** conventional header aliases, optional Gemini suggestions, explicit user confirmation of mapping and import assumptions.
3. **Preprocessing:** normalize timestamps and mass units; reject ambiguous values; identify duplicate/conflicting location–time–pollutant–duration records. No imputation.
4. **Quality review:** missing/invalid values and averaging durations; robust MAD outlier flags with at least five observations. Outliers are retained. When MAD is zero, flag deviations larger than max(1 µg/m³, 50% of the median). This is a screening heuristic, not sensor validation.
5. **Exploration:** count, mean, median, min/max, interpolated p95; within-pollutant observed-mean ranks; daily sample means; first/last observed daily comparison for each location and pollutant.
6. **Reference comparison:** WHO 2021 24-hour reference values for PM2.5 (15), PM10 (45), NO2 (25), SO2 (40), all in µg/m³. Only explicit 24-hour rows qualify. These are guideline comparisons, not official AQI or local legal exceedance determinations. Overlapping intervals/source validity are not verified.
7. **Synthesis:** grounded evidence/action selection, multilingual controlled rendering, human-reviewed proposed interventions.
8. **Longitudinal review:** audience-specific previous-brief snapshot comparison with added/missing locations, absolute/percentage changes and averaging-period warnings. A zero previous mean produces no percentage claim.

No predictive model is trained. Arbitrary sparse uploads cannot justify forecasting, causal attribution, or citywide coverage claims. Expected sampling schedules are absent, so missing-interval completeness percentages are not invented. Sampling mix, overlapping averaging intervals and station calibration can affect every descriptive result.

## GenAI without fabricated numerical claims

This is **constrained generation**, not open-ended chat:

```text
raw table → confirmed schema → deterministic facts + source IDs
                                      ↓
                          Gemini selects fact/action IDs
                                      ↓
                         strict allowlist validation
                                      ↓
                   controlled language renderer + evidence links
```

The model sees column labels for mapping, or computed facts and location labels for briefing. It does not receive raw cells, tools, browsing capabilities, secrets, or permission to execute code. Its output contract permits only IDs; unknown/duplicate IDs, additional prose and actions outside the chosen role are rejected. Values and citations come from application computations. Gemini selection itself can still be poor or manipulated by misleading labels; the UI requires human review. This limits factual fabrication; it does not certify input truth or guarantee perfect relevance.

AI inputs are capped at the first 300 computed facts for bounded provider cost. All deterministic analysis and exports retain the complete dataset. Briefs include at most eight selected findings under the normal generation prompt. Larger datasets should be split into purposeful local briefs.

English, Hindi, and Marathi advisory templates are provided at two wording levels. They are controlled templates, not unconstrained machine translations, certified translations, or measured reading-grade guarantees. Review them locally before public distribution.

## Test

```bash
python -m unittest discover -s tests -v
node --check app/static/app.js  # optional, if Node is installed
```

See [docs/TESTING.md](docs/TESTING.md) for coverage and the manual acceptance script. All test observations are synthetic. Tests use temporary SQLite databases and do not touch your workspace data.

## Architecture

| Module | Responsibility |
| --- | --- |
| `app/ingest.py` | Bounded tabular parsing and header suggestions |
| `app/analysis.py` | Pure, independently testable normalization, descriptive analysis and comparison |
| `app/briefing.py` | Provider adapter, grounded contracts, role policies, multilingual renderer |
| `app/storage.py` | Parameterized SQLite access, browser-session scoping and retention |
| `app/main.py` | Typed API contracts, request boundary, exports and static delivery |
| `app/static/` | Dependency-free responsive UI, accessible tables, SVG observations and print layout |

## Privacy, security and production scope

Opaque HttpOnly SameSite=Strict cookies scope records to this browser session. SQLite stores a hash of the session token. Cross-origin mutations are blocked, record lookups enforce ownership, requests/files are bounded, XML parsing uses defusedxml, workbook formulas are refused, CSV exports defuse formula injection, and untrusted UI values use text nodes. CSP disallows inline scripts, framing, external resources, and arbitrary client-side connections. API keys never enter the browser.

Mutating requests are limited to 20 per minute per browser session in this process. There are at most 10 datasets and 20 briefs per session. Records expire after 24 hours and are purged on the next database access; idle servers do not run background deletion. Clear workspace deletes that session's records, not forensic disk traces. A stolen cookie grants access to its session; there are no named-user accounts.

This is a **local hackathon application**, not a production multi-tenant service. Before exposing it publicly, add authenticated users, HTTPS with `AIRLEDGER_SECURE_COOKIE=1`, trusted host configuration, durable/distributed rate limits, global storage quotas, an active retention job, and appropriate deployment monitoring. SQLite storage and the in-process limiter assume one application process. Do not upload personal/confidential information; AI mode shares computed statistics and location names with Google.

## Project status

This source package contains the locally built application. It does not host a running website. Extract the entire ZIP and run `start_windows.bat` on Windows; see `START_HERE.txt` for the shortest setup path. Browser-based visual/accessibility verification and live Gemini validation were unavailable in this environment; automated API/data tests and syntax checks are provided. No claim of certified accessibility or zero hallucinations is made.

Reference: [WHO Global Air Quality Guidelines, 2021](https://www.who.int/publications/i/item/9789240034228).
