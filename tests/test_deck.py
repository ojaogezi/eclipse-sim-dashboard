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
