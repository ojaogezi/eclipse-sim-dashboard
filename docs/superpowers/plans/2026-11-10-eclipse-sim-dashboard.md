# Eclipse Simulation Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a stochastic-ensemble ECLIPSE analysis dashboard: shared extraction core → versioned JSON bundle → self-contained offline `dashboard.html` + Streamlit app, published as public repo `ojaogezi/eclipse-sim-dashboard`.

**Architecture:** `resdash/` package extracts summary/RFT/PRT/deck data per discovered case into a schema-versioned bundle; `render.py` inlines plotly.min.js + data + vanilla-JS SPA into one HTML file; `app.py` (Streamlit) reads the same bundle. Spec: `docs/superpowers/specs/2026-11-10-eclipse-sim-dashboard-design.md`.

**Tech Stack:** Python 3.13, `resdata` 6.3.2 (Summary reader/writer, `resdata.rft.ResdataRFTFile`), `numpy`, `plotly` 6.9 (offline `package_data/plotly.min.js`), `streamlit`, `pytest`. No other runtime deps.

## Global Constraints

- Run all commands from repo root `C:\Users\ogezi\.zcode\workspace\draft-2af6b49e-f403-4519-bcf5-e8a32da46c9b`.
- **IMPORT HAZARD:** the pip library is `resdata`; OUR package is `resdash` (one letter apart!). The ONLY legitimate pip-`resdata` imports in this codebase are `from resdata.summary import Summary` and `from resdata.rft import ResdataRFTFile`. Every other import of our own modules MUST be `from resdash.<module> import ...`. Double-check every import line against this rule.
- resdata import emits DeprecationWarnings: every entry point (CLI, demo, tests via `pytest.ini`) sets `filterwarnings = ignore::DeprecationWarning`. Never let warnings spam output.
- Bundle floats: 6 significant digits (`round6`); time series thinned min–max preserving at `max_points` (default 4000). Bundle always carries `schema: 1`.
- Static HTML: ZERO external URLs — no CDN, no fonts, no fetch. Test asserts no `http://`/`https://` in generated HTML.
- Real ECLIPSE data is NEVER committed. `.gitignore` blocks all ECLIPSE extensions; only `demo/runs/**` is re-included.
- Windows-first: use `pathlib`, no POSIX-only calls; `.bat` uses `py -3` launcher.
- TDD: write failing test first in every task. Commit after every task. Test command: `python -m pytest tests -q`.
- P1/P10/P50/P90 convention: P10 = optimistic (high), P50 = median.

---

### Task 1: Project scaffolding

**Files:**
- Create: `requirements.txt`, `.gitignore`, `LICENSE`, `pytest.ini`, `resdash/__init__.py`, `tests/__init__.py`, `tests/conftest.py`

**Interfaces:**
- Produces: package `resdash` importable from repo root; pytest configured with `testpaths = tests`.

- [ ] **Step 1: Create scaffold files**

`requirements.txt`:
```
resdata>=6.3
numpy>=1.26
plotly>=5.18
streamlit>=1.30
pytest>=7.4
```

`.gitignore`:
```
__pycache__/
*.pyc
.pytest_cache/
dashboard.html
bundle.json
demo/bundle.json
.streamlit/

# Real ECLIPSE output must never be committed
*.UNSMRY
*.SMSPEC
*.PRT
*.PRTX
*.DBPRTX
*.RFT
*.RSSPEC
*.EGRID
*.INIT
*.UNRST
*.DBG
*.ECLE
*.ECLEND
*.h5
*.INSPEC
*.MSG
*.RTEMSG
*.TELE
*.DATA
*.GRDECL
*.INC

# The synthetic demo ensemble is intentionally committed
!demo/runs/**
```

`LICENSE` (MIT, full text, `Copyright (c) 2026 Oja Ogezi`).

`pytest.ini`:
```
[pytest]
testpaths = tests
filterwarnings =
    ignore::DeprecationWarning
```

`resdash/__init__.py`:
```python
__version__ = "0.1.0"
```

`tests/__init__.py`: empty. `tests/conftest.py`:
```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
```

- [ ] **Step 2: Verify pytest runs green on empty suite**

Run: `python -m pytest tests -q`
Expected: `no tests ran` (exit code 5 is fine — no failures).

- [ ] **Step 3: Commit**

```bash
git add -A && git commit -m "chore: project scaffolding"
```

---

### Task 2: Summary write/extract round-trip

**Files:**
- Create: `resdash/demo_io.py` (shared writer used by tests AND demo generator), `resdash/summary.py`, `tests/test_summary.py`

**Interfaces:**
- Produces:
  - `resdash.demo_io.write_summary(case: str, start: datetime, days: list[float], vectors: dict[str, dict], out_dir: Path) -> None` where `vectors = {"FOPR": {"unit": "SM3/DAY", "data": [...]}}`. Writes `<out_dir>/<case>.SMSPEC` + `.UNSMRY` (runs with cwd temporarily set to `out_dir`).
  - `resdash.summary.extract_vectors(smspec_path: str, max_points: int = 4000) -> dict` → `{"TIME": [days], "DATE": ["YYYY-MM-DD"], "FOPR": {"unit": "SM3/DAY", "data": [...]}, ...}` (all vector keys from SMSPEC).
  - `resdash.summary.round6(v: float) -> float`, `resdash.summary.thin_minmax(values: list[float], max_points: int) -> list[int]` (indices).

- [ ] **Step 1: Probe the resdata writer/reader API (adjust names below only if these differ)**

```bash
python -W ignore -c "
from resdata.summary import Summary
import datetime, inspect
w = Summary.writer('X', datetime.datetime(2020,1,1), 1, 1, 1)
print('writer methods:', [m for m in dir(w) if not m.startswith('_')])
print(inspect.signature(Summary.writer))
"
```
Note `add_variable`/`add_t_step`/`fwrite` presence. Reader probe after first successful write: `[m for m in dir(s) if 'unit' in m.lower()]`.

- [ ] **Step 2: Write the failing test**

`tests/test_summary.py`:
```python
import datetime
from pathlib import Path

from resdash.demo_io import write_summary
from resdata.summary import extract_vectors, round6, thin_minmax


def test_roundtrip_and_units(tmp_path, monkeypatch):
    days = [0.0, 30.0, 61.0, 91.0]
    fopr = [0.0, 9500.0, 9100.0, 8800.0]
    write_summary(
        "DEMO1",
        datetime.datetime(2020, 1, 1),
        days,
        {"FOPR": {"unit": "SM3/DAY", "data": fopr}},
        tmp_path,
    )
    assert (tmp_path / "DEMO1.SMSPEC").exists()
    assert (tmp_path / "DEMO1.UNSMRY").exists()

    out = extract_vectors(str(tmp_path / "DEMO1"), max_points=4000)
    assert out["TIME"] == [round6(d) for d in days]
    assert out["DATE"][0] == "2020-01-01" and out["DATE"][-1] == "2020-04-01"
    assert out["FOPR"]["unit"].upper().startswith("SM3")
    assert [round6(v) for v in out["FOPR"]["data"]] == [round6(v) for v in fopr]


def test_thin_minmax_preserves_peaks():
    vals = [0.0] + [1.0] * 200 + [100.0] + [1.0] * 200 + [0.0]
    idx = thin_minmax(vals, 20)
    assert len(idx) <= 20
    assert vals[idx[0]] == 0.0 and vals[idx[-1]] == 0.0
    assert 100.0 in [vals[i] for i in idx]


def test_extract_decimates_long_series(tmp_path, monkeypatch):
    import random
    random.seed(7)
    n = 5000
    days = [float(i) for i in range(n)]
    data = [random.random() * 100 for _ in range(n)]
    write_summary("DEMO2", datetime.datetime(2020, 1, 1), days,
                  {"FOPR": {"unit": "SM3/DAY", "data": data}}, tmp_path)
    out = extract_vectors(str(tmp_path / "DEMO2"), max_points=100)
    assert len(out["TIME"]) <= 100
    assert len(out["FOPR"]["data"]) == len(out["TIME"])
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python -m pytest tests/test_summary.py -q`
Expected: FAIL (`ModuleNotFoundError: resdata.demo_io`).

- [ ] **Step 4: Implement `resdash/summary.py` and `resdash/demo_io.py`**

`resdash/summary.py`:
```python
"""Read ECLIPSE SMSPEC/UNSMRY into tidy parallel arrays."""
import warnings

warnings.filterwarnings("ignore", category=DeprecationWarning)

from resdata.summary import Summary  # noqa: E402


def round6(v: float) -> float:
    return float(f"{v:.6g}")


def thin_minmax(values, max_points: int) -> list[int]:
    """Indices keeping first/last + per-bucket min/max (order preserved)."""
    n = len(values)
    if n <= max_points:
        return list(range(n))
    keep = {0, n - 1}
    buckets = max(max_points - 2, 1)
    step = n / buckets
    for b in range(buckets):
        lo = int(b * step)
        hi = max(int((b + 1) * step), lo + 1)
        seg = values[lo:hi]
        keep.add(lo + min(range(len(seg)), key=lambda i: seg[i]))
        keep.add(lo + max(range(len(seg)), key=lambda i: seg[i]))
    return sorted(keep)


def extract_vectors(smspec_path: str, max_points: int = 4000) -> dict:
    s = Summary(smspec_path)
    days = list(s.days)
    dates = list(s.dates)
    keep = thin_minmax(days, max_points)
    out: dict = {
        "TIME": [round6(days[i]) for i in keep],
        "DATE": [dates[i].strftime("%Y-%m-%d") for i in keep],
    }
    for key in s.keys():
        vals = s.get_values(key)
        unit = ""
        try:
            unit = s.get_unit(key) or ""
        except Exception:
            pass
        out[key] = {"unit": unit, "data": [round6(float(vals[i])) for i in keep]}
    return out
```

`resdash/demo_io.py`:
```python
"""Write small ECLIPSE summary cases (used by tests and the demo generator)."""
import datetime
import os
from contextlib import contextmanager
from pathlib import Path

from resdata.summary import Summary


@contextmanager
def _chdir(path: Path):
    prev = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(prev)


def write_summary(case: str, start: datetime.datetime, days, vectors, out_dir: Path) -> None:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    with _chdir(out_dir):
        w = Summary.writer(case, start, 1, 1, 1)
        for key, meta in vectors.items():
            w.add_variable(key, unit=meta.get("unit", ""))
        for i, d in enumerate(days):
            t = w.add_t_step(i + 1, float(d))
            for key, meta in vectors.items():
                t[key] = float(meta["data"][i])
        w.fwrite()
```
(If the Step-1 probe shows different method names — e.g. `addVar` — adjust `demo_io.py` only; tests are API-name agnostic.)

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_summary.py -q`
Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add resdash tests && git commit -m "feat: summary round-trip (writer + extractor + thinning)"
```

---

### Task 3: Case discovery

