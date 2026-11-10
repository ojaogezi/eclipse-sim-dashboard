import datetime
import json

from resdash.bundle import build_bundle, dump_bundle, load_bundle, validate_bundle
from resdash.demo_io import write_summary


def _make_case(folder, name, values):
    days = [0.0, 30.0, 60.0]
    write_summary(name, datetime.datetime(2020, 1, 1), days,
                  {"FOPR": {"unit": "SM3/DAY", "data": values},
                   "FOPT": {"unit": "SM3", "data": [0, values[1] * 30, values[1] * 60]}},
                  folder)


def test_build_and_validate(tmp_path):
    _make_case(tmp_path / "REAL-01", "CASE_V1", [0, 1000.0, 900.0])
    _make_case(tmp_path / "REAL-02", "CASE_V2", [0, 1500.0, 1300.0])

    b = build_bundle(str(tmp_path))
    errs = validate_bundle(b)
    assert errs == []
    assert b["schema"] == 1
    assert len(b["cases"]) == 2
    names = {c["name"] for c in b["cases"]}
    assert names == {"CASE_V1", "CASE_V2"}
    c1 = b["cases"][0]
    assert c1["files"] == {"summary": True, "rft": False, "prt": False, "data": False}
    assert "FOPR" in c1["vectors"] and c1["vectors"]["FOPR"]["unit"] == "SM3/DAY"
    assert c1["rft"] == [] and c1["qc"] == {} and c1["params"] == {}
    assert b["source_folder"] == str(tmp_path)

    out = tmp_path / "bundle.json"
    dump_bundle(b, str(out))
    assert load_bundle(str(out)) == json.loads(json.dumps(b))


def test_validate_catches_errors():
    assert validate_bundle({"schema": 2}) != []          # wrong schema
    assert validate_bundle({"schema": 1, "cases": []}) == []
    bad = {"schema": 1, "cases": [{"name": "A"}, {"name": "A"}]}
    assert any("unique" in e for e in validate_bundle(bad))
