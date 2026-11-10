import datetime

from resdash.rft import extract_rft
from resdash.rft_fixture import write_rft


def test_rft_binary_roundtrip(tmp_path):
    p = tmp_path / "CASE.RFT"
    write_rft(p, [
        {"well": "P1", "date": datetime.date(2021, 6, 1), "days": 500.0,
         "ijk": [(1, 1, 1), (1, 1, 2)],
         "DEPTH": [1000.0, 1010.0], "PRESSURE": [250.0, 252.0]},
        {"well": "P1", "date": datetime.date(2022, 6, 1), "days": 900.0,
         "ijk": [(1, 1, 1), (1, 1, 2)],
         "DEPTH": [1000.0, 1010.0], "PRESSURE": [240.0, 241.0]},
        {"well": "P2", "date": datetime.date(2022, 6, 1), "days": 900.0,
         "ijk": [(2, 3, 4)], "DEPTH": [2000.0], "PRESSURE": [300.0]},
    ])
    out = extract_rft(str(p))
    assert {"well": "P2", "date": "2022-06-01", "depth": [2000.0], "pressure": [300.0]} in out
    p1 = sorted([s for s in out if s["well"] == "P1"], key=lambda s: s["date"])
    assert [s["date"] for s in p1] == ["2021-06-01", "2022-06-01"]
    assert p1[0]["depth"] == [1000.0, 1010.0]
    assert p1[0]["pressure"] == [250.0, 252.0]


def test_rft_survey_cap_keeps_latest(tmp_path):
    p = tmp_path / "MANY.RFT"
    write_rft(p, [
        {"well": "P1", "date": datetime.date(2020 + i, 1, 1), "days": 365.0 * (i + 1),
         "ijk": [(1, 1, 1)], "DEPTH": [1000.0 + i], "PRESSURE": [200.0 - i]}
        for i in range(5)
    ])
    out = extract_rft(str(p), max_surveys=2)
    assert len(out) == 2
    assert out[-1]["date"] == "2024-01-01"   # latest kept


def test_extract_rft_none_and_garbage(tmp_path):
    assert extract_rft(None) == []
    junk = tmp_path / "JUNK.RFT"
    junk.write_bytes(b"not an rft file")
    assert extract_rft(str(junk)) == []