**Files:**
- Create: `resdash/discovery.py`, `tests/test_discovery.py`

**Interfaces:**
- Consumes: nothing (pure pathlib).
- Produces: `resdash.discovery.CaseFiles` dataclass with fields `name: str, realization: str, folder: str, smspec: str, unsmry: str, rft: str | None, prt: str | None, data: str | None`; `discover(runs_folder: str, realization_regex: str | None = None) -> list[CaseFiles]`; `parse_realization(name: str, regex: str | None) -> str`.

- [ ] **Step 1: Write the failing test**

`tests/test_discovery.py`:
```python
from pathlib import Path

from resdash.discovery import discover, parse_realization


def _touch(p: Path):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("x")


def test_discover_finds_pairs_and_attachments(tmp_path):
    _touch(tmp_path / "STOCH_CHESS_BD_28_V2.SMSPEC")
    _touch(tmp_path / "STOCH_CHESS_BD_28_V2.UNSMRY")
    _touch(tmp_path / "STOCH_CHESS_BD_28_V2.PRT")
    _touch(tmp_path / "STOCH_CHESS_BD_28_V2.RFT")
    _touch(tmp_path / "other_case.SMSRY")  # junk extension: ignored
    _touch(tmp_path / "lonely.UNSMRY")     # no SMSPEC pair: skipped
    cases = discover(str(tmp_path))
    assert len(cases) == 1
    c = cases[0]
    assert c.name == "STOCH_CHESS_BD_28_V2"
    assert c.realization == "2"
    assert c.prt.endswith("STOCH_CHESS_BD_28_V2.PRT")
    assert c.rft.endswith("STOCH_CHESS_BD_28_V2.RFT")
    assert c.data is None


def test_discover_recursive_subfolders(tmp_path):
    _touch(tmp_path / "REAL-01" / "CASEA.SMSPEC")
    _touch(tmp_path / "REAL-01" / "CASEA.UNSMRY")
    _touch(tmp_path / "REAL-02" / "CASEB.SMSPEC")
    _touch(tmp_path / "REAL-02" / "CASEB.UNSMRY")
    cases = discover(str(tmp_path))
    assert {c.name for c in cases} == {"CASEA", "CASEB"}
    assert {c.realization for c in cases} == {"1", "2"}


def test_realization_regex_override():
    assert parse_realization("RUN_KR05_BASE", r"KR(\d+)") == "05"
    assert parse_realization("NO_MATCH_HERE", None) == "NO_MATCH_HERE"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_discovery.py -q`
Expected: FAIL (module missing).

- [ ] **Step 3: Implement `resdash/discovery.py`**

```python
"""Find ECLIPSE cases (SMSPEC/UNSMRY pairs) and their sibling files."""
import re
import warnings
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_REALIZATION_PATTERNS = [r"_V(\d+)$", r"REAL[-_]?(\d+)", r"_R(\d+)$"]


@dataclass
class CaseFiles:
    name: str
    realization: str
    folder: str
    smspec: str
    unsmry: str
    rft: str | None = None
    prt: str | None = None
    data: str | None = None


def parse_realization(name: str, regex: str | None) -> str:
    patterns = [regex] if regex else DEFAULT_REALIZATION_PATTERNS
    for pat in patterns:
        if not pat:
            continue
        m = re.search(pat, name, re.IGNORECASE)
        if m:
            return m.group(1)
    return name


ATTACHMENTS = {".PRT": "prt", ".RFT": "rft", ".DATA": "data"}


def discover(runs_folder: str, realization_regex: str | None = None) -> list[CaseFiles]:
    root = Path(runs_folder)
    found: dict[str, dict] = {}
    for p in sorted(root.rglob("*")):
        stem, ext = p.stem, p.suffix.upper()
        entry = found.setdefault(stem, {})
        if ext == ".SMSPEC":
            entry["smspec"] = str(p)
        elif ext == ".UNSMRY":
            entry["unsmry"] = str(p)
        elif ext in ATTACHMENTS:
            entry[ATTACHMENTS[ext]] = str(p)
    cases: list[CaseFiles] = []
    for name, files in found.items():
        if "smspec" not in files or "unsmry" not in files:
            warnings.warn(f"discovery: skipping {name!r} (no SMSPEC/UNSMRY pair)")
            continue
        cases.append(
            CaseFiles(
                name=name,
                realization=parse_realization(name, realization_regex),
                folder=str(Path(files["smspec"]).parent),
                smspec=files["smspec"],
                unsmry=files["unsmry"],
                rft=files.get("rft"),
                prt=files.get("prt"),
                data=files.get("data"),
            )
        )
    return cases
```

- [ ] **Step 4: Run tests → 3 passed. Commit**

```bash
python -m pytest tests/test_discovery.py -q
git add resdash tests && git commit -m "feat: case discovery with realization parsing"
```

---

### Task 4: Bundle assembly + validation

**Files:**
- Create: `resdash/bundle.py`, `tests/test_bundle.py`

**Interfaces:**
- Consumes: `discover`, `extract_vectors` (Tasks 2–3).
- Produces:
  - `build_bundle(runs_folder: str, realization_regex: str | None = None, max_points: int = 4000, log=print) -> dict` — schema-v1 bundle exactly as spec §5 (`schema`, `generated_utc`, `source_folder`, `cases[]`; each case: `name, realization, folder, files{summary,rft,prt,data}, params, vectors, rft, qc`). Missing RFT/PRT/DATA → empty defaults + warning, never raise.
  - `validate_bundle(b: dict) -> list[str]` (empty list = valid)
  - `dump_bundle(b: dict, path: str) -> None` / `load_bundle(path: str) -> dict`
  - In this task `params={}`, `rft=[]`, `qc={}` placeholders wired through; Tasks 6–8 fill them.

- [ ] **Step 1: Write the failing test**

`tests/test_bundle.py`:
```python
import datetime
import json
from pathlib import Path

from resdash.bundle import build_bundle, dump_bundle, load_bundle, validate_bundle
from resdash.demo_io import write_summary


def _make_case(folder: Path, name: str, values):
    days = [0.0, 30.0, 60.0]
    write_summary(name, datetime.datetime(2020, 1, 1), days,
                  {"FOPR": {"unit": "SM3/DAY", "data": values},
                   "FOPT": {"unit": "SM3", "data": [0, values[1]*30, values[1]*60]}},
                  folder)


def test_build_and_validate(tmp_path, capsys):
    _make_case(tmp_path / "REAL-01", "CASE_V1", [0, 1000.0, 900.0])
    _make_case(tmp_path / "REAL-02", "CASE_V2", [0, 1500.0, 1300.0])

    b = build_bundle(str(tmp_path))
    errs = validate_bundle(b)
    assert errs == []
    assert b["schema"] == 1
    assert len(b["cases"]) == 2
    names = {c["name"] for c in b["cases"]}
    assert names == {"CASE_V1", "CASE_V2"}
    c1 = b["cases"][0]
    assert c1["files"] == {"summary": True, "rft": False, "prt": False, "data": False}
    assert "FOPR" in c1["vectors"] and c1["vectors"]["FOPR"]["unit"] == "SM3/DAY"
    assert c1["rft"] == [] and c1["qc"] == {} and c1["params"] == {}
    assert b["source_folder"] == str(tmp_path)

    out = tmp_path / "bundle.json"
    dump_bundle(b, str(out))
    assert load_bundle(str(out)) == json.loads(json.dumps(b))


def test_validate_catches_errors():
    assert validate_bundle({"schema": 2}) != []          # wrong schema
    assert validate_bundle({"schema": 1, "cases": []}) == []
    bad = {"schema": 1, "cases": [{"name": "A"}, {"name": "A"}]}
    assert any("unique" in e for e in validate_bundle(bad))
```

- [ ] **Step 2: Run → FAIL. Step 3: Implement `resdash/bundle.py`**

```python
"""Assemble, validate, persist the dashboard data bundle (schema v1)."""
import datetime as dt
import json
from pathlib import Path

from resdash import __version__
from resdash.discovery import discover
from resdash.summary import extract_vectors

SCHEMA_VERSION = 1


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_bundle(runs_folder: str, realization_regex: str | None = None,
                 max_points: int = 4000, log=print) -> dict:
    cases_out = []
    for c in discover(runs_folder, realization_regex):
        log(f"extracting {c.name} ...")
        entry = {
            "name": c.name,
            "realization": c.realization,
            "folder": c.folder,
            "files": {"summary": True, "rft": bool(c.rft), "prt": bool(c.prt), "data": bool(c.data)},
            "params": {},
            "vectors": extract_vectors(c.smspec, max_points=max_points),
            "rft": [],
            "qc": {},
        }
        cases_out.append(entry)
    return {
        "schema": SCHEMA_VERSION,
        "generated_utc": _now(),
        "source_folder": str(runs_folder),
        "tool_version": __version__,
        "cases": cases_out,
    }


def validate_bundle(b: dict) -> list[str]:
    errs = []
    if b.get("schema") != SCHEMA_VERSION:
        errs.append(f"unsupported schema {b.get('schema')!r}, expected {SCHEMA_VERSION}")
        return errs
    names = [c.get("name") for c in b.get("cases", [])]
    if len(names) != len(set(names)):
        errs.append("case names must be unique")
    for c in b.get("cases", []):
        for req in ("name", "realization", "folder", "files", "vectors"):
            if req not in c:
                errs.append(f"case missing {req!r}: {c.get('name')}")
    return errs


def dump_bundle(b: dict, path: str) -> None:
    Path(path).write_text(json.dumps(b, separators=(",", ":")), encoding="utf-8")


def load_bundle(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))
```

- [ ] **Step 4: Run tests → 2 passed. Commit**

```bash
python -m pytest tests/test_bundle.py -q
git add resdash tests && git commit -m "feat: schema-v1 bundle assembly and validation"
```

---

### Task 5: Static renderer v1 (template + Overview + Time Series) + CLI — end-to-end slice

**Files:**
- Create: `resdash/assets/template.html`, `resdash/assets/dashboard.css`, `resdash/assets/dashboard.js`, `resdash/render.py`, `build_dashboard.py`
- Test: `tests/test_render.py`

**Interfaces:**
- Consumes: bundle dict (Task 4).
- Produces: `resdash.render.render_html(bundle: dict, out_path: str) -> str`; CLI `python build_dashboard.py <runs_folder> [-o out.html] [--max-points N] [--realization-regex RE] [--bundle-json PATH]` (either `<runs_folder>` or `--bundle-json`).

- [ ] **Step 1: Write the failing test**

