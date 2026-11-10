"""Write small ECLIPSE summary cases (used by tests and the demo generator)."""
import datetime
import os
import warnings
from contextlib import contextmanager
from pathlib import Path

warnings.filterwarnings("ignore", category=DeprecationWarning)

from resdata.summary import Summary  # noqa: E402  (pip resdata, not our resdash)


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
