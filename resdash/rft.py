"""Read ECLIPSE .RFT surveys via resdata into plain arrays."""
import warnings

warnings.filterwarnings("ignore", category=DeprecationWarning)

from resdata.rft import ResdataRFTFile  # noqa: E402  (pip resdata, not our resdash)

from resdash.summary import round6  # noqa: E402


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
                # resdata 6.x cells expose .depth/.pressure properties
                # (older C builds used get_depth()/get_pressure())
                d = getattr(cell, "depth", None)
                p = getattr(cell, "pressure", None)
                if d is None and hasattr(cell, "get_depth"):
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