`tests/test_render.py`:
```python
import datetime
import json
import re

from resdash.bundle import build_bundle
from resdash.demo_io import write_summary
from resdash.render import render_html


def _demo_bundle(tmp_path):
    days = [float(d) for d in range(0, 366, 30)]
    fopr = [0, 9000, 8800, 8600, 8400, 8200, 8000, 7800, 7600, 7400, 7200, 7000, 6800]
    for i, mult in enumerate([1.0, 1.2]):
        write_summary(f"CASE_V{i+1}", datetime.datetime(2020, 1, 1), days,
                      {"FOPR": {"unit": "SM3/DAY", "data": [v * mult for v in fopr]}},
                      tmp_path / f"REAL-0{i+1}")
    return build_bundle(str(tmp_path))


def test_render_selfcontained(tmp_path):
    b = _demo_bundle(tmp_path)
    out = tmp_path / "dash.html"
    render_html(b, str(out))
    html = out.read_text(encoding="utf-8")
    assert "Plotly.newPlot" in html
    assert "bundle-data" in html
    json.loads(re.search(r'<script id="bundle-data" type="application/json">(.*?)</script>',
                         html, re.S).group(1))
    assert "generated_utc" in html
    assert not re.search(r'(src|href)\s*=\s*["\']https?://', html)
    assert out.stat().st_size > 1_000_000  # plotly embedded
```

- [ ] **Step 2: Run → FAIL. Step 3: Implement assets + renderer + CLI**

`resdash/assets/template.html`:
```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>ECLIPSE Ensemble Dashboard</title>
<style>/*__APP_CSS__*/</style>
</head>
<body>
<header>
  <h1>ECLIPSE Ensemble Dashboard</h1>
  <div id="meta"></div>
  <nav id="tabs">
    <button data-tab="overview" class="active">Overview</button>
    <button data-tab="timeseries">Time Series</button>
    <button data-tab="parameters">Parameters</button>
    <button data-tab="rft">RFT</button>
    <button data-tab="qc">QC</button>
  </nav>
</header>
<main>
  <section id="overview" class="tab active"></section>
  <section id="timeseries" class="tab"></section>
  <section id="parameters" class="tab"></section>
  <section id="rft" class="tab"></section>
  <section id="qc" class="tab"></section>
</main>
<script>/*__PLOTLY__*/</script>
<script id="bundle-data" type="application/json">/*__BUNDLE__*/</script>
<script>/*__APP_JS__*/</script>
</body>
</html>
```

`resdash/assets/dashboard.css` (compact dark engineering theme):
```css
:root{--bg:#101418;--panel:#1a2027;--ink:#e8eaed;--muted:#9aa4ad;--accent:#4fc3f7;--line:#2a323c}
*{box-sizing:border-box}
body{margin:0;font:14px/1.45 "Segoe UI",Arial,sans-serif;background:var(--bg);color:var(--ink)}
header{padding:14px 20px;border-bottom:1px solid var(--line)}
h1{font-size:18px;margin:0 0 4px}
#meta{color:var(--muted);font-size:12px}
#tabs button{background:none;border:1px solid var(--line);color:var(--muted);padding:6px 14px;margin-right:6px;cursor:pointer;border-radius:4px}
#tabs button.active{color:var(--accent);border-color:var(--accent)}
main{padding:16px 20px}
.tab{display:none}.tab.active{display:block}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:6px;padding:12px;margin-bottom:14px}
table{border-collapse:collapse;width:100%;font-size:13px}
th,td{border:1px solid var(--line);padding:4px 8px;text-align:right;white-space:nowrap}
th{color:var(--muted);cursor:pointer}td:first-child,th:first-child{text-align:left}
select,input[type=text],input[type=checkbox]{background:var(--bg);color:var(--ink);border:1px solid var(--line);border-radius:4px;padding:4px}
.controls{display:flex;flex-wrap:wrap;gap:14px;align-items:center;margin-bottom:10px}
.controls label{color:var(--muted);font-size:12px;display:flex;gap:4px;align-items:center}
.plot{width:100%;min-height:420px}
.muted{color:var(--muted)}
button.action{background:var(--accent);border:none;color:#08222e;font-weight:600;padding:6px 12px;border-radius:4px;cursor:pointer}
```

`resdash/assets/dashboard.js` (v1 — framework + Overview + Time Series; Parameters/RFT/QC tabs added in Task 9):
```javascript
/* global Plotly */
function $(id) { return document.getElementById(id); }
function esc(s) { return String(s).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c])); }
function fmt(v, d = 3) { return v == null || isNaN(v) ? '–' : Number(v).toPrecision(d); }

const BUNDLE = JSON.parse($('bundle-data').textContent);
const CASES = BUNDLE.cases;

/* ---------- shared helpers ---------- */
const P10_HIGH = a => quantile(a, 0.9);   // P10 = optimistic (high)
const P50 = a => quantile(a, 0.5);
const P90_LOW = a => quantile(a, 0.1);
function quantile(sortedCopy, q) {
  if (!sortedCopy.length) return null;
  const a = [...sortedCopy].sort((x, y) => x - y), pos = (a.length - 1) * q,
        lo = Math.floor(pos), hi = Math.ceil(pos);
  return a[lo] + (a[hi] - a[lo]) * (pos - lo);
}
function lastVal(c, key) {
  const v = c.vectors[key]; if (!v) return null;
  for (let i = v.data.length - 1; i >= 0; i--) if (v.data[i] != null && !isNaN(v.data[i])) return v.data[i];
  return null;
}
function vectorGroups() {  // FIELD / W:type / other
  const g = { FIELD: [], WELL: {}, OTHER: [] };
  for (const key of Object.keys(CASES[0].vectors)) {
    if (key === 'TIME' || key === 'DATE') continue;
    if (/^F/.test(key)) g.FIELD.push(key);
    else if (/^W[A-Z]+:/.test(key)) { const t = key.split(':')[0]; (g.WELL[t] = g.WELL[t] || []).push(key); }
    else g.OTHER.push(key);
  }
  for (const k of Object.keys(g.WELL)) g.FIELD = g.FIELD.concat(g.WELL[k]);
  g.FIELD = [...new Set(g.FIELD)];
  return g;
}
const LAYOUT = {
  paper_bgcolor: '#1a2027', plot_bgcolor: '#1a2027',
  font: { color: '#e8eaed', size: 12 },
  margin: { l: 60, r: 20, t: 40, b: 40 },
  xaxis: { gridcolor: '#2a323c' }, yaxis: { gridcolor: '#2a323c' },
  legend: { orientation: 'h', y: -0.2 },
};

/* ---------- tabs ---------- */
document.querySelectorAll('#tabs button').forEach(btn => btn.onclick = () => {
  document.querySelectorAll('#tabs button').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  btn.classList.add('active'); $(btn.dataset.tab).classList.add('active');
});

/* ---------- Overview ---------- */
function renderOverview() {
  const rows = CASES.map(c => ({
    name: c.name, realization: c.realization,
    FOPT: lastVal(c, 'FOPT'), FGPT: lastVal(c, 'FGPT'), FWPT: lastVal(c, 'FWPT'),
    FGIT: lastVal(c, 'FGIT'), FWIT: lastVal(c, 'FWIT'),
    FPR: lastVal(c, 'FPR'), mb: c.qc && c.qc.mb_error_max, nts: c.qc && c.qc.timesteps,
  }));
  $('overview').innerHTML =
    '<div class="panel"><table id="ov-table"><thead><tr>' +
    Object.keys(rows[0]).map(h => `<th>${esc(h)}</th>`).join('') +
    '</tr></thead><tbody>' +
    rows.map(r => '<tr>' + Object.keys(r).map(h =>
      h === 'name' ? `<td>${esc(r[h])}</td>` :
      h === 'realization' ? `<td>${esc(r[h])}</td>` :
      `<td>${r[h] == null ? '–' : fmt(r[h], 4)}</td>`).join('') + '</tr>').join('') +
    '</tbody></table></div>' +
    '<div class="panel"><div class="controls"><label>End-point ' +
    '<select id="ov-endpoint">' + ['FOPT', 'FGPT', 'FWPT', 'FWIT', 'FGIT'].map(k => `<option>${k}</option>`).join('') +
    '</select></label><span class="muted" id="ov-stats"></span></div><div id="ov-rank" class="plot"></div></div>';
  const draw = () => {
    const key = $('ov-endpoint').value;
    const pts = CASES.map(c => ({ name: c.name, v: lastVal(c, key) })).filter(p => p.v != null)
                     .sort((a, b) => a.v - b.v);
    const vals = pts.map(p => p.v);
    $('ov-stats').textContent = vals.length > 1 ?
      `P90 ${fmt(P90_LOW(vals))} · P50 ${fmt(P50(vals))} · P10 ${fmt(P10_HIGH(vals))}` : '';
    Plotly.newPlot('ov-rank', [{
      type: 'bar', orientation: 'h',
      x: pts.map(p => p.v), y: pts.map(p => p.name),
      marker: { color: '#4fc3f7' }, text: pts.map(p => fmt(p.v, 4)), textposition: 'auto',
    }], { ...LAYOUT, yaxis: { ...LAYOUT.yaxis, autorange: 'reversed' },
         xaxis: { ...LAYOUT.xaxis, title: key } }, { displayModeBar: false });
  };
  $('ov-endpoint').onchange = draw; draw();
}

/* ---------- Time Series ---------- */
function renderTimeSeries() {
  const groups = vectorGroups();
  $('timeseries').innerHTML =
    '<div class="panel"><div class="controls">' +
    '<label>Vector <select id="ts-vector"></select></label>' +
    '<label><input type="checkbox" id="ts-log"> log Y</label>' +
    '<label><input type="checkbox" id="ts-date"> dates on X</label>' +
    '<button class="action" id="ts-csv">Export CSV</button></div>' +
    '<div class="controls" id="ts-cases"></div>' +
    '<div id="ts-plot" class="plot"></div></div>';
  const sel = $('ts-vector');
  const opt = k => `<option value="${esc(k)}">${esc(k)}</option>`;
  sel.innerHTML = groups.FIELD.filter(k => /^F/.test(k)).map(opt).join('') +
    Object.keys(groups.WELL).sort().flatMap(t => groups.WELL[t]).map(opt).join('') +
    groups.OTHER.map(opt).join('');
  $('ts-cases').innerHTML = '<label class="muted">Cases</label>' + CASES.map((c, i) =>
    `<label><input type="checkbox" class="ts-case" value="${i}" ${i < 2 ? 'checked' : ''}> ${esc(c.name)}</label>`).join('');
  const draw = () => {
    const key = sel.value, useDate = $('ts-date').checked;
    const traces = [...document.querySelectorAll('.ts-case:checked')].map(cb => CASES[+cb.value])
      .filter(c => c.vectors[key]).map(c => ({
        name: c.name,
        x: useDate ? c.vectors.DATE : c.vectors.TIME,
        y: c.vectors[key].data, mode: 'lines',
      }));
    Plotly.newPlot('ts-plot', traces, {
      ...LAYOUT, yaxis: { ...LAYOUT.yaxis, type: $('ts-log').checked ? 'log' : 'linear' },
      xaxis: { ...LAYOUT.xaxis, title: useDate ? 'date' : 'days' },
    }, { responsive: true });
  };
  ['ts-vector', 'ts-log', 'ts-date'].forEach(id => { $(id).onchange = draw; });
  document.querySelectorAll('.ts-case').forEach(cb => cb.onchange = draw);
  $('ts-csv').onclick = () => {
    const key = sel.value, cols = ['CASE', 'TIME', 'DATE', key];
    const lines = [cols.join(',')];
    [...document.querySelectorAll('.ts-case:checked')].map(cb => CASES[+cb.value])
      .filter(c => c.vectors[key]).forEach(c =>
        c.vectors.TIME.forEach((t, i) => lines.push([c.name, t, c.vectors.DATE[i], c.vectors[key].data[i]].join(','))));
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([lines.join('\n')], { type: 'text/csv' }));
    a.download = key.replace(/[^A-Za-z0-9_-]/g, '_') + '.csv'; a.click();
  };
  draw();
}

/* ---------- boot ---------- */
$('meta').textContent =
  `${CASES.length} cases · generated ${BUNDLE.generated_utc} · source ${BUNDLE.source_folder}`;
renderOverview();
renderTimeSeries();
window.DASH = { renderParameters: () => {}, renderRFT: () => {}, renderQC: () => {} };
```

