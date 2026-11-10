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
        first = line.split()[0]
        if not line.startswith("'") and first.isalpha() and first.isupper() and len(first) > 3:
            keyword = first.upper()
        if keyword == "MULTIPLY":
            m = MULTIPLY_RE.match(line)
            if m:
                params[f"MULTIPLY:{m.group(1).upper()}"] = float(m.group(2))
            if line == "/":  # lone slash terminates the keyword; records carry their own /
                keyword = None
        elif keyword == "WCONPROD":
            m = WCONPROD_RE.match(line)
            if m:
                params[f"WCONPROD:{m.group(1)}:{m.group(2).upper()}"] = float(m.group(3))
        elif keyword == "WCONINJE":
            m = WCONINJE_RE.match(line)
            if m:
                params[f"WCONINJE:{m.group(1)}:{m.group(2).upper()}"] = float(m.group(3))
        elif keyword in ("DATES", "START"):
            m = DATES_RE.match(line)
            if m:
                iso = f"{int(m.group(3)):04d}-{MONTHS[m.group(2).upper()]:02d}-{int(m.group(1)):02d}"
                params["SCHEDULE_END" if keyword == "DATES" else "START"] = iso


def _grdecl_stats(path: Path, params: dict) -> None:
    prop = None
    tokens: list[str] = []
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = _strip_comment(raw).strip()
        if not line:
            continue
        if prop is None:
            head = line.split()[0]
            if re.fullmatch(r"[A-Z][A-Z0-9_]*", head):
                prop = head.upper()
                line = line[len(head):].strip()
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
