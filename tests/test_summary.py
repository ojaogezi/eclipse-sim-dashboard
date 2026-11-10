import datetime

from resdash.demo_io import write_summary
from resdash.summary import extract_vectors, round6, thin_minmax


def test_roundtrip_and_units(tmp_path):
    days = [0.0, 30.0, 61.0, 91.0]
    fopr = [0.0, 9500.0, 9100.0, 8800.0]
    write_summary(
        "DEMO1",
        datetime.datetime(2020, 1, 1),
        days,
        {"FOPR": {"unit": "SM3/DAY", "data": fopr}},
        tmp_path,
    )
    assert (tmp_path / "DEMO1.SMSPEC").exists()
    assert (tmp_path / "DEMO1.UNSMRY").exists()

    out = extract_vectors(str(tmp_path / "DEMO1"), max_points=4000)
    assert out["TIME"] == [round6(d) for d in days]
    assert out["DATE"][0] == "2020-01-01" and out["DATE"][-1] == "2020-04-01"
    assert out["FOPR"]["unit"].upper().startswith("SM3")
    assert [round6(v) for v in out["FOPR"]["data"]] == [round6(v) for v in fopr]


def test_thin_minmax_preserves_peaks():
    vals = [0.0] + [1.0] * 200 + [100.0] + [1.0] * 200 + [0.0]
    idx = thin_minmax(vals, 20)
    assert len(idx) <= 20
    assert vals[idx[0]] == 0.0 and vals[idx[-1]] == 0.0
    assert 100.0 in [vals[i] for i in idx]


def test_extract_decimates_long_series(tmp_path):
    import random
    random.seed(7)
    n = 5000
    days = [float(i) for i in range(n)]
    data = [random.random() * 100 for _ in range(n)]
    write_summary("DEMO2", datetime.datetime(2020, 1, 1), days,
                  {"FOPR": {"unit": "SM3/DAY", "data": data}}, tmp_path)
    out = extract_vectors(str(tmp_path / "DEMO2"), max_points=100)
    assert len(out["TIME"]) <= 100
    assert len(out["FOPR"]["data"]) == len(out["TIME"])
