# Verification and judge acceptance cases

## Automated suite

Run `python -m unittest discover -s tests -v`. The suite uses the standard library, FastAPI's test client and temporary databases. Synthetic observations and provider doubles appear only in tests.

| Area | Checks |
| --- | --- |
| Ingestion | UTF-8 BOM, semicolon/TSV, quoted multiline records, duplicate headers, ragged rows, empty/oversized/unsupported files, row limit, XLSX values, formulas and multiple sheets |
| Cleaning | Mixed units, raw-cell preservation, source IDs, duplicates, conflicts, missing values, ppb rejection, explicit decimal/date order, nonfinite/negative/overflow values, fixed-field confirmation and duplicate mappings |
| Analysis | Exact known means/p95/ranks, 24-hour qualification, daily endpoint evidence, outlier retention, zero baseline, added/missing locations and unknown averaging duration |
| Briefs | Role-specific actions, both wording levels across all languages, preserved numeric/evidence values, missing API key, unknown IDs, duplicate IDs, extra prose, wrong-role actions, empty evidence and sanitized provider failure |
| API/security | End-to-end snapshots and immutable evidence exports, file upload, session isolation for read/write/export, cross-origin rejection, CSP/nosniff, CSV formula injection, XSS-safe DOM boundary, failed-AI no-save behavior, invalid mapping, role-specific baselines, clearing, pagination, rate/body limits, validation and static delivery |

## Manual acceptance script

These checks are supplied for the local browser; they were not executed by a browser agent in the build environment.

1. Start the server from the README. Verify that the initial intake has no fake observations or populated charts.
2. Tab through navigation, file selection, paste input and buttons. Ensure focus stays visible. Activate the skip link; it should focus the workspace.
3. Upload the **synthetic** fixture. Confirm the source preview and mappings. Before checking confirmation, choose Analyse: expect a clear error without losing your input.
4. Confirm the mapping. Expect 10 source readings, 4 included and 6 excluded. TEST North should have PM2.5 mean 27 µg/m³. Select PM10: TEST East should show 50 µg/m³. Never compare the bars as a shared health-risk scale.
5. Open North's receipt. Verify raw `0.024 mg/m3` and normalized `24 µg/m³`, with source row R2. Close with Escape and verify focus returns to the source link.
6. Toggle Flagged only. See duplicates, two conflicting rows, missing/negative values, and the unsupported gas unit. Download the cleaned CSV and inspect dispositions.
7. Without a Gemini key, ensure AI is visibly disconnected and rules mode is labelled. Generate each audience's brief; school actions should concern activity plans/gate idling, not ward inspections.
8. Generate Hindi and Marathi advisories at each wording level. Verify document language attributes with assistive technology, retained numbers/evidence and vulnerable-group guidance. Review translation quality with a fluent speaker before publication.
9. Add a real key on the server, restart, and generate in AI mode. Verify that a successful provider response saves a Gemini-labelled brief. With an invalid key, expect an error and no new saved brief; no silent rules fallback.
10. Modify North's concentrations to 48 and 60 in a second file. Generate for the same audience: the mean changes from 27 to 54 µg/m³, a +27 / +100% descriptive change. Generate for a different audience without a prior brief: no baseline should be claimed.
11. Open the first archive entry. It should retain the old 24/30 observations and its original hash. Export its evidence pack and verify raw rows, selected fact IDs and baseline links. Print the brief; navigation and controls should be omitted.
12. In another browser profile/incognito session, request the original dataset/brief URLs: expect 404. Cross-session history should be empty.
13. At 375 px, 768 px and 1440 px widths, inspect the layout, horizontal table scrolling, focus rings and dialog containment. Test 200% zoom, reduced motion and a screen reader. Charts have adjacent values and a daily-values disclosure.
14. Clear the workspace. History and all previous evidence routes should become unavailable to that session.

## Not verified here

- Live Gemini authentication/model availability and real-provider output quality: no key supplied.
- Browser rendering, contrast tooling, keyboard/screen-reader operation and print output: managed browser-control tool unavailable.
- Accuracy/calibration of any uploaded real monitor data: no real dataset supplied.
- Certified translation quality or quantified reading grades.

## Efficiency check

Run `python -m tests.benchmark` for a generated 20,000-row synthetic benchmark. No network or model call is needed for descriptive analysis. File, row, column, cell, workbook-expansion, browser-chart and provider-fact limits bound the major processing paths. This measures in-process parsing, normalization and summarization, excluding uploads, SQLite persistence, browser rendering and AI latency. Timing varies by machine.