`resdash/render.py`:
```python
"""Assemble the self-contained dashboard.html."""
import json
from pathlib import Path

import plotly

ASSETS = Path(__file__).parent / "assets"
PLOTLY_JS = Path(plotly.__file__).parent / "package_data" / "plotly.min.js"


def render_html(bundle: dict, out_path: str) -> str:
    html = (ASSETS / "template.html").read_text(encoding="utf-8")
    payload = json.dumps(bundle, separators=(",", ":")).replace("</", "<\\/")
    html = (html
            .replace("/*__PLOTLY__*/", PLOTLY_JS.read_text(encoding="utf-8"))
            .replace("/*__APP_CSS__*/", (ASSETS / "dashboard.css").read_text(encoding="utf-8"))
            .replace("/*__BUNDLE__*/", payload)
            .replace("/*__APP_JS__*/", (ASSETS / "dashboard.js").read_text(encoding="utf-8")))
    Path(out_path).write_text(html, encoding="utf-8")
    return out_path
```

`build_dashboard.py`:
```python
#!/usr/bin/env python3
"""Build a self-contained dashboard.html from a folder of ECLIPSE runs."""
import argparse
import sys
import warnings

warnings.filterwarnings("ignore", category=DeprecationWarning)

from resdash.bundle import build_bundle, load_bundle, validate_bundle  # noqa: E402
from resdash.render import render_html  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("runs_folder", nargs="?", help="folder containing ECLIPSE runs")
    ap.add_argument("-o", "--output", default="dashboard.html")
    ap.add_argument("--bundle-json", help="load a previously built bundle instead of extracting")
    ap.add_argument("--max-points", type=int, default=4000)
    ap.add_argument("--realization-regex", default=None)
    args = ap.parse_args(argv)

    if args.bundle_json:
        bundle = load_bundle(args.bundle_json)
    elif args.runs_folder:
        bundle = build_bundle(args.runs_folder, realization_regex=args.realization_regex,
                              max_points=args.max_points)
    else:
        ap.error("provide RUNS_FOLDER or --bundle-json")

    errs = validate_bundle(bundle)
    if errs:
        for e in errs:
            print(f"bundle error: {e}", file=sys.stderr)
        return 2
    render_html(bundle, args.output)
    print(f"wrote {args.output} ({len(bundle['cases'])} cases)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run tests → pass. Step 5: Manual end-to-end smoke**

```bash
python build_dashboard.py demo 2>/dev/null || true   # demo/ doesn't exist yet – expected error path
python -m pytest tests -q
```
Expected: full suite green.

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "feat: static renderer v1 (Overview + Time Series) and CLI"
```

---

### Task 6: Deck parameter extraction (.DATA + GRDECL stats)

**Files:**
- Create: `resdash/deck.py`, `tests/test_deck.py`

**Interfaces:**
- Consumes: `CaseFiles` (Task 3).
- Produces: `resdash.deck.extract_deck_params(case: CaseFiles) -> dict` — flat `{str: float|str}`. Keys: `MULTIPLY:<PROP>` (last value per property), `WCONPROD:<WELL>:<MODE>`, `WCONINJE:<WELL>:<MODE>`, `START` (ISO date str), `EQUIL_DATUM`/`EQUIL_PRESSURE`, `SCHEDULE_END` (last DATES found, ISO str), and for each sibling GRDECL property file `<PROP>_MEAN`, `<PROP>_P10`, `<PROP>_P50`, `<PROP>_P90` (ACTNUM not weighted in v1 — plain stats). Unknown/unparsable → key omitted.

- [ ] **Step 1: Write the failing test**

`tests/test_deck.py`:
```python
from pathlib import Path

from resdash.deck import extract_deck_params
from resdash.discovery import CaseFiles


def _case(tmp_path: Path) -> CaseFiles:
    d = tmp_path
    (d / "CASE_V1.DATA").write_text(
        "-- demo deck\n"
        "RUNSPEC\n\nDIMENS\n 10 10 3 /\n\n"
        "SCHEDULE\n"
        "WCONPROD\n 'P1' 'ORAT' 2500 4* 30 /\n /\n"
        "WCONINJE\n 'I1' 'WATER' 'OPEN' 'RATE' 4000 1* 500 /\n /\n"
        "DATES\n 1 'JAN' 2025 /\n /\n"
        "MULTIPLY\n 'PORO' 1.15 /\n 'PERMX' 1.30 /\n /\n", encoding="utf-8")
    (d / "CASE_V1_PROP_PORO.GRDECL").write_text(
        "PORO\n 0.20 0.22 0.24 0.26 0.28 0.30 0.32 0.34 /\n", encoding="utf-8")
    (d / "CASE_V1_PROP_PERMX.GRDECL").write_text(
        "PERMX\n 10 50 100 200 300 500 /\n", encoding="utf-8")
    return CaseFiles(name="CASE_V1", realization="1", folder=str(d),
                     smspec=str(d / "CASE_V1.SMSPEC"), unsmry=str(d / "CASE_V1.UNSMRY"),
                     data=str(d / "CASE_V1.DATA"))


def test_deck_params(tmp_path):
    p = extract_deck_params(_case(tmp_path))
    assert p["MULTIPLY:PORO"] == 1.15
    assert p["MULTIPLY:PERMX"] == 1.30
    assert p["WCONPROD:P1:ORAT"] == 2500.0
    assert p["WCONINJE:I1:RATE"] == 4000.0
    assert p["PORO_MEAN"] > 0.25 and 0 < p["PORO_P50"] < 1
    assert p["PERMX_P50"] == 150.0  # (100+200)/2


def test_no_data_file_gives_grdecl_only(tmp_path):
    (tmp_path / "ONLY_V2_PROP_NTG.GRDECL").write_text("NTG\n 1 1 0 1 /\n", encoding="utf-8")
    c = CaseFiles(name="ONLY_V2", realization="2", folder=str(tmp_path),
                  smspec="x", unsmry="x")
    p = extract_deck_params(c)
    assert p["NTG_MEAN"] == 0.75 and "MULTIPLY:PORO" not in p
```

- [ ] **Step 2: Run → FAIL. Step 3: Implement `resdash/deck.py`**

```python
"""Extract per-case input parameters from .DATA decks and GRDECL property stats."""
import re
from pathlib import Path

import numpy as np

from resdash.discovery import CaseFiles

NUM = r"([-+]?\d+\.?\d*(?:[Ee][-+]?\d+)?)"

WCONPROD_RE = re.compile(r"^'([^']+)'\s+'([A-Z]{4})'\s+" + NUM, re.I)
WCONINJE_RE = re.compile(r"^'([^']+)'\s+'[A-Z]+'\s+'[A-Z]+'\s+'([A-Z]{4})'\s+" + NUM, re.I)
MULTIPLY_RE = re.compile(r"^'([A-Z0-9_]+)'\s+" + NUM, re.I)
DATES_RE = re.compile(r"^(\d{1,2})\s+'([A-Z]{3})'\s+(\d{4})", re.I)
MONTHS = {m: i + 1 for i, m in enumerate(
    ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"])}


def _strip_comment(line: str) -> str:
    return line.split("--", 1)[0].rstrip()


def _parse_deck_text(text: str, params: dict) -> None:
    keyword = None
    for raw in text.splitlines():
        line = _strip_comment(raw).strip()
        if not line:
            continue
        first = line.split()[0].upper()
        if not line.startswith("'") and first.isalpha() and keyword not in ("MULTIPLY",):
            keyword = first if first.isalpha() else keyword
        if keyword == "MULTIPLY":
            m = MULTIPLY_RE.match(line)
            if m:
                params[f"MULTIPLY:{m.group(1).upper()}"] = float(m.group(2))
            if line.endswith("/"):
                keyword = None
        elif keyword == "WCONPROD":
            m = WCONPROD_RE.match(line)
            if m:
                params[f"WCONPROD:{m.group(1)}:{m.group(2).upper()}"] = float(m.group(3))
        elif keyword == "WCONINJE":
            m = WCONINJE_RE.match(line)
            if m:
                params[f"WCONINJE:{m.group(1)}:{m.group(2).upper()}"] = float(m.group(3))
        elif keyword == "DATES":
            m = DATES_RE.match(line)
            if m:
                params["SCHEDULE_END"] = f"{int(m.group(3)):04d}-{MONTHS[m.group(2).upper()]:02d}-{int(m.group(1)):02d}"
        elif keyword == "START":
            m = DATES_RE.match(line)
            if m:
                params["START"] = f"{int(m.group(3)):04d}-{MONTHS[m.group(2).upper()]:02d}-{int(m.group(1)):02d}"


def _grdecl_stats(path: Path, params: dict) -> None:
    tokens: list[str] = []
    prop = None
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = _strip_comment(raw).strip()
        if not line:
            continue
        if prop is None and re.fullmatch(r"[A-Z][A-Z0-9_]*", line.split()[0]):
            prop = line.split()[0].upper()
            line = line[len(line.split()[0]):]
        tokens.extend(line.split())
    if prop is None or not tokens:
        return
    vals = np.array([float(t) for t in tokens if re.fullmatch(NUM, t)], dtype=float)
    if not vals.size:
        return
    params[f"{prop}_MEAN"] = float(np.mean(vals))
    for q, tag in [(0.1, "P10"), (0.5, "P50"), (0.9, "P90")]:
        params[f"{prop}_{tag}"] = float(np.percentile(vals, q * 100))


def extract_deck_params(case: CaseFiles) -> dict:
    params: dict = {}
    if case.data and Path(case.data).exists():
        _parse_deck_text(Path(case.data).read_text(encoding="utf-8", errors="ignore"), params)
    folder = Path(case.folder)
    grdecls = sorted(set(folder.glob(f"{case.name}_PROP_*.GRDECL"))) + [folder / f"{case.name}.GRDECL"]
    for g in grdecls:
        if g.exists():
            _grdecl_stats(g, params)
    return params
```

