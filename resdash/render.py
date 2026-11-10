"""Assemble the self-contained dashboard.html."""
import json
from pathlib import Path

import plotly

ASSETS = Path(__file__).parent / "assets"
PLOTLY_JS = Path(plotly.__file__).parent / "package_data" / "plotly.min.js"


def render_html(bundle: dict, out_path: str) -> str:
    html = (ASSETS / "template.html").read_text(encoding="utf-8")
    payload = json.dumps(bundle, separators=(",", ":")).replace("</", "<\\/")
    html = (html
            .replace("/*__PLOTLY__*/", PLOTLY_JS.read_text(encoding="utf-8"))
            .replace("/*__APP_CSS__*/", (ASSETS / "dashboard.css").read_text(encoding="utf-8"))
            .replace("/*__BUNDLE__*/", payload)
            .replace("/*__APP_JS__*/", (ASSETS / "dashboard.js").read_text(encoding="utf-8")))
    Path(out_path).write_text(html, encoding="utf-8")
    return out_path
