"""Stream-parse ECLIPSE .PRT for QC metrics. Defensive: every metric optional."""
import re

EXP_RE = re.compile(r"[-+]?\d+\.?\d*[Ee][-+]?\d+")   # 0.2100E-03 style (ECLIPSE standard)
PLN_RE = re.compile(r"[-+]?\d+\.\d+")                # plain decimal fallback


def _line_value(line: str) -> float | None:
    """Metric value on a labelled line: exponent float preferred, else first decimal."""
    m = EXP_RE.search(line) or PLN_RE.search(line)
    return float(m.group(0)) if m else None
TS_RE = re.compile(r"^\s*NEW TIME STEP\b", re.I)
CPU_RE = re.compile(
    r"TOTAL CPU TIME\s*:?\s*([-+]?\d+\.?\d*(?:[Ee][-+]?\d+)?)\s*(SECONDS?|MINUTES?|HOURS?)?", re.I)
FIP_RE = re.compile(r"FLUID VOLUMES IN PLACE\s+\(SURFACE\)\s+FOR REGION\s+(\d+)", re.I)
VOL_RE = re.compile(r"(OIL|GAS|WATER)\s+SM3\s+([-+]?\d+\.?\d*(?:[Ee][-+]?\d+)?)", re.I)


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
            upper = line.upper()
            if "MATERIAL BALANCE" in upper and "ERROR" in upper:
                v = _line_value(line)
                if v is not None:
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
