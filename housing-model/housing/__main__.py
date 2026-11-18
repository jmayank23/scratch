"""Command line.

  python -m housing fetch [--only zillow fred ...] [--force]
  python -m housing normalize
  python -m housing build
  python -m housing check
  python -m housing baseline
  python -m housing all          # all five steps in order
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import config as C


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m housing")
    ap.add_argument("--data-dir", type=Path, default=C.DATA_DIR,
                    help="where raw, interim and out folders go (default ./data)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fetch")
    f.add_argument("--only", nargs="*", help="sources: zillow fred acs irs bps qcew crosswalk")
    f.add_argument("--force", action="store_true", help="download again even if on disk")
    for name in ("normalize", "build", "check", "baseline"):
        sub.add_parser(name)
    a = sub.add_parser("all")
    a.add_argument("--force", action="store_true")
    args = ap.parse_args(argv)
    d = args.data_dir

    if args.cmd in ("fetch", "all"):
        from .fetch import fetch_all
        fetch_all(d, only=getattr(args, "only", None), force=args.force)
    if args.cmd in ("normalize", "all"):
        from .normalize import normalize_all
        normalize_all(d)
    if args.cmd in ("build", "all"):
        from .build import build
        build(d)
    if args.cmd in ("check", "all"):
        from .checks import run_checks
        fails = run_checks(d)
        if fails:
            print("[check] FAILED:\n  " + "\n  ".join(fails))
            return 1
        print("[check] all hard checks passed")
    if args.cmd in ("baseline", "all"):
        from .baseline import run_baselines
        run_baselines(d)
    return 0


if __name__ == "__main__":
    sys.exit(main())