- [ ] **Step 4: Run tests → 2 passed. Step 5: Wire into `build_bundle`**

In `resdash/bundle.py` replace `"params": {},` with:
```python
from resdash.deck import extract_deck_params  # at module top
...
            "params": (extract_deck_params(c) if c.data or Path(c.folder).glob(f"{c.name}*GRDECL") else {}),
```
Simplify to always call: `"params": extract_deck_params(c),` (it returns `{}` when nothing found).

Run: `python -m pytest tests -q` → all green. Commit:
```bash
git add -A && git commit -m "feat: deck parameter + GRDECL statistics extraction"
```

---

### Task 7: PRT QC parser (streaming)

**Files:**
- Create: `resdash/prt.py`, `tests/test_prt.py`

**Interfaces:**
- Consumes: `CaseFiles.prt` path (may be None).
- Produces: `resdash.prt.extract_prt(prt_path: str | None) -> dict` → `{"mb_error_max": float|None, "mb_error_last": float|None, "timesteps": int|None, "cpu_hours": float|None, "fip_regions": {region_str: {"oil_sm3": float, "gas_sm3": float, "water_sm3": float}}|{}}`. Missing/unmatched → `None` values, never raise. Streamed — O(1) memory.

- [ ] **Step 1: Write the failing test with a realistic PRT fixture**

`tests/test_prt.py`:
```python
from resdash.prt import extract_prt

FIXTURE = """
 ECHO OF THE SCHEDULE SECTION
 NEW TIME STEP              1 SIZE =   30.0 DAYS
 MATERIAL BALANCE ERROR  AT 2025-02-01:     0.2100E-03 PERCENT
 NEW TIME STEP              2 SIZE =   28.0 DAYS
 MATERIAL BALANCE ERROR  AT 2025-03-01:     0.5400E-02 PERCENT
 NEW TIME STEP              3 SIZE =   31.0 DAYS
 MATERIAL BALANCE ERROR  AT 2025-04-01:     0.1200E-03 PERCENT
 ==========================================
                          :FIELD TOTAL:
   CURRENTLY IN PLACE     :  OIL  SM3      12345670.   GAS  SM3        5432101.
                          :  WATER SM3     76543210.
 FLUID VOLUMES IN PLACE  (SURFACE)  FOR REGION     1
   OIL   SM3      4000000.   GAS  SM3       1000000.   WATER SM3      20000000.
 FLUID VOLUMES IN PLACE  (SURFACE)  FOR REGION     2
   OIL   SM3       8345670.   GAS  SM3       4432101.   WATER SM3      56543210.
 ==========================================
 TOTAL CPU TIME :   0.4321E+05 SECONDS
"""


def test_prt_metrics(tmp_path):
    p = tmp_path / "CASE.PRT"
    p.write_text(FIXTURE, encoding="utf-8")
    qc = extract_prt(str(p))
    assert qc["mb_error_max"] == 0.0054          # 0.54e-2
    assert qc["mb_error_last"] == 0.00012        # 0.12e-3
    assert qc["timesteps"] == 3
    assert abs(qc["cpu_hours"] - 12.0) < 0.01    # 43210 s / 3600
    assert qc["fip_regions"]["1"]["oil_sm3"] == 4_000_000.0
    assert qc["fip_regions"]["2"]["gas_sm3"] == 4_432_101.0


def test_prt_missing_and_unparsable(tmp_path):
    assert extract_prt(None) == {"mb_error_max": None, "mb_error_last": None,
                                 "timesteps": None, "cpu_hours": None, "fip_regions": {}}
    junk = tmp_path / "J.PRT"; junk.write_text("no keywords here\n", encoding="utf-8")
    qc = extract_prt(str(junk))
    assert qc["mb_error_max"] is None and qc["fip_regions"] == {}
```

- [ ] **Step 2: Run → FAIL. Step 3: Implement `resdash/prt.py`**

```python
"""Stream-parse ECLIPSE .PRT for QC metrics. Defensive: every metric optional."""
import re

MB_RE = re.compile(r"MATERIAL BALANCE\s+ERROR\D*?([-+]?\d*\.\d+(?:[Ee][-+]?\d+)?)", re.I)
TS_RE = re.compile(r"^\s*NEW TIME STEP\b", re.I | re.M)
CPU_RE = re.compile(
    r"TOTAL CPU TIME\s*:?\s*([-+]?\d+\.?\d*(?:[Ee][-+]?\d+)?)\s*(SECONDS?|MINUTES?|HOURS?)?", re.I)
FIP_RE = re.compile(r"FLUID VOLUMES IN PLACE\s+\(SURFACE\)\s+FOR REGION\s+(\d+)", re.I)
VOL_RE = re.compile(r"(OIL|GAS|WATER)\s+SM3\s+([-+]?\d+\.?\d*(?:[Ee][-+]?\d+)?", re.I)


def extract_prt(prt_path: str | None) -> dict:
    out = {"mb_error_max": None, "mb_error_last": None, "timesteps": None,
           "cpu_hours": None, "fip_regions": {}}
    if not prt_path:
        return out
    try:
        fh = open(prt_path, "r", encoding="utf-8", errors="ignore")
    except OSError:
        return out
    with fh:
        current_region = None
        for line in fh:
            m = MB_RE.search(line)
            if m:
                v = float(m.group(1))
                out["mb_error_max"] = v if out["mb_error_max"] is None else max(out["mb_error_max"], v)
                out["mb_error_last"] = v
            if TS_RE.match(line):
                out["timesteps"] = (out["timesteps"] or 0) + 1
            m = CPU_RE.search(line)
            if m and out["cpu_hours"] is None:
                v = float(m.group(1))
                unit = (m.group(2) or "SECONDS").upper()
                mult = 1.0 if unit.startswith("H") else (1 / 60 if unit.startswith("M") else 1 / 3600)
                out["cpu_hours"] = v * mult
            m = FIP_RE.search(line)
            if m:
                current_region = m.group(1)
                out["fip_regions"].setdefault(current_region, {})
                continue
            if current_region:
                for vm in VOL_RE.finditer(line):
                    out["fip_regions"][current_region][f"{vm.group(1).lower()}_sm3"] = float(vm.group(2))
                if "TOTAL" in line.upper() and ":" in line:
                    current_region = None
    return out
```

- [ ] **Step 4: Run tests → 2 passed. Step 5: Wire into bundle**

In `bundle.py`: `from resdash.prt import extract_prt` and replace `"qc": {},` with:
```python
            "qc": extract_prt(c.prt),
```
Run full suite → green. Commit:
```bash
git add -A && git commit -m "feat: streaming PRT QC parser (MB error, timesteps, CPU, FIP)"
```

---

### Task 8: RFT extraction (+ fixture strategy)

**Files:**
- Create: `resdash/rft.py`, `resdash/rft_fixture.py`, `tests/test_rft.py`

**Interfaces:**
- Produces: `resdash.rft.extract_rft(rft_path: str | None, max_surveys: int = 50) -> list[dict]` → `[{"well": str, "date": "YYYY-MM-DD", "depth": [float], "pressure": [float]}]` (empty list if path None/unreadable; surveys capped to the latest `max_surveys` per well).
- `resdash.rft_fixture.write_rft(path, well, days, depths, pressures)` — minimal hand-rolled ECLIPSE RFT binary (Fortran unformatted records) **only if needed** for the demo (see Step 1 decision).

- [ ] **Step 1: Probe whether a test RFT can come from resdata itself**

Check for any write support / bundled test data:
```bash
python -W ignore -c "
from resdata.rft import ResdataRFTFile, ResdataRFT
print([m for m in dir(ResdataRFT) if not m.startswith('_')][:40])
print([m for m in dir(ResdataRFTFile) if not m.startswith('_')])
"
```
**Decision rule:** if no writer exists (expected), write `resdash/rft_fixture.py` implementing the classic layout read by resdata's C core (keyword records: `TIME` (int, days), `WELLETC` (100 × char8, well name at index 4), `CONIPOS` (int array of i,j,k triplets), then float arrays `PRESSURE`, `DEPTH`, `SWAT`, `SGAS` — layout reference: https://github.com/equinor/resdata/blob/master/lib/resdata/rft/rd_rft.c). **Timebox: 60 minutes.** If `ResdataRFTFile` still cannot read the fixture, ship the reader anyway with a unit test that monkeypatches `resdash.rft.ResdataRFTFile` with a stub (test below), and set demo RFT = off (`make_demo.py` writes no `.RFT`) — the dashboard RFT tab then demonstrates graceful degradation. Do not spend longer.

- [ ] **Step 2: Write the failing test**

`tests/test_rft.py`:
```python
import datetime
from pathlib import Path

from resdash import rft as rftmod
from resdata.rft import ResdataRFTFile


class _Cell:
    def __init__(self, depth, pressure):
        self._d, self._p = depth, pressure
    def get_depth(self): return self._d
    def get_pressure(self): return self._p


class _RFT:
    def __init__(self, well, date, cells):
        self._w, self._dt, self._c = well, date, cells
    def get_well_name(self): return self._w
    def get_date(self): return self._dt
    def __iter__(self): return iter(self._c)


class _File:
    def __init__(self, surveys): self._s = surveys
    def __len__(self): return len(self._s)
    def __getitem__(self, i): return self._s[i]


def test_extract_rft_via_reader(monkeypatch):
    surveys = _File([
        _RFT("P1", datetime.datetime(2021, 6, 1),
             [_Cell(1000.0, 250.0), _Cell(1010.0, 252.0)]),
        _RFT("P1", datetime.datetime(2022, 6, 1),
             [_Cell(1000.0, 240.0), _Cell(1010.0, 241.0)]),
        _RFT("P2", datetime.datetime(2022, 6, 1),
             [_Cell(2000.0, 300.0)]),
    ])
    monkeypatch.setattr(rftmod, "ResdataRFTFile", lambda p: surveys)
    out = rftmod.extract_rft("whatever.RFT", max_surveys=1)
    assert {"well": "P2", "date": "2022-06-01", "depth": [2000.0], "pressure": [300.0]} in out
    p1 = [s for s in out if s["well"] == "P1"]
    assert len(p1) == 1 and p1[0]["date"] == "2022-06-01"   # capped to latest
    assert p1[0]["depth"] == [1000.0, 1010.0]


def test_extract_rft_none():
    assert rftmod.extract_rft(None) == []


def test_real_binary_fixture_if_available(tmp_path):
    """Skipped automatically unless rft_fixture produced a readable file (Step 1)."""
    from resdata import rft_fixture
    p = tmp_path / "CASE.RFT"
    try:
        rft_fixture.write_rft(str(p), "P1", 500, [1000.0, 1010.0], [250.0, 252.0])
        ResdataRFTFile(str(p))
    except Exception:
        import pytest
        pytest.skip("hand-rolled RFT fixture not available/readable — demo runs without RFT")
    out = rftmod.extract_rft(str(p))
    assert out and out[0]["well"] == "P1"
```

