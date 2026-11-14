# Build verification

Verified on Python 3.12.14 in a clean virtual environment using `requirements.txt` and the recorded dependency constraints.

- **44 automated tests passed.** Includes parsing/normalization, grounded-output validation, multilingual values/evidence, end-to-end API snapshots and exports, session isolation, retention, limits and security boundaries.
- JavaScript syntax: `node --check app/static/app.js` passed.
- HTML structure: 79 unique IDs; static label targets and ARIA heading references resolve. This is a structural check, not a browser accessibility audit.
- Dependency consistency: `pip check` reported no broken requirements.
- Python source was formatted with Ruff 0.14.5. Runtime does not require Ruff.

## Bounded synthetic benchmark

Command: `python -m tests.benchmark`

| Measure | Result |
| --- | ---: |
| Synthetic readings | 20,000 |
| Synthetic locations | 50 |
| Input bytes | 896,053 |
| Parse | 0.0781 s |
| Normalize | 0.0946 s |
| Summarize | 0.0197 s |
| Combined computation | **0.1924 s** |

One run on this build machine; not a latency SLA. Excludes file transfer, SQLite, browser rendering and model latency. No benchmark observations are inserted into the application. Displayed station charts are capped at 12 locations and timeline charts at 90 days; full readings remain in the ledger/exports. Gemini's input is capped at 300 computed facts. History queries project metadata rather than loading every raw snapshot.

## Verification limits

No browser-control tool was available through the managed preview workflow, so no browser preview server was started. Rendering, real keyboard/screen-reader behavior, contrast tooling, responsive screenshots and print layout still need the manual checks in TESTING.md. Static delivery and API behavior were tested through the actual ASGI application.

No Gemini API key or real civic dataset was provided. Live provider availability, authentication, quality of model selections, translation review and source-monitor accuracy remain unverified. Rules-based briefs work without credentials and are clearly labelled. Tests use synthetic observations and isolated provider doubles, never simulated production responses.

Initial verification was completed locally. The subsequent private GitHub handoff distributes source files only; it does not deploy a running website.
