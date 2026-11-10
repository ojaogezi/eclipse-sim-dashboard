"""Write small ECLIPSE .RFT binaries (used by tests and the demo generator).

Layout produced matches what resdata/resfo_utilities expect for an RFT survey:
TIME, DATE, WELLETC, CONIPOS/CONJPOS/CONKPOS, then DEPTH/PRESSURE/SWAT/SGAS
arrays, repeated per survey.
"""
import datetime

import numpy as np
import resfo


def write_rft(path, surveys: list[dict]) -> None:
    """surveys: [{'well': str, 'date': datetime.date, 'days': float,
                  'ijk': [(i,j,k), ...], 'DEPTH': [...], 'PRESSURE': [...],
                  'SWAT': [...], 'SGAS': [...]}]"""
    def kw(name: str) -> str:
        return name.ljust(8)  # resfo requires exactly 8-char keywords

    contents = []
    for s in surveys:
        n = len(s["DEPTH"])
        well_etc = ["DAYS", s["well"], "", "METRES", "BARSA", "R", "STANDARD"] + [""] * 7
        contents.append((kw("TIME"), np.array([float(s["days"])], dtype=np.float32)))
        contents.append((kw("DATE"), np.array(
            [s["date"].day, s["date"].month, s["date"].year], dtype=np.int32)))
        contents.append((kw("WELLETC"), np.array(well_etc, dtype="S8")))
        contents.append((kw("CONIPOS"), np.array([c[0] for c in s["ijk"]], dtype=np.int32)))
        contents.append((kw("CONJPOS"), np.array([c[1] for c in s["ijk"]], dtype=np.int32)))
        contents.append((kw("CONKPOS"), np.array([c[2] for c in s["ijk"]], dtype=np.int32)))
        contents.append((kw("DEPTH"), np.array(s["DEPTH"], dtype=np.float32)))
        contents.append((kw("PRESSURE"), np.array(s["PRESSURE"], dtype=np.float32)))
        contents.append((kw("SWAT"), np.array(s.get("SWAT", [0.2] * n), dtype=np.float32)))
        contents.append((kw("SGAS"), np.array(s.get("SGAS", [0.0] * n), dtype=np.float32)))
    resfo.write(str(path), contents)
