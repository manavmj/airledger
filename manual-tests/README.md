# AirLedger manual upload tests

**Every observation in this folder is synthetic test data. None represents real air conditions.** The tests verify software behavior, not environmental or health accuracy.

Download the complete [manual test pack](https://github.com/manavmj/airledger/raw/refs/heads/main/manual-tests/AirLedger-Manual-Test-Pack.zip) and extract it before choosing files in the upload control. Do not upload the ZIP itself. Files are also included in the full source ZIP under `manual-tests/`.

## Before you start

- Use a fresh browser profile or incognito window if you want a clean first-brief baseline without deleting existing records.
- Keep the **same browser/profile and host address** throughout the baseline/comparison sequence. `localhost` and `127.0.0.1` have separate cookies.
- Upload one file at a time. Review mappings, use **Day / month / year** where stated, tick the import confirmation, then choose **Review & analyse**.
- Start with **rules-based** briefs to check exact calculations. AI selection may include fewer facts or order them differently; calculated values must remain identical.
- Expected concentrations below are normalized to **µg/m³**. Reference comparisons describe explicitly supplied 24-hour readings, not official AQI.

## What to upload and expect

| File | Purpose | Expected result |
| --- | --- | --- |
| `01_clean_baseline.csv` | Clean CSV and first saved brief | 6 rows included, 0 excluded, 2 locations. TEST North mean **30**, median **30**, p95 **39**; TEST South mean **15**. North ranks first for PM2.5. |
| `02_comparison_next_period.csv` | Compare against the saved baseline | 6 included. North mean **60**, South **15**. For the same audience: North **+30 (+100%)**, South **0 (0%)**. |
| `03_messy_readings.csv` | Mixed units, missing/negative values, duplicate and conflict handling | 10 rows total, **4 included / 6 excluded**, 3 included locations. North mean **27**, South **12**, East PM10 **50**. `0.024 mg/m3` becomes `24 µg/m³`; raw cells remain unchanged. |
| `04_no_averaging_period.csv` | Prevent unsupported daily guideline claims | 2 included, mean **90**. Averaging period is unknown; **no WHO 24-hour reference finding** should be created. No official AQI should be invented. |
| `05_all_invalid.csv` | Abstain when evidence is unusable | **0 included / 4 excluded**. No location rank. Composing a brief must fail with no valid evidence; no fabricated brief is saved. |
| `06_fixed_columns_and_dates.tsv` | Explicit mapping, fixed pollutant/unit, slash dates | Manually map `PM25_reading` to concentration, choose fixed **PM2.5** and **ug/m3**, choose **DMY**. 3 included, mean **20**, dates **3–5 April 2026**, not March. |
| `07_outlier_retained.csv` | Flag outliers without silently deleting them | 5 included, **1 flagged**, 0 excluded. Mean **208.6**, median **11**, p95 **802.4**. The `1000` reading is flagged as a statistical outlier and remains included. |
| `08_security_text.csv` | Treat source labels as text; safe spreadsheet export | 3 included, 2 locations. The HTML-looking label displays as literal text and **does not execute or open an alert**. The formula-looking location is prefixed with an apostrophe in the cleaned CSV export. |
| `09_duplicate_headers.csv` | Reject malformed schema | Import rejected: column names must be unique. No analysis is created for this file. |
| `10_formula_cells.xlsx` | Refuse formulas in uploaded workbooks | Import rejected: formula cells are not accepted. Export calculated values before retrying. |
| `11_clean_baseline.xlsx` | Equivalent Excel workflow | Same numerical results as `01_clean_baseline.csv`: 6 included, North mean 30, South mean 15. |

## A. Clean evidence and traceability

1. Upload `01_clean_baseline.csv`.
2. Confirm automatic mappings for location, timestamp, pollutant, value, unit and duration.
3. Confirm **6 included**, **0 excluded**, North **30** and South **15**.
4. Open North's **Trace source rows** link. It must link to **R2, R3, R4**, with values **20, 30, 40**.
5. WHO 2021 PM2.5 24-hour reference checks should count North **3/3** and South **1/3** above 15. A value equal to 15 is not counted as above the guideline.
6. In Briefing studio, select **Ward officer**, English, and easy reading. Compose and save the brief.
7. In a fresh workspace, it should say there is **no baseline**. An existing prior ward brief will instead be used as the baseline.

## B. Previous-brief comparison

1. After saving the baseline ward brief, upload `02_comparison_next_period.csv` in the same browser session.
2. Analyse it, then compose another brief for **Ward officer**.
3. North should change **30 → 60**, **+30 µg/m³**, **+100%**. South should remain **15 → 15**, **0%**. Each location has 3 readings in both periods.
4. In the archive, reopen the earlier brief. It must still show the original North observations and original source fingerprint.
5. Select **School team** and compose its first brief. With no prior school brief, it should have **no baseline**, even if ward briefs exist.

## C. Data quality

With `03_messy_readings.csv`, use the **Flagged only** filter:

- **R4:** excluded duplicate.
- **R6:** excluded missing concentration.
- **R7:** excluded unknown/unsupported `ppb` unit; no guessed gas conversion.
- **R8:** excluded negative concentration.
- **R10 and R11:** both excluded conflicting readings at the same location/time/pollutant/averaging period.
- **R2:** retained; raw `0.024 mg/m3`, normalized **24 µg/m³**.

Verify that no missing value was filled in and every excluded row still appears in the source ledger/export. Use the separate outlier file to distinguish a **flagged-but-retained** observation from an excluded observation.

## D. GenAI, language and audience

1. Follow `docs/API_KEYS.md` in the full source project to configure Gemini. Restart the server and refresh the page.
2. With the clean baseline file, choose **Suggest mapping with AI**. Review the suggestion; it must still require your confirmation.
3. Generate with **Use GenAI to select and prioritize evidence** checked. The saved draft must say **Gemini-selected evidence**. Numbers and row links must agree with Evidence room; a configured-key badge alone does not prove a successful provider call.
4. Generate school, housing society and ward briefs. School actions should concern activity plans/gate idling; society actions facilities/dust/idling; ward actions inspections/follow-up. Proposed actions must not be described as already completed.
5. Generate English, Hindi and Marathi advisories at both reading levels. Values/evidence should remain consistent; vulnerable-group guidance and limitations should remain present. AI may select different subsets across separate calls, so compare each draft to its own evidence rather than expecting identical selected facts.
6. For an explicit failure test, stop the server, start it with an intentionally invalid key and request an AI brief. Expect an error and **no new AI-labelled brief**. Restore your valid key and restart afterward. Do not publish real keys in test files.

The model chooses verified IDs. It cannot add arbitrary output sentences through the API contract. This does not validate sensor truth or guarantee useful model prioritization.

## E. Access and accessibility

- Test the whole workflow with Tab/Shift+Tab/Enter and visible focus. Close source dialogs with Escape.
- Use 200% browser zoom and a narrow viewport. Tables should scroll rather than hide evidence.
- Open the app in a different browser profile: earlier session records should not appear there.
- Print a brief and download its evidence pack. Check that the pack contains original raw cells and source fingerprints.
- Clear workspace **only if you intend to delete that session's records**; previous source/brief routes should then stop resolving.

## Optional fixture verification

From the full project's root, after installing its requirements:

```powershell
.\.venv\Scripts\python.exe manual-tests\verify_fixtures.py
```

This checks fixture results against the actual analysis functions. It makes no model calls and writes no records to your application database. Manual browser steps above still require human testing.
