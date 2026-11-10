# Eclipse Simulation Dashboard — Design

**Date:** 2026-11-10 · **Status:** Approved (Approach A) · **Target:** public repo `ojaogezi/eclipse-sim-dashboard`

## 1. Problem & users

A reservoir engineer runs ECLIPSE ensembles (stochastic realizations, e.g. `STOCH_STOCH_CHESS_BD_28_X1MLTP2_V2`, plus a `Nova Run` folder of sibling runs). Typical run output: `.SMSPEC`/`.UNSMRY` (summary), `.RFT` (well pressures), huge `.PRT` (QC + FIP), `.DATA` + INCLUDEs + GRDECL property files (input parameters). Today, comparing cases/parameters means opening each run in a heavy tool.

Deliverable: a dashboard that ingests a folder of runs and supports case comparison, parameter analysis, RFT and QC views, publishable to GitHub and runnable on any Windows 11 PC — with or without Python.

**Primary user:** the author (reservoir engineer, ECLIPSE background). **Secondary:** colleagues who receive the repo or a generated `dashboard.html`.

## 2. Goals / non-goals

**Goals (v1)**
1. `python build_dashboard.py <runs_folder>` → single self-contained `dashboard.html` (works offline via `file://`, no Python/internet needed on the viewing PC).
2. `streamlit run app.py` → same views, live loading from a folder.
3. Views (identical in both frontends): Overview (case table + end-point ranking), Time Series (vector × case), Parameters (per-case inputs + tornado/correlation vs a chosen end-point), RFT (pressure vs depth, well × date × case), QC (MB error, timesteps, CPU, FIP).
4. Case model = stochastic realizations; realization ID auto-parsed from file name, configurable.
5. Public GitHub repo containing code + synthetic demo ensemble only. Real data never committed.

**Non-goals (v1):** 3D grid/UNRST visualization, compositional/PVT analysis, history matching, deck editing, ERT integration, incremental/watch-mode.

## 3. Verified environment facts (this PC)

- Python 3.13; packages installed: `resdata` 6.3.2, `pandas`, `numpy`, `plotly` 6.9 (offline bundle at `plotly/package_data/plotly.min.js`, 4.85 MB), `streamlit`, `dash`, `flask`.
- resdata API paths (verified by import):
  - Summary read: `resdata.summary.Summary` (`Summary.resample`, numpy vectors, `get_values`, well list, units).
  - Summary **write** (demo generation): `Summary.writer(...)` → `add_variable`, `add_t_step`, `fwrite` — exists in 6.3.2.
  - RFT read: `resdata.rft.ResdataRFTFile` / `ResdataRFT` / `ResdataRFTCell` / `ResdataPLTCell` (note: lives in `resdata.rft`, **not** `resdata.resfile`).
  - `resdata` emits DeprecationWarnings on import — suppress with `-W ignore` / `warnings.filterwarnings` in entry points, don't let it spam the console.
- `gh` CLI authenticated as `ojaogezi`, scopes include `repo`.

## 4. Architecture (Approach A — shared core, two thin frontends)

```
                 ┌──────────────────────────── resdash/ (core) ───────────────────────────┐
runs_folder ──▶ │ discovery → summary.py · rft.py · prt.py · deck.py → bundle.py (v1 JSON) │
                 └───────────────┬───────────────────────────────────────────┬────────────┘
                                 │                                           │
                     build_dashboard.py (CLI)                        app.py (Streamlit)
                                 │ render.py (template + inline assets)     │ reads bundle or extracts live
                                 ▼                                           ▼
                       dashboard.html (self-contained)               localhost web app
```

One extraction codebase guarantees both frontends show identical data. The bundle is the contract; it is versioned (`schema` field) so old bundles keep working.

### Repo layout

```
eclipse-sim-dashboard/
├── README.md  ·  LICENSE (MIT)  ·  requirements.txt  ·  .gitignore
├── build_dashboard.py      # CLI entry
├── run_dashboard.bat       # Windows convenience: deps check → build → open
├── app.py                  # Streamlit entry
├── resdash/
│   ├── __init__.py · discovery.py · summary.py · rft.py · prt.py · deck.py
│   ├── bundle.py           # assemble + validate + version schema
│   ├── render.py           # HTML assembly: template + inline JS/CSS/plotly.min.js + data
│   └── assets/             # dashboard.js, dashboard.css, template.html
├── demo/
│   ├── make_demo.py        # writes synthetic ensemble (8 realizations) via Summary.writer
│   └── runs/<REAL-*/>      # SMSPEC/UNSMRY (+RFT, +PRT-lite, +DATA) per case, committed
├── demo_dashboard.html     # pre-built from demo/runs, committed → instant try
└── tests/                  # pytest
```

