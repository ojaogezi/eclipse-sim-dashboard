import datetime
import subprocess
import sys

import plotly.graph_objects as go

from resdash.bundle import build_bundle
from resdash.demo_io import write_summary


def _bundle(tmp_path):
    days = [0.0, 30.0, 60.0]
    for i, m in enumerate([1.0, 1.3]):
        write_summary(f"C{i}_V{i}", datetime.datetime(2020, 1, 1), days,
                      {"FOPR": {"unit": "SM3/DAY", "data": [0, 1000 * m, 900 * m]}},
                      tmp_path / f"R{i}")
    return build_bundle(str(tmp_path))


def test_figures_build(tmp_path, monkeypatch):
    monkeypatch.setenv("DASH_TEST", "1")
    import app
    b = _bundle(tmp_path)
    assert isinstance(app.fig_overview(b), go.Figure)
    fig = app.fig_timeseries(b, "FOPR", [b["cases"][0]["name"]], logy=False)
    assert len(fig.data) == 1
    assert isinstance(app.fig_parameters(b, "FOPR"), go.Figure)
    assert isinstance(app.fig_qc(b), go.Figure)


def test_syntax_check():
    r = subprocess.run([sys.executable, "-m", "py_compile", "app.py"], capture_output=True)
    assert r.returncode == 0
