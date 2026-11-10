import datetime
import json
import re

from resdash.bundle import build_bundle
from resdash.demo_io import write_summary
from resdash.render import PLOTLY_JS, render_html


def _demo_bundle(tmp_path):
    days = [float(d) for d in range(0, 366, 30)]
    fopr = [0, 9000, 8800, 8600, 8400, 8200, 8000, 7800, 7600, 7400, 7200, 7000, 6800]
    for i, mult in enumerate([1.0, 1.2]):
        write_summary(f"CASE_V{i+1}", datetime.datetime(2020, 1, 1), days,
                      {"FOPR": {"unit": "SM3/DAY", "data": [v * mult for v in fopr]}},
                      tmp_path / f"REAL-0{i+1}")
    return build_bundle(str(tmp_path))


def test_render_selfcontained(tmp_path):
    b = _demo_bundle(tmp_path)
    out = tmp_path / "dash.html"
    render_html(b, str(out))
    html = out.read_text(encoding="utf-8")
    assert "Plotly.newPlot" in html
    assert "bundle-data" in html
    json.loads(re.search(r'<script id="bundle-data" type="application/json">(.*?)</script>',
                         html, re.S).group(1))
    assert "generated_utc" in html
    # our markup must reference no external resources (plotly.min.js itself
    # contains internal https strings; strip it before checking)
    ours = html.replace(PLOTLY_JS.read_text(encoding="utf-8"), "")
    assert "<script src=" not in ours and "<link " not in ours
    assert not re.search(r'(src|href)\s*=\s*["\']https?://', ours)
    assert out.stat().st_size > 1_000_000  # plotly embedded