## 5. Data flow & bundle schema

**Discovery** (`discovery.py`): recursive scan; a *case* = directory basename or file basename having `.SMSPEC`/`.UNSMRY` pair (both extensions and uppercase/lowercase). Optional attachments matched by same base: `.RFT`, `.PRT`, `.DATA` (+ `INCLUDE` files referenced). Realization ID = regex capture (default tries `_V(\d+)`, `REAL-(\d+)`, `_(R\d+)`, falls back to whole basename); overridable via CLI `--realization-regex`. Runs missing UNSMRY are skipped with a warning; junk ignored. Deduplicate case names.

**Summary extraction** (`summary.py`): read SMSPEC/UNSMRY once per case; export every vector as parallel arrays keyed by vector key (`TIME` days, `YEARS`, `DATE` ISO, then `FOPR`, `WOPR:WELL` …) with unit metadata. Downstream consumers never call resdata.

**RFT** (`rft.py`): per well × survey date: depth (MASKED or CELL depth), pressure (and PLT rates if present). Cap surveys per well to keep bundle sane (default 50, configurable).

**PRT** (`prt.py`): stream line-by-line, bounded memory. Capture: max/last material-balance error, timestep count + shortest-step histogram bins, CPU time, initial FIP table per region (oil/gas/water surface + reservoir volumes) if present.

**Deck parameters** (`deck.py`): parse `.DATA` + INCLUDEs (handle `INCLUDE 'file'` recursion): scalar keywords that differ across cases — `MULTIPLY`/`MULTX…` targets, `PORO`/`PERM` multipliers, `WCONPROD`/`WCONINJE` control modes & limits, schedule start/end dates, `EQUIL` datum & contacts, `PVT`/`SAT`/`EQLNUM` region counts. Plus GRDECL statistics per property file (ACTNUM-weighted mean/P10/P50/P90 of PORO, PERMX/Y/Z, NTG; MULTIPLY region counts). GRDECL parse is chunked (`numpy.fromstring` per line batch) for speed.

**Bundle (v1):**

```json
{
  "schema": 1,
  "generated_utc": "...",
  "source_folder": "C:/.../runs",
  "cases": [{
    "name": "STOCH_..._V2", "realization": "V2", "folder": "...",
    "files": {"summary": true, "rft": true, "prt": true, "data": true},
    "params": {"PORO_MEAN": 0.234, "PERMX_P50": 112.5, "MULTX": 1.5, "...": 0},
    "vectors": {"TIME": [0.0, ...], "DATE": ["2020-01-01", ...],
                 "FOPR": {"unit": "SM3/DAY", "data": [...]}, ...},
    "rft": [{"well": "P1", "date": "2021-06-01", "depth": [...], "pressure": [...]}],
    "qc": {"mb_error_max": 0.0031, "timesteps": 1234, "cpu_hours": 12.3,
            "fip_regions": {"1": {"oil_sm3": 1.2e7, "gas_sm3": 0, "water_sm3": 3.4e7}}}
  }]
}
```

Size control: floats rounded to 6 significant digits (encode as plain JSON numbers); vectors longer than 4000 points decimated by min–max preserving thinning (peaks kept); warn + count in validation summary. Expected bundle for 8 demo cases ≈ 1–5 MB; for 45 MB UNSMRY real cases ≈ 15–40 MB → acceptable single-file HTML.

## 6. Frontends

**Static (`render.py`)**: single HTML: inline `<style>`, inline plotly.min.js, inline `<script id="bundle">` JSON. No external fetches ever (works from `file://`, Edge/Chrome). Vanilla JS, tabbed SPA:

- **Overview** — case table (name, realization, key end-points: FOPT/FGPT/FWPT at last date, FPR last, qc flags), sortable; end-point ranking bar chart (P10/P50/P90 across realizations).
- **Time Series** — pick vector(s) × case(s); x-axis days/date; log-y toggle; per-well drill-down (WOPR/WBHP for chosen well); export current series as CSV button.
- **Parameters** — table of `params` per case; pick an end-point (e.g. FOPT) → tornado of parameter correlation (Spearman, computed client-side) + scatter (param × end-point, case-colored).
- **RFT** — well dropdown × survey-date dropdown × case overlays; depth on y (inverted), pressure on x.
- **QC** — MB error vs time per case (if extracted), timestep stats table, FIP volume table.

