from pathlib import Path

from resdash.discovery import discover, parse_realization


def _touch(p: Path):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("x")


def test_discover_finds_pairs_and_attachments(tmp_path):
    _touch(tmp_path / "STOCH_CHESS_BD_28_V2.SMSPEC")
    _touch(tmp_path / "STOCH_CHESS_BD_28_V2.UNSMRY")
    _touch(tmp_path / "STOCH_CHESS_BD_28_V2.PRT")
    _touch(tmp_path / "STOCH_CHESS_BD_28_V2.RFT")
    _touch(tmp_path / "other_case.SMSRY")  # junk extension: ignored
    _touch(tmp_path / "lonely.UNSMRY")     # no SMSPEC pair: skipped
    cases = discover(str(tmp_path))
    assert len(cases) == 1
    c = cases[0]
    assert c.name == "STOCH_CHESS_BD_28_V2"
    assert c.realization == "2"
    assert c.prt.endswith("STOCH_CHESS_BD_28_V2.PRT")
    assert c.rft.endswith("STOCH_CHESS_BD_28_V2.RFT")
    assert c.data is None


def test_discover_recursive_subfolders(tmp_path):
    _touch(tmp_path / "REAL-01" / "CASEA.SMSPEC")
    _touch(tmp_path / "REAL-01" / "CASEA.UNSMRY")
    _touch(tmp_path / "REAL-02" / "CASEB.SMSPEC")
    _touch(tmp_path / "REAL-02" / "CASEB.UNSMRY")
    cases = discover(str(tmp_path))
    assert {c.name for c in cases} == {"CASEA", "CASEB"}
    assert {c.realization for c in cases} == {"01", "02"}


def test_realization_regex_override():
    assert parse_realization("RUN_KR05_BASE", r"KR(\d+)") == "05"
    assert parse_realization("NO_MATCH_HERE", None) == "NO_MATCH_HERE"
