#!/usr/bin/env python3
"""Generate the synthetic stochastic demo ensemble (8 realizations)."""
import argparse
import datetime as dt
import math
import random
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
warnings.filterwarnings("ignore", category=DeprecationWarning)

from resdash.bundle import build_bundle, dump_bundle  # noqa: E402
from resdash.demo_io import write_summary  # noqa: E402
from resdash.rft_fixture import write_rft  # noqa: E402

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
DAYS = list(range(0, 3653, 31))  # 10 years, monthly


def _sim(knobs, seed):
    """Synthetic waterflood: decline + water breakthrough, responsive to knobs."""
    poro_mult, perm_mult, inj_rate, prod_target = knobs
    rng = random.Random(seed)
    bth = 12.0 * (2.0 - min(perm_mult, 1.4) / 1.4) + rng.uniform(-3, 3)
    fopr, fwpr, fwir, fopt, fwpt, fwit, fpr = [], [], [], [], [], [], []
    for i, d in enumerate(DAYS):
        m = i
        wct = 1 / (1 + math.exp(-(m - bth) / 6)) * 0.95
        rate = prod_target * min(1.0, perm_mult ** 0.5) * math.exp(-0.004 * m) * (0.9 + 0.2 * poro_mult)
        oil, water = rate * (1 - wct), rate * wct
        fopr.append(oil)
        fwpr.append(water)
        fwir.append(inj_rate * (1 + 0.02 * math.sin(m / 6)))
        fopt.append((fopt[-1] if fopt else 0.0) + oil * 31)
        fwpt.append((fwpt[-1] if fwpt else 0.0) + water * 31)
        fwit.append((fwit[-1] if fwit else 0.0) + fwir[-1] * 31)
        fpr.append(300.0 - 0.0025 * d + 40.0 * poro_mult * math.exp(-d / 1200) + rng.uniform(-2, 2))
    return {"FOPR": {"unit": "SM3/DAY", "data": fopr}, "FOPT": {"unit": "SM3", "data": fopt},
            "FWPR": {"unit": "SM3/DAY", "data": fwpr}, "FWPT": {"unit": "SM3", "data": fwpt},
            "FWIR": {"unit": "SM3/DAY", "data": fwir}, "FWIT": {"unit": "SM3", "data": fwit},
            "FPR": {"unit": "BARSA", "data": fpr},
            "FGPR": {"unit": "SM3/DAY", "data": [0.0] * len(DAYS)},
            **{f"WOPR:{w}": {"unit": "SM3/DAY", "data": [v / 3 for v in fopr]} for w in WELLS},
            **{f"WWPR:{w}": {"unit": "SM3/DAY", "data": [v / 3 for v in fwpr]} for w in WELLS},
            **{f"WBHP:{w}": {"unit": "BARSA", "data": [v * 1.1 for v in fpr]} for w in WELLS}}


def _write_rft_surveys(d: Path, case: str, knobs, p_end: float) -> None:
    poro_mult = knobs[0]
    surveys = []
    for wi, w in enumerate(WELLS):
        top = 1000.0 + 300.0 * wi
        for si, (months, days) in enumerate([(24, 730), (60, 1825)]):
            date = dt.date(2020, 1, 1) + dt.timedelta(days=days)
            n = 5
            depths = [top + 20.0 * k for k in range(n)]
            # pressure gradient + depletion with time, realization-dependent
            grad = 0.02 * (1.1 - 0.1 * poro_mult)
            pressures = [p_end * (0.9 - 0.05 * si) + grad * (depth - top) for depth in depths]
            surveys.append({"well": w, "date": date, "days": float(days),
                            "ijk": [(wi + 1, 1, k + 1) for k in range(n)],
                            "DEPTH": depths, "PRESSURE": pressures})
    write_rft(d / f"{case}.RFT", surveys)


def _write_case(out: Path, idx: int, knobs) -> str:
    case = f"STOCH_DEMO_{idx:02d}_V{idx}"
    d = out / f"REAL-{idx:02d}"
    d.mkdir(parents=True, exist_ok=True)
    vectors = _sim(knobs, seed=idx)
    write_summary(case, START, DAYS, vectors, d)
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
    _write_rft_surveys(d, case, knobs, p_end=vectors["FPR"]["data"][-1])
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