**Streamlit (`app.py`)**: same five tabs, reads a bundle JSON if given (`--bundle`) or extracts from a folder (`st.text_input` path + cache); uses `st.plotly_chart`. No new extraction logic.

## 7. Error handling

- Missing RFT/PRT/DATA for a case → tab shows "not available for this case"; never aborts the build.
- Unparsable keyword / unknown GRDECL property → skipped, collected into a warnings list printed in the build summary (cases found, per-case files used, warnings, elapsed).
- PRT streamed with O(1) memory; `.PRT` > 2 GB still fine.
- Bundle validation (`bundle.py`): required keys, unique case names, `schema` check; clear error if schema newer than the frontend understands.
- Streamlit: friendly errors if folder path invalid or no cases found.

## 8. Testing

`pytest` (resdata writer → extractor round-trips):
- `test_summary.py` — write synthetic summary via `Summary.writer`, extract, assert keys/units/values match to tolerance.
- `test_deck.py` — fixture `.DATA` + GRDECL; assert params & stats.
- `test_prt.py` — fixture PRT text (MB error line, FIP table); assert parsed values.
- `test_rft.py` — demo RFT fixture (see risks) → wells, dates, arrays.
- `test_bundle.py` — schema validation, size controls (rounding/decimation), degrade-with-missing-files.
- `test_render.py` — build demo dashboard: file exists, contains plotly marker + schema marker, JSON parses, no `http://`/`https://` resource references.
- `test_demo.py` — `make_demo.py` regenerates byte-stable file set (idempotent).

CI: GitHub Actions on push (windows-latest + ubuntu-latest, `pip install -r requirements.txt`, `pytest`, rebuild `demo_dashboard.html` artifact). Optional but included — cheap and proves Windows portability continuously.

## 9. Windows 11 portability & delivery

- `run_dashboard.bat`: `py -3 -m pip install -r requirements.txt` (first run only), `py -3 build_dashboard.py %~1`, `start "" dashboard.html`. Documented fallback if `py` launcher missing.
- Viewing any generated `dashboard.html` needs nothing but a browser — repo ZIP → double-click `demo_dashboard.html` works.
- `.gitignore` excludes real-data outputs: `dashboard.html`, `*.UNSMRY`/`*.SMSPEC`/`*.PRT`/`*.RFT` outside `demo/runs`, `__pycache__/`, `.streamlit/`.
- Publish: `gh repo create ojaogezi/eclipse-sim-dashboard --public --source . --push` after MIT `LICENSE`, README with screenshots + 3-line quickstarts (view demo / build yours / streamlit).

## 10. Demo ensemble plan

8 realizations of a synthetic waterflood: 1 injector + 3 producers, 10 years monthly. Realization knobs (also written into each `params`): PORO field ×{0.85,1.0,1.15}, PERMX ×{0.7,1.0,1.4}, MULTX {1,2}, WCT target variance → spread in FOPT for tornado views. `make_demo.py` uses `Summary.writer` for SMSPEC/UNSMRY; writes small `.DATA` + GRDECL; writes a minimal `.PRT` text (hand-authored template with FIP table + MB error lines).

## 11. Risks & mitigations

| Risk | Mitigation |
|---|---|
| resdata has **no RFT writer** → demo/tests can't round-trip RFT | Check `ResdataRFT` write support at implementation; else write a minimal spec-conformant RFT binary via `struct` (format is short: keywords + arrays), or mark demo RFT as optional and unit-test the reader against a checked-in 2-survey fixture generated once. |
| 45 MB UNSMRY → very large single HTML | 6-sig-fig rounding + min–max thinning at 4000 pts; measure demo first; document `--max-points` knob. |
| PRT format varies by ECLIPSE version | Parse defensively (regex families, multiple known layouts); missing section → warn + skip, never fail. |
| Vector key explosion (thousands of region vectors) | Extract all, but dashboard groups by family (F/W/C/R/L/A) with searchable picker; bundle stores parallel arrays (compact). |
| Streamlit on locked-down PCs | Static HTML is the primary path; Streamlit optional. |

## 12. Milestones

1. Core extraction (summary → bundle → minimal HTML) with demo ensemble — end-to-end slice.
2. RFT + PRT + deck parameters into bundle; tabs Parameters/RFT/QC.
3. Streamlit app; `run_dashboard.bat`; README + screenshots.
4. Tests green + CI; build & commit `demo_dashboard.html`; push to GitHub.
