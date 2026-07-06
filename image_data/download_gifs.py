#!/usr/bin/env python3
"""
Download animated GIF sprites from Pokemon Showdown and save them
matching the naming convention used in the images/pokemon folder.

Usage:
    python image_data/download_gifs.py --out image_data/gif --delay 0.15

The script reads files from image_data/images/pokemon and for each
file like `001_Bulbasaur.png` attempts to download
https://play.pokemonshowdown.com/sprites/ani/<slug>.gif using a few
slug transformations until one succeeds.
"""

from __future__ import annotations

import argparse
import io
import re
import sys
import time
import unicodedata
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

import requests

BASE_URL = "https://play.pokemonshowdown.com/sprites/ani/"
IMAGES_DIR = Path(__file__).resolve().parent / "images" / "pokemon"
DEFAULT_OUT_DIR = Path(__file__).resolve().parent / "gif"


def filename_safe_stem(path: Path) -> str:
    return path.stem


def normalize_text(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    s = s.encode("ascii", "ignore").decode("ascii")
    s = s.lower()
    return s


def generate_slug_candidates(species: str) -> List[str]:
    """Generate plausible Showdown sprite slugs from a species name.

    We try several variants to increase the chance of a match:
    - lowercase, spaces -> '-', punctuation removed
    - lowercase, spaces removed
    - lowercase, punctuation removed
    - replace gender symbols
    """
    s = normalize_text(species)
    # replace common gender symbols
    s = s.replace("♀", "f").replace("♂", "m")

    candidates = []

    # spaces to hyphen
    candidates.append(re.sub(r"[^a-z0-9\- ]+", "", s).strip().replace(" ", "-"))
    # spaces removed
    candidates.append(re.sub(r"[^a-z0-9 ]+", "", s).strip().replace(" ", ""))
    # remove punctuation entirely
    candidates.append(re.sub(r"[^a-z0-9]+", "", s).strip())

    # also try with dots replaced by nothing and hyphens kept
    candidates.append(s.replace('.', '').replace(' ', '-'))

    # dedupe while preserving order
    seen = set()
    out = []
    for c in candidates:
        if c and c not in seen:
            seen.add(c)
            out.append(c)
    return out


def fetch(session: requests.Session, url: str) -> bytes:
    response = session.get(url, timeout=30)
    response.raise_for_status()
    return response.content


def download_gif_for_file(
    session: requests.Session,
    source_path: Path,
    out_dir: Path,
    delay: float = 0.0,
) -> Tuple[str, Optional[Path]]:
    stem = filename_safe_stem(source_path)
    # preserve naming convention: keep the full stem including any numeric prefix
    dest_path = out_dir / f"{stem}.gif"

    # try to extract species name (part after the first underscore)
    if "_" in stem:
        _, species = stem.split("_", 1)
    else:
        species = stem

    candidates = generate_slug_candidates(species)

    for cand in candidates:
        url = f"{BASE_URL}{cand}.gif"
        try:
            resp = session.get(url, timeout=20)
        except Exception:
            resp = None
        if resp and resp.status_code == 200 and resp.content:
            # basic content-type check (not strict)
            ct = resp.headers.get("content-type", "")
            if "gif" in ct.lower() or resp.content[:6] in (b"GIF87a", b"GIF89a"):
                out_dir.mkdir(parents=True, exist_ok=True)
                dest_path.write_bytes(resp.content)
                if delay > 0:
                    time.sleep(delay)
                return cand, dest_path
    return "", None


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Download animated GIF sprites from Pokemon Showdown.")
    parser.add_argument("--out", default=str(DEFAULT_OUT_DIR), help="Output directory for GIF files.")
    parser.add_argument("--delay", type=float, default=0.12, help="Delay between downloads in seconds.")
    parser.add_argument("--source", default=str(IMAGES_DIR), help="Source images folder to read names from.")
    args = parser.parse_args(list(argv) if argv is not None else None)

    source_dir = Path(args.source)
    out_dir = Path(args.out)

    if not source_dir.exists():
        print(f"Source images folder does not exist: {source_dir}", file=sys.stderr)
        return 2

    files = sorted([p for p in source_dir.iterdir() if p.is_file() and p.suffix.lower() in ('.png', '.jpg', '.jpeg')])
    if not files:
        print(f"No image files found in: {source_dir}", file=sys.stderr)
        return 0

    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (compatible; PokemonGifDownloader/1.0)",
        "Accept-Language": "en-US,en;q=0.9",
    })

    failures = []
    successes = []
    for i, p in enumerate(files, start=1):
        try:
            cand, dest = download_gif_for_file(session, p, out_dir, delay=args.delay)
            if dest:
                print(f"[{i:03d}/{len(files):03d}] {p.name} -> {dest.name} (slug: {cand})")
                successes.append((p.name, dest.name))
            else:
                print(f"[{i:03d}/{len(files):03d}] {p.name} -> NOT FOUND", file=sys.stderr)
                failures.append((p.name, "not-found"))
        except Exception as exc:
            print(f"[{i:03d}/{len(files):03d}] {p.name} FAILED: {exc}", file=sys.stderr)
            failures.append((p.name, str(exc)))

    if failures:
        print("\nSome downloads failed:", file=sys.stderr)
        for name, reason in failures:
            print(f"- {name}: {reason}", file=sys.stderr)
        return 1

    print(f"\nDone. GIF files are in: {out_dir.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
