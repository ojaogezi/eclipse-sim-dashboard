#!/usr/bin/env python3
"""Build a self-contained dashboard.html from a folder of ECLIPSE runs."""
import argparse
import sys
import warnings

warnings.filterwarnings("ignore", category=DeprecationWarning)

from resdash.bundle import build_bundle, load_bundle, validate_bundle  # noqa: E402
from resdash.render import render_html  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("runs_folder", nargs="?", help="folder containing ECLIPSE runs")
    ap.add_argument("-o", "--output", default="dashboard.html")
    ap.add_argument("--bundle-json", help="load a previously built bundle instead of extracting")
    ap.add_argument("--max-points", type=int, default=4000)
    ap.add_argument("--realization-regex", default=None)
    args = ap.parse_args(argv)

    if args.bundle_json:
        bundle = load_bundle(args.bundle_json)
    elif args.runs_folder:
        bundle = build_bundle(args.runs_folder, realization_regex=args.realization_regex,
                              max_points=args.max_points)
    else:
        ap.error("provide RUNS_FOLDER or --bundle-json")

    errs = validate_bundle(bundle)
    if errs:
        for e in errs:
            print(f"bundle error: {e}", file=sys.stderr)
        return 2
    render_html(bundle, args.output)
    print(f"wrote {args.output} ({len(bundle['cases'])} cases)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
