#!/usr/bin/env python3
# scrapper.py
import argparse
import csv
import json
import re
import time
import os
from typing import Any, Dict, List, Optional, Tuple, Set
import requests
from bs4 import BeautifulSoup
from pathlib import Path

BASE = "https://www.dr.dk"
UA = {"User-Agent": "DR-Playlist-Scraper/1.0 (contact: ahma@itu.dk)"}

# ---------- logging ----------


def ts() -> str: return time.strftime("%H:%M:%S")
def log(msg: str) -> None: print(f"[{ts()}] {msg}", flush=True)

# ---------- HTTP ----------


def http_get(url: str, timeout: int = 25) -> requests.Response:
    log(f"GET {url}")
    r = requests.get(url, headers=UA, timeout=timeout)
    log(f"→ {r.status_code} ({len(r.content)} bytes)")
    r.raise_for_status()
    return r


def http_get_json(url: str, timeout: int = 25) -> Dict[str, Any]:
    r = http_get(url, timeout=timeout)
    return r.json()

# ---------- HTML/JSON helpers ----------


def extract_build_id(html: str) -> Optional[str]:
    # First we are getting build id which is needed to construct episode JSON URLs
    m = re.search(
        r'__NEXT_DATA__"\s*type="application/json">(.+?)</script>', html, re.DOTALL)
    if m:
        try:
            data = json.loads(m.group(1))
            bid = data.get("buildId")
            if isinstance(bid, str) and bid.strip():
                return bid
        except Exception:
            pass
    # Fallback: static path reference
    m2 = re.search(r'/_next/static/([A-Za-z0-9\-_]+)/_buildManifest\.js', html)
    return m2.group(1) if m2 else None


def find_episode_slugs_from_html(html: str, channel: str, date: str) -> List[str]:
    """Find anchors like /lyd/playlister/{channel}/{date}/{slug} and return unique slugs."""
    soup = BeautifulSoup(html, "html.parser")
    prefix = f"/lyd/playlister/{channel}/{date}/"
    slugs: List[str] = []
    seen: Set[str] = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith(prefix):
            slug = href[len(prefix):].strip("/")
            if slug and slug not in seen:
                seen.add(slug)
                slugs.append(slug)
    return slugs


def page_props(obj: Dict[str, Any]) -> Dict[str, Any]:
    return obj.get("pageProps") or obj.get("props", {}).get("pageProps") or {}


def roles_to_artists(roles: Any) -> Tuple[str, str, str]:
    """Return (artist_names, artist_names_with_roles, artist_urns)."""
    if not isinstance(roles, list):
        return "", "", ""
    names, pairs, urns = [], [], []
    for r in roles:
        name = r.get("name") or r.get("title")
        role = r.get("role")
        urn = r.get("artistUrn") or r.get("urn") or r.get("id")
        if name:
            names.append(name)
            pairs.append(f"{name} ({role})" if role else name)
        if urn:
            urns.append(urn)
    return ", ".join(names), ", ".join(pairs), ", ".join(urns)


def get_program_description(ep_meta: Dict[str, Any], pp: Optional[Dict[str, Any]] = None) -> str:
    """Prefer description on episode; fallback to program/programme object if present."""
    def pick(d: Dict[str, Any]) -> Optional[str]:
        for k in ["description", "shortDescription", "teaser", "synopsis", "summary"]:
            v = d.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()
        return None
    if isinstance(ep_meta, dict):
        v = pick(ep_meta)
        if v:
            return v
    if isinstance(pp, dict):
        for key in ["program", "programme"]:
            obj = pp.get(key)
            if isinstance(obj, dict):
                v = pick(obj)
                if v:
                    return v
    return ""


def episode_tracks_to_rows(
    date: str,
    channel: str,
    ep_meta: Dict[str, Any],
    playlist_points: List[Dict[str, Any]],
    programme_description: str,
    source_url: str
) -> List[Dict[str, Any]]:
    rows = []
    for t in (playlist_points or []):
        names, pairs, urns = roles_to_artists(t.get("roles"))
        rows.append({
            "date": date,
            "channel": channel,
            "programme_title": ep_meta.get("title"),
            "programme_slug": ep_meta.get("slug"),
            "programme_production_number": ep_meta.get("productionNumber"),
            "programme_start_time": ep_meta.get("startTime"),
            "programme_description": programme_description,
            "track_played_time": t.get("playedTime"),
            "track_title": t.get("title"),
            "track_duration_ms": t.get("durationMilliseconds"),
            "track_is_classical": t.get("classical"),
            "track_description": t.get("description"),
            "track_urn": t.get("trackUrn"),
            "artist_names": names,
            "artist_names_with_roles": pairs,
            "artist_urns": urns,
            "source_json": source_url,
        })
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--channel", required=True, help="e.g. p3")
    ap.add_argument("--date", required=True, help="YYYY-MM-DD")
    ap.add_argument(
        "--out", help="Output CSV path; default: dr_{channel}_{date}.csv")
    ap.add_argument("--sleep", type=float, default=0.5,
                    help="Delay between episode requests")
    # we might need this delay not to overload the server or get blocked
    args = ap.parse_args()

    # derive page URL from channel+date
    page_url = f"{BASE}/lyd/playlister/{args.channel}/{args.date}/"

    # default to data/<channel>_<date>.csv, unless --out is provided
    if args.out:
        out_path = Path(args.out)
    else:
        out_path = Path("data") / f"dr_{args.channel}_{args.date}.csv"

    log(f"Scraping {page_url}")
    # First we get the main page HTML
    html = http_get(page_url).text

    # Then we are getting build id which is needed to construct episode JSON URLs
    build_id = extract_build_id(html)
    log(f"Detected buildId: {build_id!r}")
    if not build_id:
        raise RuntimeError(
            "Could not detect Next.js buildId from HTML. Site structure may have changed.")

    # Later we will need episode slugs from the main page HTML so we can get episode JSONs
    slugs = find_episode_slugs_from_html(html, args.channel, args.date)
    log(f"Found {len(slugs)} episode slugs")
    for i, s in enumerate(slugs[:12], 1):
        log(f"  [{i}] {s}")

    all_rows: List[Dict[str, Any]] = []
    for i, slug in enumerate(slugs, 1):
        ep_url = f"{BASE}/lyd/_next/data/{build_id}/da/playlister/{args.channel}/{args.date}/{slug}.json"
        try:
            ep_json = http_get_json(ep_url)
            pp = page_props(ep_json)
            ep_meta = pp.get("episode") or {}
            playlist_points = pp.get(
                "playlistIndexPoints") or []  # list of tracks
            programme_description = get_program_description(ep_meta, pp)
            log(f"[{i}/{len(slugs)}] {ep_meta.get('title')!r} start={ep_meta.get('startTime')} tracks={len(playlist_points)}")
            rows = episode_tracks_to_rows(args.date, args.channel, ep_meta, playlist_points,
                                          programme_description, ep_url)
            all_rows.extend(rows)
        except Exception as e:
            log(f"ERROR on {ep_url}: {e}")
        time.sleep(args.sleep)

    # write CSV (Episode JSONs only)
    headers = [
        "date", "channel", "programme_title", "programme_slug", "programme_production_number",
        "programme_start_time", "programme_description",
        "track_played_time", "track_title", "track_duration_ms", "track_is_classical",
        "track_description", "track_urn", "artist_names", "artist_names_with_roles", "artist_urns", "source_json"
    ]

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=headers)
        w.writeheader()
        w.writerows(all_rows)

    log(f"✅ Saved {len(all_rows)} rows → {out_path}")


if __name__ == "__main__":
    main()
