"""Read ECLIPSE SMSPEC/UNSMRY into tidy parallel arrays."""
import warnings

warnings.filterwarnings("ignore", category=DeprecationWarning)

from resdata.summary import Summary  # noqa: E402  (pip resdata, not our resdash)

TIME_KEYS = ("TIME", "DATE")


def round6(v: float) -> float:
    return float(f"{v:.6g}")


def _least_significant(idx: list[int], values) -> int:
    """Position in idx of the interior point closest to the line between neighbors."""
    best, best_gap = None, float("inf")
    for i in range(1, len(idx) - 1):
        gap = abs(values[idx[i]] - (values[idx[i - 1]] + values[idx[i + 1]]) / 2)
        if gap < best_gap:
            best, best_gap = i, gap
    return best


def thin_minmax(values, max_points: int) -> list[int]:
    """Indices (≤ max_points) keeping ends, global extremes and per-bucket min/max."""
    n = len(values)
    if n <= max_points:
        return list(range(n))
    gmin = min(range(n), key=lambda i: values[i])
    gmax = max(range(n), key=lambda i: values[i])
    keep = {0, n - 1, gmin, gmax}
    buckets = max(max_points - 4, 1)
    step = n / buckets
    for b in range(buckets):
        lo = int(b * step)
        hi = max(int((b + 1) * step), lo + 1)
        seg = values[lo:hi]
        keep.add(lo + min(range(len(seg)), key=lambda i: seg[i]))
        keep.add(lo + max(range(len(seg)), key=lambda i: seg[i]))
    out = sorted(keep)
    if len(out) > max_points:
        stride = (len(out) - 1) / (max_points - 1)
        out = sorted({out[round(i * stride)] for i in range(max_points)}
                     | {out[0], out[-1], gmin, gmax})
        while len(out) > max_points:  # rare: union added a few over budget
            out.pop(_least_significant(out, values))
    return out


def _unit(s, key: str) -> str:
    for getter in ("get_unit", "unit"):
        try:
            u = getattr(s, getter)(key)
            if u and u != "None":
                return str(u)
        except Exception:
            continue
    return ""


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
        if key in TIME_KEYS:
            continue
        vals = s.get_values(key)
        out[key] = {"unit": _unit(s, key), "data": [round6(float(vals[i])) for i in keep]}
    return out