- [ ] **Step 3: Implement `resdash/rft.py`**

```python
"""Read ECLIPSE .RFT surveys via resdata into plain arrays."""
from resdata.rft import ResdataRFTFile
from resdata.summary import round6


def extract_rft(rft_path: str | None, max_surveys: int = 50) -> list[dict]:
    if not rft_path:
        return []
    try:
        f = ResdataRFTFile(rft_path)
    except Exception:
        return []
    per_well: dict[str, list[dict]] = {}
    for i in range(len(f)):
        r = f[i]
        try:
            well = r.get_well_name()
            date = r.get_date().strftime("%Y-%m-%d")
            depths, pressures = [], []
            for cell in r:
                d, p = cell.get_depth(), cell.get_pressure()
                if d is not None and p is not None:
                    depths.append(round6(float(d)))
                    pressures.append(round6(float(p)))
            if depths:
                per_well.setdefault(well, []).append({"well": well, "date": date,
                                                      "depth": depths, "pressure": pressures})
        except Exception:
            continue
    out: list[dict] = []
    for well, surveys in per_well.items():
        out.extend(surveys[-max_surveys:])
    return out
```

Implement `resdash/rft_fixture.py` per Step 1 decision rule (or a stub raising `NotImplementedError` if demo RFT is off — the test skips then).

- [ ] **Step 4: Run tests → 3 passed (1 possibly skipped). Wire into bundle**

`bundle.py`: `from resdash.rft import extract_rft`; replace `"rft": [],` with:
```python
            "rft": extract_rft(c.rft, max_surveys=max_surveys),
```
(Add `max_surveys: int = 50` parameter to `build_bundle`.)
Run full suite → green. Commit:
```bash
git add -A && git commit -m "feat: RFT survey extraction with per-well capping"
```

---

### Task 9: Full demo ensemble + Parameters/RFT/QC tabs

**Files:**
- Create: `demo/make_demo.py`
- Modify: `resdash/assets/dashboard.js` (add three tab renderers, drop the `window.DASH` stub)
- Test: `tests/test_demo.py`

**Interfaces:**
- Consumes: all extractors; `demo_io.write_summary`, `rft_fixture.write_rft` (if available).
- Produces: `demo/runs/REAL-01 … REAL-08/<CASE>_V<i>.{SMSPEC,UNSMRY,DATA}` + `_PROP_{PORO,PERMX}.GRDECL` + `.PRT`; `demo/bundle.json` (gitignored) → `demo_dashboard.html` (committed). New JS globals: `renderParameters()`, `renderRFT()`, `renderQC()`.

- [ ] **Step 1: Write the failing test**

`tests/test_demo.py`:
```python
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_demo_builds_and_is_deterministic(tmp_path):
    r = subprocess.run([sys.executable, str(ROOT / "demo" / "make_demo.py"),
                        "--out", str(tmp_path)], capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stderr
    runs = sorted((tmp_path).glob("REAL-*"))
    assert len(runs) == 8
    for d in runs:
        smspecs = list(d.glob("*.SMSPEC"))
        assert len(smspecs) == 1 and (d / smspecs[0].with_suffix(".UNSMRY").name).exists()
    b = json.loads((tmp_path / "bundle.json").read_text())
    assert len(b["cases"]) == 8
    fopts = [c["vectors"]["FOPT"]["data"][-1] for c in b["cases"]]
    assert max(fopts) / min(fopts) > 1.3      # realizations genuinely differ
    params_spread = [c["params"]["PORO_MEAN"] for c in b["cases"]]
    assert max(params_spread) > min(params_spread)   # params captured
    # deterministic: second run byte-identical (except generated_utc)
    r2 = subprocess.run([sys.executable, str(ROOT / "demo" / "make_demo.py"),
                         "--out", str(tmp_path / "again")], capture_output=True, text=True, timeout=300)
    assert r2.returncode == 0
    strip = lambda s: json.dumps({k: v for k, v in json.loads(s).items() if k != "generated_utc"},
                                 sort_keys=True)
    assert strip((tmp_path / "bundle.json").read_text()) == \
           strip((tmp_path / "again" / "bundle.json").read_text())
```

- [ ] **Step 2: Run → FAIL. Step 3: Implement `demo/make_demo.py`**

```python
#!/usr/bin/env python3
"""Generate the synthetic stochastic demo ensemble (8 realizations)."""
import argparse
import datetime as dt
import math
import random
import warnings
from pathlib import Path

warnings.filterwarnings("ignore", category=DeprecationWarning)

from resdash.bundle import build_bundle, dump_bundle  # noqa: E402
from resdash.demo_io import write_summary  # noqa: E402

# realization knobs: (poro_mult, permx_mult, inj_rate, prod_target)
KNOBS = [
    (0.85, 0.70, 4000, 2500), (0.85, 1.40, 4000, 2500),
    (1.00, 0.70, 5000, 3000), (1.00, 1.00, 5000, 3000),
    (1.00, 1.40, 5000, 3000), (1.15, 0.70, 6000, 3500),
    (1.15, 1.00, 6000, 3500), (1.15, 1.40, 6000, 3500),
]
BASE_PORO = [0.18, 0.20, 0.22, 0.24, 0.26, 0.28, 0.30, 0.32]
BASE_PERM = [10.0, 50.0, 100.0, 200.0, 350.0, 500.0, 750.0, 1000.0]
WELLS = ["P1", "P2", "P3"]
START = dt.datetime(2020, 1, 1)


def _sim(knobs, seed):
    """Synthetic waterflood: decline + water breakthrough, responsive to knobs."""
    poro_mult, perm_mult, inj_rate, prod_target = knobs
    rng = random.Random(seed)
    days = list(range(0, 3653, 31))                     # 10 years monthly
    fopr, fopt, fwpr, fwpt, fwir, fwit, fpr = [], [], [], [], [], [], []
    bth = 12.0 * (2.0 - min(perm_mult, 1.4) / 1.4) + rng.uniform(-3, 3)  # breakthrough month
    for i, d in enumerate(days):
        m = i
        wct = 1 / (1 + math.exp(-(m - bth) / 6)) * 0.95
        rate = prod_target * min(1.0, perm_mult ** 0.5) * math.exp(-0.004 * m) * (0.9 + 0.2 * poro_mult)
        oil, water = rate * (1 - wct), rate * wct
        fopr.append(oil); fwpr.append(water); fwir.append(inj_rate * (1 + 0.02 * math.sin(m / 6)))
        fopt.append((fopt[-1] if fopt else 0.0) + oil * 31)
        fwpt.append((fwpt[-1] if fwpt else 0.0) + water * 31)
        fwit.append((fwit[-1] if fwit else 0.0) + fwir[-1] * 31)
        fpr.append(300.0 - 0.0025 * d + 40.0 * poro_mult * math.exp(-d / 1200) + rng.uniform(-2, 2))
    return {"FOPR": {"unit": "SM3/DAY", "data": fopr}, "FOPT": {"unit": "SM3", "data": fopt},
            "FWPR": {"unit": "SM3/DAY", "data": fwpr}, "FWPT": {"unit": "SM3", "data": fwpt},
            "FWIR": {"unit": "SM3/DAY", "data": fwir}, "FWIT": {"unit": "SM3", "data": fwit},
            "FPR": {"unit": "BARSA", "data": fpr},
            "FGPR": {"unit": "SM3/DAY", "data": [0] * len(days)},
            **{f"WOPR:{w}": {"unit": "SM3/DAY", "data": [v / 3 for v in fopr]} for w in WELLS},
            **{f"WWPR:{w}": {"unit": "SM3/DAY", "data": [v / 3 for v in fwpr]} for w in WELLS},
            **{f"WBHP:{w}": {"unit": "BARSA", "data": [v * 1.1 for v in fpr]} for w in WELLS}}


def _write_case(out: Path, idx: int, knobs) -> str:
    case = f"STOCH_DEMO_{idx:02d}_V{idx}"
    d = out / f"REAL-{idx:02d}"
    d.mkdir(parents=True, exist_ok=True)
    write_summary(case, START, list(range(0, 3653, 31)), _sim(knobs, seed=idx), d)
    poro_mult, perm_mult, inj, prod = knobs
    (d / f"{case}.DATA").write_text(
        "RUNSPEC\nTITLE\n 'synthetic demo'\n/\nSCHEDULE\n"
        f"WCONPROD\n 'P1' 'ORAT' {prod / 3:.1f} 4* 30 /\n /\n"
        f"WCONINJE\n 'I1' 'WATER' 'OPEN' 'RATE' {inj:.1f} 1* 500 /\n /\n"
        f"MULTIPLY\n 'PORO' {poro_mult} /\n 'PERMX' {perm_mult} /\n /\n"
        "DATES\n 1 'JAN' 2030 /\n /\n", encoding="utf-8")
    (d / f"{case}_PROP_PORO.GRDECL").write_text(
        "PORO\n " + " ".join(f"{v * poro_mult:.4f}" for v in BASE_PORO) + " /\n", encoding="utf-8")
    (d / f"{case}_PROP_PERMX.GRDECL").write_text(
        "PERMX\n " + " ".join(f"{v * perm_mult:.2f}" for v in BASE_PERM) + " /\n", encoding="utf-8")
    mb = [0.0002, 0.0031, 0.0009, 0.0004, 0.0006, 0.0022, 0.0005, 0.0008][idx - 1]
    (d / f"{case}.PRT").write_text(
        " NEW TIME STEP\n" * 120 +
        f" MATERIAL BALANCE ERROR  AT 2030-01-01:     {mb:.4f}E-03 PERCENT\n"
        " FLUID VOLUMES IN PLACE  (SURFACE)  FOR REGION     1\n"
        f"   OIL   SM3      {1.1e7 * poro_mult:.1f}   GAS  SM3       0.   WATER SM3      {3.0e7:.1f}\n"
        " TOTAL CPU TIME :   0.3600E+05 SECONDS\n", encoding="utf-8")
    return case


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(Path(__file__).parent / "runs"))
    ap.add_argument("--bundle", default=None, help="also write bundle.json here")
    args = ap.parse_args()
    out = Path(args.out)
    for i, knobs in enumerate(KNOBS, start=1):
        print(f"realization {i}: {knobs}")
        _write_case(out, i, knobs)
    b = build_bundle(str(out))
    dump_bundle(b, args.bundle or str(out.parent / "bundle.json"))
    print(f"wrote {len(b['cases'])} cases")


if __name__ == "__main__":
    main()
```
(The synthetic `_sim` model is deliberately simple — decline + sigmoid water breakthrough driven by the realization knobs — but produces genuinely distinct FOPT outcomes so tornado/P10-P90 views show real spread.)

