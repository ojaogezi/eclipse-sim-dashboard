import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_demo_builds_and_is_deterministic(tmp_path):
    r = subprocess.run([sys.executable, str(ROOT / "demo" / "make_demo.py"),
                        "--out", str(tmp_path), "--bundle", str(tmp_path / "bundle.json")],
                       capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stderr
    runs = sorted(tmp_path.glob("REAL-*"))
    assert len(runs) == 8
    for d in runs:
        smspecs = list(d.glob("*.SMSPEC"))
        assert len(smspecs) == 1
        assert (d / smspecs[0].with_suffix(".UNSMRY").name).exists()
        assert len(list(d.glob("*.RFT"))) == 1
    b = json.loads((tmp_path / "bundle.json").read_text())
    assert len(b["cases"]) == 8
    fopts = [c["vectors"]["FOPT"]["data"][-1] for c in b["cases"]]
    assert max(fopts) / min(fopts) > 1.3      # realizations genuinely differ
    poro_means = [c["params"]["PORO_MEAN"] for c in b["cases"]]
    assert max(poro_means) > min(poro_means)  # params captured
    rfts = [len(c["rft"]) for c in b["cases"]]
    assert all(n == 6 for n in rfts)          # 3 wells x 2 surveys
    # deterministic: second run identical except generated_utc
    r2 = subprocess.run([sys.executable, str(ROOT / "demo" / "make_demo.py"),
                         "--out", str(tmp_path / "again"),
                         "--bundle", str(tmp_path / "again" / "bundle.json")],
                        capture_output=True, text=True, timeout=300)
    assert r2.returncode == 0, r2.stderr
    def strip(s):
        b = json.loads(s)
        b.pop("generated_utc", None)
        b.pop("source_folder", None)
        for c in b["cases"]:
            c.pop("folder", None)
        return json.dumps(b, sort_keys=True)
    assert strip((tmp_path / "bundle.json").read_text()) == \
           strip((tmp_path / "again" / "bundle.json").read_text())
