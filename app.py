#!/usr/bin/env python3
"""Streamlit frontend for the ECLIPSE ensemble dashboard (same bundle as the static HTML)."""
import json
import os
import warnings
from pathlib import Path

warnings.filterwarnings("ignore", category=DeprecationWarning)

import plotly.graph_objects as go
import streamlit as st

from resdash.bundle import build_bundle, load_bundle, validate_bundle

TEMPLATE = dict(paper_bgcolor="#0e1117", plot_bgcolor="#262730", font=dict(color="#fafafa"))


def load_bundle_file(path):  # thin wrapper kept for import parity
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _last(c, key):
    v = c["vectors"].get(key)
    return None if not v else next((x for x in reversed(v["data"]) if x is not None), None)


def fig_overview(b):
    fig = go.Figure()
    names = [c["name"] for c in b["cases"]]
    fig.add_bar(x=names, y=[_last(c, "FOPT") for c in b["cases"]], name="FOPT")
    fig.add_bar(x=names, y=[_last(c, "FWPT") for c in b["cases"]], name="FWPT")
    fig.update_layout(barmode="group", **TEMPLATE)
    return fig


def fig_timeseries(b, key, case_names, logy=False):
    fig = go.Figure()
    for c in b["cases"]:
        if c["name"] not in case_names or key not in c["vectors"]:
            continue
        fig.add_scatter(x=c["vectors"]["TIME"], y=c["vectors"][key]["data"],
                        mode="lines", name=c["name"])
    fig.update_layout(yaxis_type="log" if logy else "linear", **TEMPLATE)
    return fig


def fig_parameters(b, endpoint):
    import numpy as np
    ys = np.array([_last(c, endpoint) or 0.0 for c in b["cases"]], dtype=float)
    keys = sorted({k for c in b["cases"] for k, v in c.get("params", {}).items()
                   if isinstance(v, (int, float))})
    rhos = []
    for k in keys:
        xs = np.array([c.get("params", {}).get(k, np.nan) for c in b["cases"]], dtype=float)
        if np.isfinite(xs).all() and len(set(xs)) > 1:
            rx = xs.argsort().argsort().astype(float)
            ry = ys.argsort().argsort().astype(float)
            rhos.append((k, float(np.corrcoef(rx, ry)[0, 1])))
    rhos.sort(key=lambda t: abs(t[1]), reverse=True)
    fig = go.Figure(go.Bar(x=[r for _, r in rhos], y=[k for k, _ in rhos], orientation="h",
                           marker_color=["#4fc3f7" if r >= 0 else "#ef9a9a" for _, r in rhos]))
    fig.update_layout(title=f"Spearman rho vs {endpoint}", **TEMPLATE)
    return fig


def fig_rft(b, well, date, case_names):
    fig = go.Figure()
    for c in b["cases"]:
        if c["name"] not in case_names:
            continue
        for s in c.get("rft", []):
            if s["well"] == well and s["date"] == date:
                fig.add_scatter(x=s["pressure"], y=s["depth"], mode="lines+markers",
                                name=c["name"])
    fig.update_layout(yaxis_autorange="reversed", **TEMPLATE)
    return fig


def fig_qc(b):
    fig = go.Figure(go.Bar(x=[c["name"] for c in b["cases"]],
                           y=[(c.get("qc") or {}).get("mb_error_max") for c in b["cases"]],
                           marker_color="#ef9a9a"))
    fig.update_layout(yaxis_title="MB error max (%)", **TEMPLATE)
    return fig


def main():
    st.set_page_config(page_title="ECLIPSE Ensemble Dashboard", layout="wide", page_icon="🛢️")
    st.title("🛢️ ECLIPSE Ensemble Dashboard")
    src = st.sidebar.text_input("Bundle JSON path", value="demo/bundle.json")
    folder = st.sidebar.text_input("…or runs folder to extract now", value="")
    if folder and Path(folder).exists():
        b = build_bundle(folder)
    elif Path(src).exists():
        b = load_bundle(src)
    else:
        st.info("Point the sidebar at a bundle.json or a runs folder. "
                "Build one with: python build_dashboard.py <runs_folder>")
        return
    errs = validate_bundle(b)
    if errs:
        st.error("; ".join(errs))
        return
    st.caption(f"{len(b['cases'])} cases · generated {b['generated_utc']}")
    keys = sorted(k for c in b["cases"][:1] for k in c["vectors"] if k not in ("TIME", "DATE"))
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["Overview", "Time Series", "Parameters", "RFT", "QC"])
    with tab1:
        st.plotly_chart(fig_overview(b), use_container_width=True)
        st.dataframe([{"case": c["name"], "realization": c["realization"],
                       "FOPT": _last(c, "FOPT"), "FWPT": _last(c, "FWPT"),
                       "FPR": _last(c, "FPR")} for c in b["cases"]], hide_index=True)
    with tab2:
        key = st.selectbox("Vector", keys)
        names = st.multiselect("Cases", [c["name"] for c in b["cases"]],
                               default=[c["name"] for c in b["cases"][:2]])
        st.plotly_chart(fig_timeseries(b, key, names, st.checkbox("log Y")),
                        use_container_width=True)
    with tab3:
        endpoint = st.selectbox("End-point", ["FOPT", "FGPT", "FWPT", "FWIT", "FGIT"])
        st.plotly_chart(fig_parameters(b, endpoint), use_container_width=True)
        st.dataframe([{"case": c["name"], **c.get("params", {})} for c in b["cases"]],
                     hide_index=True)
    with tab4:
        wells = sorted({s["well"] for c in b["cases"] for s in c.get("rft", [])})
        if wells:
            w = st.selectbox("Well", wells)
            dates = sorted({s["date"] for c in b["cases"] for s in c.get("rft", [])
                            if s["well"] == w})
            d = st.selectbox("Date", dates)
            st.plotly_chart(fig_rft(b, w, d, [c["name"] for c in b["cases"]]),
                            use_container_width=True)
        else:
            st.info("No RFT data in this bundle.")
    with tab5:
        st.plotly_chart(fig_qc(b), use_container_width=True)
        st.dataframe([{"case": c["name"], **(c.get("qc") or {})} for c in b["cases"]],
                     hide_index=True)


if not os.environ.get("DASH_TEST"):
    main()  # streamlit executes the script top-to-bottom; tests set DASH_TEST=1
