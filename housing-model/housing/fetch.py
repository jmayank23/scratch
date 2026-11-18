"""Download the raw files.

Rules:
  - A file that is already on disk is not downloaded again (use --force to refresh).
  - Zillow files go into a folder named for the download date, so that old revisions stay.
  - A missing year (HTTP 404) is skipped and logged. Other errors are retried 3 times.
  - Every download is written to data/raw/manifest.jsonl (URL, size, SHA-256, time).
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import time
from pathlib import Path

import requests

from . import config as C


class Fetcher:
    def __init__(self, data_dir: Path, force: bool = False):
        self.raw = Path(data_dir) / "raw"
        self.raw.mkdir(parents=True, exist_ok=True)
        self.force = force
        self.session = requests.Session()
        self.session.headers["User-Agent"] = C.USER_AGENT
        self.manifest = self.raw / "manifest.jsonl"

    def _log(self, **rec):
        rec["at"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
        with self.manifest.open("a") as f:
            f.write(json.dumps(rec) + "\n")

    def get(self, url: str, dest: Path, params: dict | None = None) -> Path | None:
        """Download url to dest. Return dest, or None if the server says 400 or 404."""
        if dest.exists() and dest.stat().st_size > 0 and not self.force:
            return dest
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_suffix(dest.suffix + ".part")
        for attempt in range(1, 4):
            try:
                with self.session.get(url, params=params, stream=True, timeout=120) as r:
                    if r.status_code in (400, 404):
                        # 404: that year is not published. 400: the API refused the query.
                        self._log(url=url, status=r.status_code)
                        print(f"  skip ({r.status_code}): {url}")
                        return None
                    r.raise_for_status()
                    h = hashlib.sha256()
                    with tmp.open("wb") as f:
                        for chunk in r.iter_content(1 << 20):
                            f.write(chunk)
                            h.update(chunk)
                tmp.replace(dest)
                self._log(url=url, path=str(dest.relative_to(self.raw)), status=200,
                          bytes=dest.stat().st_size, sha256=h.hexdigest())
                print(f"  ok: {dest.relative_to(self.raw)} ({dest.stat().st_size/1e6:.1f} MB)")
                return dest
            except requests.RequestException as e:
                print(f"  try {attempt}/3 failed: {url}: {e}")
                time.sleep(5 * attempt)
        self._log(url=url, status="failed")
        raise RuntimeError(f"download failed after 3 tries: {url}")


# ---------------------------------------------------------------- per source

def fetch_zillow(f: Fetcher):
    snap = dt.date.today().isoformat()
    for name, url in C.ZILLOW.items():
        f.get(url, f.raw / "zillow" / snap / f"{name}.csv")


def fetch_fred(f: Fetcher):
    for s in C.FRED_SERIES:
        f.get(C.FRED_URL.format(series=s), f.raw / "fred" / f"{s}.csv")


def _acs_params(year: int, geo_in: str | None) -> dict:
    p = {"get": "NAME," + ",".join(C.ACS_VARS), "for": "zip code tabulation area:*"}
    if geo_in:
        p["in"] = geo_in
    key = os.environ.get("CENSUS_API_KEY")
    if key:
        p["key"] = key
    return p


def fetch_acs(f: Fetcher):
    """National ZCTA query first. If the API refuses it (older vintages), query per state."""
    for y in C.ACS_YEARS:
        url = C.ACS_URL.format(year=y)
        dest = f.raw / "acs" / f"acs5_{y}_national.json"
        if dest.exists() and not f.force:
            continue
        try:
            if f.get(url, dest, params=_acs_params(y, None)) is not None:
                json.loads(dest.read_text())  # must be valid JSON
                continue
        except (RuntimeError, ValueError):
            dest.unlink(missing_ok=True)
        print(f"  ACS {y}: national query failed, trying per state")
        for st in C.STATE_FIPS:
            try:
                f.get(url, f.raw / "acs" / f"acs5_{y}_st{st}.json",
                      params=_acs_params(y, f"state:{st}"))
            except RuntimeError as e:
                print(f"  ACS {y} state {st}: {e}")


def fetch_irs(f: Fetcher):
    for y in C.IRS_YEARS:
        f.get(C.IRS_URL.format(yy=f"{y % 100:02d}"), f.raw / "irs" / f"{y}zpallagi.csv")


def fetch_bps(f: Fetcher):
    for y in C.BPS_YEARS:
        f.get(C.BPS_URL.format(year=y), f.raw / "bps" / f"co{y}a.txt")


def fetch_qcew(f: Fetcher):
    for y in C.QCEW_YEARS:
        f.get(C.QCEW_URL.format(year=y), f.raw / "qcew" / f"{y}_county_total.csv")


def fetch_crosswalk(f: Fetcher):
    f.get(C.ZCTA_COUNTY_URL, f.raw / "crosswalk" / "zcta_county_2020.txt")


SOURCES = {
    "zillow": fetch_zillow,
    "fred": fetch_fred,
    "acs": fetch_acs,
    "irs": fetch_irs,
    "bps": fetch_bps,
    "qcew": fetch_qcew,
    "crosswalk": fetch_crosswalk,
}


def fetch_all(data_dir: Path, only: list[str] | None = None, force: bool = False):
    f = Fetcher(data_dir, force=force)
    for name, fn in SOURCES.items():
        if only and name not in only:
            continue
        print(f"[fetch] {name}")
        try:
            fn(f)
        except RuntimeError as e:
            # One failed source must not stop the others. The build marks it as missing.
            print(f"  ERROR {name}: {e}")
