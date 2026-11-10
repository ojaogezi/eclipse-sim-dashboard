"""Find ECLIPSE cases (SMSPEC/UNSMRY pairs) and their sibling files."""
import re
import warnings
from dataclasses import dataclass
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


def _match_first(name: str, regex: str | None) -> str | None:
    patterns = [regex] if regex else DEFAULT_REALIZATION_PATTERNS
    for pat in patterns:
        if not pat:
            continue
        m = re.search(pat, name, re.IGNORECASE)
        if m:
            return m.group(1)
    return None


def parse_realization(name: str, regex: str | None) -> str:
    return _match_first(name, regex) or name


ATTACHMENTS = {".PRT": "prt", ".RFT": "rft", ".DATA": "data"}


def discover(runs_folder: str, realization_regex: str | None = None) -> list[CaseFiles]:
    root = Path(runs_folder)
    found: dict[str, dict] = {}
    for p in sorted(root.rglob("*")):
        if p.is_dir():
            continue
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
        realization = parse_realization(name, realization_regex)
        if realization == name:
            # ensemble layout: REAL-01/CASEA → take the realization from the folder
            parent = Path(files["smspec"]).parent.name
            folder_real = _match_first(parent, realization_regex)
            if folder_real is not None:
                realization = folder_real
        cases.append(
            CaseFiles(
                name=name,
                realization=realization,
                folder=str(Path(files["smspec"]).parent),
                smspec=files["smspec"],
                unsmry=files["unsmry"],
                rft=files.get("rft"),
                prt=files.get("prt"),
                data=files.get("data"),
            )
        )
    return cases