- [ ] **Step 4: Add the three remaining tab renderers to `dashboard.js`** (replace the `window.DASH = ...` stub line with these calls at boot: `renderParameters(); renderRFT(); renderQC();`)

```javascript
/* ---------- Parameters ---------- */
function numericParams() {
  const keys = new Set();
  CASES.forEach(c => Object.entries(c.params || {})
    .forEach(([k, v]) => { if (typeof v === 'number' && isFinite(v)) keys.add(k); }));
  return [...keys].sort();
}
function spearman(x, y) {
  const rank = a => { const idx = [...a.keys()].sort((i, j) => a[i] - a[j]);
    const r = new Array(a.length); let i = 0;
    while (i < idx.length) { let j = i;
      while (j + 1 < idx.length && a[idx[j + 1]] === a[idx[i]]) j++;
      const v = (i + j) / 2 + 1; for (let k = i; k <= j; k++) r[idx[k]] = v; i = j + 1; }
    return r; };
  const rx = rank(x), ry = rank(y), n = x.length;
  const mx = rx.reduce((s, v) => s + v, 0) / n, my = ry.reduce((s, v) => s + v, 0) / n;
  let num = 0, dx = 0, dy = 0;
  for (let i = 0; i < n; i++) { num += (rx[i] - mx) * (ry[i] - my); dx += (rx[i] - mx) ** 2; dy += (ry[i] - my) ** 2; }
  return num / Math.sqrt(dx * dy || 1);
}
function renderParameters() {
  const endpoints = ['FOPT', 'FGPT', 'FWPT', 'FWIT', 'FGIT'];
  $('parameters').innerHTML =
    '<div class="panel"><div class="controls">' +
    '<label>End-point <select id="pa-endpoint">' + endpoints.map(k => `<option>${k}</option>`).join('') + '</select></label>' +
    '<label>Parameter <select id="pa-param"></select></label></div>' +
    '<div class="controls"><div id="pa-tornado" class="plot" style="height:380px"></div>' +
    '<div id="pa-scatter" class="plot" style="height:380px"></div></div></div>' +
    '<div class="panel"><table id="pa-table"></table></div>';
  const params = numericParams();
  $('pa-param').innerHTML = params.map(k => `<option>${esc(k)}</option>`).join('');
  const table = () => {
    const keys = [...new Set(CASES.flatMap(c => Object.keys(c.params || {})))].sort();
    $('pa-table').innerHTML = '<tr><th>case</th>' + keys.map(k => `<th>${esc(k)}</th>`).join('') + '</tr>' +
      CASES.map(c => '<tr><td>' + esc(c.name) + '</td>' +
        keys.map(k => { const v = (c.params || {})[k]; return `<td>${v == null ? '–' : esc(v)}</td>`; }).join('') + '</tr>').join('');
  };
  const draw = () => {
    const end = $('pa-endpoint').value;
    const ys = CASES.map(c => lastVal(c, end));
    const pairs = CASES.map((c, i) => ({ c, y: ys[i] })).filter(p => p.y != null);
    const cors = params.map(p => {
      const xs = pairs.map(pr => pr.c.params[p]);
      const yy = pairs.map(pr => pr.y);
      return xs.every(v => typeof v === 'number') && new Set(xs).size > 1 ? { p, rho: spearman(xs, yy) } : null;
    }).filter(Boolean).sort((a, b) => Math.abs(b.rho) - Math.abs(a.rho));
    Plotly.newPlot('pa-tornado', [{
      type: 'bar', orientation: 'h', x: cors.map(c => c.rho), y: cors.map(c => c.p),
      marker: { color: cors.map(c => c.rho >= 0 ? '#4fc3f7' : '#ef9a9a') },
    }], { ...LAYOUT, title: `Spearman ρ vs ${end}`, yaxis: { ...LAYOUT.yaxis, autorange: 'reversed' } },
      { displayModeBar: false });
    const p = $('pa-param').value;
    Plotly.newPlot('pa-scatter', [{
      x: pairs.map(pr => pr.c.params[p]), y: pairs.map(pr => pr.y),
      mode: 'markers', text: pairs.map(pr => pr.c.name),
      marker: { size: 9, color: '#4fc3f7' },
    }], { ...LAYOUT, xaxis: { ...LAYOUT.xaxis, title: p }, yaxis: { ...LAYOUT.yaxis, title: end } },
      { displayModeBar: false });
    table();
  };
  $('pa-endpoint').onchange = draw; $('pa-param').onchange = draw; draw();
}

/* ---------- RFT ---------- */
function renderRFT() {
  const wells = [...new Set(CASES.flatMap(c => (c.rft || []).map(s => s.well)))].sort();
  if (!wells.length) {
    $('rft').innerHTML = '<div class="panel muted">No RFT data available for these cases ' +
      '(cases run without RFT output, or .RFT files not found next to the summary files).</div>';
    return;
  }
  $('rft').innerHTML =
    '<div class="panel"><div class="controls">' +
    '<label>Well <select id="rft-well">' + wells.map(w => `<option>${esc(w)}</option>`).join('') + '</select></label>' +
    '<label>Date <select id="rft-date"></select></label></div>' +
    '<div class="controls" id="rft-cases"></div><div id="rft-plot" class="plot"></div></div>';
  const datesFor = w => [...new Set(CASES.flatMap(c => (c.rft || [])
    .filter(s => s.well === w).map(s => s.date)))].sort();
  const refreshDates = () => {
    const w = $('rft-well').value;
    $('rft-date').innerHTML = datesFor(w).map(d => `<option>${d}</option>`).join('');
    $('rft-cases').innerHTML = '<label class="muted">Cases</label>' +
      CASES.map((c, i) => (c.rft || []).some(s => s.well === w) ?
        `<label><input type="checkbox" class="rft-case" value="${i}" checked> ${esc(c.name)}</label>` : '').join('');
    document.querySelectorAll('.rft-case').forEach(cb => cb.onchange = draw);
    draw();
  };
  const draw = () => {
    const w = $('rft-well').value, d = $('rft-date').value;
    const traces = [...document.querySelectorAll('.rft-case:checked')].map(cb => CASES[+cb.value])
      .map(c => (c.rft || []).find(s => s.well === w && s.date === d))
      .filter(Boolean).map(s => ({ name: s.well + ' ' + s.date, x: s.pressure, y: s.depth, mode: 'lines+markers' }));
    Plotly.newPlot('rft-plot', traces,
      { ...LAYOUT, yaxis: { ...LAYOUT.yaxis, autorange: 'reversed', title: 'depth' },
        xaxis: { ...LAYOUT.xaxis, title: 'pressure' } }, { responsive: true });
  };
  $('rft-well').onchange = refreshDates; $('rft-date').onchange = draw;
  refreshDates();
}

/* ---------- QC ---------- */
function renderQC() {
  const hasQC = CASES.some(c => c.qc && Object.keys(c.qc).length);
  $('qc').innerHTML = hasQC
    ? '<div class="panel"><table id="qc-table"></table></div>' +
      '<div class="panel"><div id="qc-mb" class="plot"></div></div>' +
      '<div class="panel"><h3 class="muted">FIP by region</h3><div id="qc-fip"></div></div>'
    : '<div class="panel muted">No QC data (.PRT) found for these cases.</div>';
  if (!hasQC) return;
  $('qc-table').innerHTML =
    '<tr><th>case</th><th>MB error max (%)</th><th>timesteps</th><th>CPU (h)</th></tr>' +
    CASES.map(c => `<tr><td>${esc(c.name)}</td><td>${fmt(c.qc.mb_error_max, 2)}</td>` +
      `<td>${c.qc.timesteps ?? '–'}</td><td>${fmt(c.qc.cpu_hours, 3)}</td></tr>`).join('');
  Plotly.newPlot('qc-mb', [{
    type: 'bar', x: CASES.map(c => c.name), y: CASES.map(c => c.qc.mb_error_max ?? null),
    marker: { color: '#ef9a9a' },
  }], { ...LAYOUT, yaxis: { ...LAYOUT.yaxis, title: 'MB error max (%)' } }, { displayModeBar: false });
  const regionSel = document.createElement('select');
  const regions = [...new Set(CASES.flatMap(c => Object.keys((c.qc.fip_regions || {}))))].sort();
  regionSel.innerHTML = regions.map(r => `<option>${r}</option>`).join('');
  $('qc-fip').appendChild(regionSel); $('qc-fip').appendChild(document.createElement('div')).id = 'qc-fip-plot';
  const drawFip = () => {
    const r = regionSel.value;
    Plotly.newPlot('qc-fip-plot', ['oil_sm3', 'gas_sm3', 'water_sm3'].map((ph, i) => ({
      type: 'bar', name: ph.replace('_sm3', ''), x: CASES.map(c => c.name),
      y: CASES.map(c => (c.qc.fip_regions || {})[r] ? c.qc.fip_regions[r][ph] ?? 0 : null),
    })), { ...LAYOUT, barmode: 'group', yaxis: { ...LAYOUT.yaxis, title: `region ${r} (SM3)` } },
      { displayModeBar: false });
  };
  regionSel.onchange = drawFip; drawFip();
}
```

- [ ] **Step 5: Run tests + build demo dashboard**

```bash
python -m pytest tests -q
python demo/make_demo.py
python build_dashboard.py demo/runs -o demo_dashboard.html
```
Open `demo_dashboard.html` in a browser; click all five tabs. Fix any JS console errors (F12).

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "feat: full demo ensemble + Parameters/RFT/QC tabs"
```

---

### Task 10: Streamlit app

**Files:**
- Create: `app.py`, `tests/test_app.py`

**Interfaces:**
- Consumes: bundle (Task 4 schema).
- Produces: importable functions `load_bundle(path) -> dict`, `fig_overview(b) -> plotly figure`, `fig_timeseries(b, key, cases, logy) -> figure`, `fig_parameters(b, endpoint) -> figure`, `fig_rft(b, well, date, cases) -> figure`, `fig_qc(b) -> figure`; `streamlit run app.py` UI with the five tabs.

- [ ] **Step 1: Write the failing test**

`tests/test_app.py`:
```python
import json
import subprocess
import sys
from pathlib import Path

import plotly.graph_objects as go

from resdash.bundle import build_bundle
from resdash.demo_io import write_summary
import datetime


def _bundle(tmp_path):
    days = [0.0, 30.0, 60.0]
    for i, m in enumerate([1.0, 1.3]):
        write_summary(f"C{i}_V{i}", datetime.datetime(2020, 1, 1), days,
                      {"FOPR": {"unit": "SM3/DAY", "data": [0, 1000 * m, 900 * m]}},
                      tmp_path / f"R{i}")
    return build_bundle(str(tmp_path))


def test_figures_build(tmp_path, monkeypatch):
    monkeypatch.setenv("DASH_TEST", "1")
    import app
    b = _bundle(tmp_path)
    assert isinstance(app.fig_overview(b), go.Figure)
    fig = app.fig_timeseries(b, "FOPR", [b["cases"][0]["name"]], logy=False)
    assert len(fig.data) == 1
    assert isinstance(app.fig_parameters(b, "FOPR"), go.Figure)
    assert isinstance(app.fig_qc(b), go.Figure)


