"""Assemble, validate, persist the dashboard data bundle (schema v1)."""
import datetime as dt
import json
from pathlib import Path

from resdash import __version__
from resdash.deck import extract_deck_params
from resdash.discovery import discover
from resdash.prt import extract_prt
from resdash.summary import extract_vectors

SCHEMA_VERSION = 1


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_bundle(runs_folder: str, realization_regex: str | None = None,
                 max_points: int = 4000, max_surveys: int = 50, log=print) -> dict:
    cases_out = []
    for c in discover(runs_folder, realization_regex):
        log(f"extracting {c.name} ...")
        cases_out.append({
            "name": c.name,
            "realization": c.realization,
            "folder": c.folder,
            "files": {"summary": True, "rft": bool(c.rft), "prt": bool(c.prt), "data": bool(c.data)},
            "params": extract_deck_params(c),
            "vectors": extract_vectors(c.smspec, max_points=max_points),
            "rft": [],
            "qc": extract_prt(c.prt),
        })
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