def test_syntax_check():
    r = subprocess.run([sys.executable, "-m", "py_compile", "app.py"], capture_output=True)
    assert r.returncode == 0
```

- [ ] **Step 2: Run → FAIL. Step 3: Implement `app.py`**

```python
#!/usr/bin/env python3
"""Streamlit frontend for the ECLIPSE ensemble dashboard (same bundle as the static HTML)."""
import warnings

warnings.filterwarnings("ignore", category=DeprecationWarning)

import json
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

from resdash.bundle import build_bundle, load_bundle, validate_bundle

st.set_page_config(page_title="ECLIPSE Ensemble Dashboard", layout="wide", page_icon="🛢️")

TEMPLATE = dict(paper_bgcolor="#0e1117", plot_bgcolor="#262730", font=dict(color="#fafafa"))


def load_bundle(path):  # thin wrapper kept for tests/import parity
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _last(c, key):
    v = c["vectors"].get(key)
    return None if not v else next((x for x in reversed(v["data"]) if x is not None), None)


def fig_overview(b):
    fig = go.Figure()
    names = [c["name"] for c in b["cases"]]
    fig.add_bar(x=names, y=[_last(c, "FOPT") for c in b["cases"]], name="FOPT")
    fig.add_bar(x=names, y=[_last(c, "FWPT") for c in b["cases"]], name="FWPT")
    fig.update_layout(barmode="group", **TEMPLATE)
    return fig


def fig_timeseries(b, key, case_names, logy=False):
    fig = go.Figure()
    for c in b["cases"]:
        if c["name"] not in case_names or key not in c["vectors"]:
            continue
        v = c["vectors"][key]
        fig.add_scatter(x=c["vectors"]["TIME"], y=v["data"], mode="lines", name=c["name"])
    fig.update_layout(yaxis_type="log" if logy else "linear", **TEMPLATE)
    return fig


def fig_parameters(b, endpoint):
    import numpy as np
    ys = np.array([_last(c, endpoint) or 0.0 for c in b["cases"]], dtype=float)
    keys = sorted({k for c in b["cases"] for k, v in c.get("params", {}).items()
                   if isinstance(v, (int, float))})
    rhos = []
    for k in keys:
        xs = np.array([c.get("params", {}).get(k, np.nan) for c in b["cases"]], dtype=float)
        if np.isfinite(xs).all() and len(set(xs)) > 1:
            rx, ry = xs.argsort().argsort().astype(float), ys.argsort().argsort().astype(float)
            rhos.append((k, float(np.corrcoef(rx, ry)[0, 1])))
    rhos.sort(key=lambda t: abs(t[1]), reverse=True)
    fig = go.Figure(go.Bar(x=[r for _, r in rhos], y=[k for k, _ in rhos], orientation="h",
                           marker_color=["#4fc3f7" if r >= 0 else "#ef9a9a" for _, r in rhos]))
    fig.update_layout(title=f"Spearman rho vs {endpoint}", **TEMPLATE)
    return fig


def fig_rft(b, well, date, case_names):
    fig = go.Figure()
    for c in b["cases"]:
        if c["name"] not in case_names:
            continue
        for s in c.get("rft", []):
            if s["well"] == well and s["date"] == date:
                fig.add_scatter(x=s["pressure"], y=s["depth"], mode="lines+markers", name=c["name"])
    fig.update_layout(yaxis_autorange="reversed", **TEMPLATE)
    return fig


def fig_qc(b):
    fig = go.Figure(go.Bar(x=[c["name"] for c in b["cases"]],
                           y=[(c.get("qc") or {}).get("mb_error_max") for c in b["cases"]],
                           marker_color="#ef9a9a"))
    fig.update_layout(yaxis_title="MB error max (%)", **TEMPLATE)
    return fig


def main():
    st.title("🛢️ ECLIPSE Ensemble Dashboard")
    src = st.sidebar.text_input("Bundle JSON path", value="demo/bundle.json")
    folder = st.sidebar.text_input("…or runs folder to extract now", value="")
    if folder and Path(folder).exists():
        b = build_bundle(folder)
    elif Path(src).exists():
        b = load_bundle(src)
    else:
        st.info("Point the sidebar at a bundle.json or a runs folder. "
                "Build one with: python build_dashboard.py <runs_folder>")
        return
    errs = validate_bundle(b)
    if errs:
        st.error("; ".join(errs)); return
    st.caption(f"{len(b['cases'])} cases · generated {b['generated_utc']}")
    keys = sorted(k for c in b["cases"][:1] for k in c["vectors"] if k not in ("TIME", "DATE"))
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["Overview", "Time Series", "Parameters", "RFT", "QC"])
    with tab1:
        st.plotly_chart(fig_overview(b), use_container_width=True)
        st.dataframe([{"case": c["name"], "realization": c["realization"],
                       "FOPT": _last(c, "FOPT"), "FWPT": _last(c, "FWPT"),
                       "FPR": _last(c, "FPR")} for c in b["cases"]], hide_index=True)
    with tab2:
        key = st.selectbox("Vector", keys)
        names = st.multiselect("Cases", [c["name"] for c in b["cases"]],
                               default=[c["name"] for c in b["cases"][:2]])
        st.plotly_chart(fig_timeseries(b, key, names, st.checkbox("log Y")), use_container_width=True)
    with tab3:
        endpoint = st.selectbox("End-point", ["FOPT", "FGPT", "FWPT", "FWIT", "FGIT"])
        st.plotly_chart(fig_parameters(b, endpoint), use_container_width=True)
        st.dataframe([{ "case": c["name"], **c.get("params", {})} for c in b["cases"]], hide_index=True)
    with tab4:
        wells = sorted({s["well"] for c in b["cases"] for s in c.get("rft", [])})
        if wells:
            w = st.selectbox("Well", wells)
            dates = sorted({s["date"] for c in b["cases"] for s in c.get("rft", []) if s["well"] == w})
            d = st.selectbox("Date", dates)
            st.plotly_chart(fig_rft(b, w, d, [c["name"] for c in b["cases"]]), use_container_width=True)
        else:
            st.info("No RFT data in this bundle.")
    with tab5:
        st.plotly_chart(fig_qc(b), use_container_width=True)
        st.dataframe([{"case": c["name"], **(c.get("qc") or {})} for c in b["cases"]], hide_index=True)


if not os.environ.get("DASH_TEST"):
    main()  # streamlit executes the script top-to-bottom; tests set DASH_TEST=1
```
(`os` is already imported at the top of the file — the guard lets pytest import `app` without launching the Streamlit UI. In `tests/test_app.py`, call `monkeypatch.setenv("DASH_TEST", "1")` BEFORE `import app` inside each test.)

- [ ] **Step 4: Run tests → pass; manual smoke `streamlit run app.py` → verify tabs. Commit**

```bash
python -m pytest tests -q
git add -A && git commit -m "feat: Streamlit frontend sharing the bundle"
```

---

### Task 11: Windows launcher + README

**Files:**
- Create: `run_dashboard.bat`, `README.md`

- [ ] **Step 1: `run_dashboard.bat`**

```bat
@echo off
setlocal
REM ECLIPSE Ensemble Dashboard - double-click convenience launcher.
REM Usage: run_dashboard.bat [folder_with_eclipse_runs]   (default: .)
set "FOLDER=%~1"
if "%FOLDER%"=="" set "FOLDER=%~dp0."
where py >nul 2>nul
if errorlevel 1 (
  echo Python launcher "py" not found. Install Python 3 from python.org ^(tick "py launcher"^).
  pause & exit /b 1
)
py -3 -c "import resdata, plotly, streamlit" >nul 2>nul
if errorlevel 1 (
  echo Installing dependencies ^(one-time^)...
  py -3 -m pip install -r "%~dp0requirements.txt"
)
py -3 "%~dp0build_dashboard.py" "%FOLDER%" -o "%~dp0dashboard.html"
if errorlevel 1 ( pause & exit /b 1 )
start "" "%~dp0dashboard.html"
endlocal
```

- [ ] **Step 2: `README.md`** — sections: What it is (1 para + screenshot placeholders), Demo in 10 seconds (download ZIP → open `demo_dashboard.html`), Build from your ECLIPSE runs (bat + CLI + options table), Streamlit mode, What gets analyzed (5 tabs), Data privacy (real data never leaves your PC; repo holds synthetic demo only), Requirements (Windows 10/11 + browser; Python 3.10+ optional for building), Development (pytest), License (MIT). Real screenshots added in Task 12 after CI builds (use manual screenshots captured during Task 9 verification).

- [ ] **Step 3: Verify `.bat` runs end-to-end on the demo**

```bash
cmd //c "run_dashboard.bat demo\\runs"
```
Expected: `dashboard.html` opens in default browser with 8 cases.

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "feat: Windows launcher and README"
```

---

### Task 12: CI + final verification pass

**Files:**
- Create: `.github/workflows/ci.yml`
- Modify: `README.md` (screenshots into `docs/screenshots/`)

- [ ] **Step 1: CI workflow**

`.github/workflows/ci.yml`:
```yaml
name: ci
on: [push, pull_request]
jobs:
  test:
    strategy:
      matrix:
        os: [windows-latest, ubuntu-latest]
    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install -r requirements.txt
      - run: python -m pytest tests -q
      - run: python demo/make_demo.py --out demo_runs --bundle demo_bundle.json
      - run: python build_dashboard.py demo_runs -o ci_dashboard.html
      - uses: actions/upload-artifact@v4
        with: { name: dashboard-${{ matrix.os }}, path: ci_dashboard.html }
```

- [ ] **Step 2: Full local verification**

```bash
python -m pytest tests -q
python demo/make_demo.py
python build_dashboard.py demo/runs -o demo_dashboard.html
cmd //c "run_dashboard.bat demo\\runs"
```
All green + browser shows 8 cases, five tabs functional. Capture screenshots → `docs/screenshots/`.

- [ ] **Step 3: Commit**

```bash
git add -A && git commit -m "ci: test matrix + demo dashboard rebuild"
```

---

### Task 13: Publish to GitHub

- [ ] **Step 1: Confirm clean tree, then create + push**

```bash
git status --short        # must be empty
git log --oneline         # review history
gh repo create eclipse-sim-dashboard --public --source . --push --description "Self-contained ECLIPSE ensemble analysis dashboard: summary vectors, deck parameters, RFT and PRT QC - one offline HTML file"
```

- [ ] **Step 2: Tag and verify**

```bash
git tag v0.1.0 && git push origin v0.1.0
gh repo view ojaogezi/eclipse-sim-dashboard --web
```
Verify: README renders, `demo_dashboard.html` downloadable from the repo, Actions green.
```
</content>
</invoke>
