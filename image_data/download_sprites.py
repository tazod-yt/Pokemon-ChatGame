#!/usr/bin/env python3
"""
Download Gen 1 Pokemon entries, but save the Gen 6 sprite art for those Pokemon.

This matches the PokémonDB layout where:
- the main archive page gives us the Generation 1 roster
- each Pokemon page contains a Generation 9 section with the clean modern sprite

The script:
1. Scrapes the Generation 1 section from https://pokemondb.net/sprites
2. Visits each of those Pokemon's sprite pages
3. Grabs the Generation 6 normal sprite image
4. Saves it as PNG

If the source image is already PNG, it is saved directly.
If the source image is another format, Pillow is used to convert it to PNG.
"""

from __future__ import annotations

import argparse
import io
import re
import sys
import time
from pathlib import Path
from typing import Iterable, List, Optional, Tuple
from urllib.parse import urljoin

import requests

try:
    from PIL import Image
except ImportError:  # pragma: no cover - optional dependency
    Image = None


BASE_URL = "https://pokemondb.net/sprites"
DEFAULT_OUT_DIR = Path(__file__).resolve().parent / "images" / "pokemon"


def slug_from_href(href: str) -> str:
    return href.rstrip("/").rsplit("/", 1)[-1]


def extract_pokemon_name(html: str) -> str:
    match = re.search(r"<h1[^>]*>\s*([^<]+?)\s+sprites\s*</h1>", html, re.IGNORECASE)
    if not match:
        raise RuntimeError("Could not determine the Pokémon name from the sprite page.")
    return match.group(1).strip()


def filename_safe_name(name: str) -> str:
    cleaned = re.sub(r'[\\/:*?"<>|]', "", name)
    cleaned = re.sub(r"\s+", "_", cleaned)
    return cleaned


def fetch(session: requests.Session, url: str) -> str:
    response = session.get(url, timeout=30)
    response.raise_for_status()
    return response.text


def extract_species_urls_for_generation(html: str, generation: int) -> List[str]:
    next_generation = generation + 1
    match = re.search(
        rf"<h2[^>]*>\s*Generation {generation}\s*</h2>(.*?)(?:<h2[^>]*>\s*Generation {next_generation}\s*</h2>|</body>)",
        html,
        re.IGNORECASE | re.DOTALL,
    )
    if not match:
        raise RuntimeError(f"Could not find the Generation {generation} section on the sprites page.")

    section = match.group(1)
    hrefs = re.findall(r'href="(/sprites/[^"]+)"', section, flags=re.IGNORECASE)

    seen = set()
    ordered = []
    for href in hrefs:
        if href not in seen:
            seen.add(href)
            ordered.append(urljoin(BASE_URL, href))
    return ordered


def extract_generation_6_image_url(html: str) -> Optional[str]:
    patterns = [
        r'href="(https://img\.pokemondb\.net/sprites/x-y/normal/[^"]+)"',
        r'src="(https://img\.pokemondb\.net/sprites/x-y/normal/[^"]+)"',
        r'data-src="(https://img\.pokemondb\.net/sprites/x-y/normal/[^"]+)"',
    ]
    for pattern in patterns:
        match = re.search(pattern, html, re.IGNORECASE)
        if match:
            return match.group(1)
    return None


def save_as_png(image_bytes: bytes, dest_path: Path, content_type: str | None = None, source_url: str = "") -> None:
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    is_png = (
        (content_type and "png" in content_type.lower())
        or source_url.lower().endswith(".png")
        or image_bytes.startswith(b"\x89PNG\r\n\x1a\n")
    )

    if is_png:
        dest_path.write_bytes(image_bytes)
        return

    if Image is None:
        raise RuntimeError(
            f"{dest_path.name} is not a PNG and Pillow is not installed. "
            "Install Pillow with: pip install pillow"
        )

    with Image.open(io.BytesIO(image_bytes)) as img:
        img.save(dest_path, format="PNG")


def download_sprite(
    session: requests.Session,
    page_url: str,
    out_dir: Path,
    index: int,
    delay: float = 0.0,
) -> Tuple[str, Path]:
    page_html = fetch(session, page_url)
    pokemon_name = extract_pokemon_name(page_html)
    image_url = extract_generation_6_image_url(page_html)
    if not image_url:
        raise RuntimeError(f"Could not find the Generation 6 sprite on {page_url}")

    safe_name = filename_safe_name(pokemon_name)
    dest_path = out_dir / f"{index:03d}_{safe_name}.png"

    response = session.get(image_url, timeout=30)
    response.raise_for_status()
    save_as_png(response.content, dest_path, response.headers.get("content-type"), image_url)

    if delay > 0:
        time.sleep(delay)

    return pokemon_name, dest_path


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Download Gen 1 Pokemon list, but save the Generation 6 sprites as PNGs."
    )
    parser.add_argument(
        "--source-generation",
        type=int,
        default=1,
        choices=[1],
        help="Pokemon roster generation to scrape from the archive. Defaults to Gen 1.",
    )
    parser.add_argument(
        "--out",
        default=str(DEFAULT_OUT_DIR),
        help="Output directory for the downloaded PNG files.",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.15,
        help="Optional delay in seconds between downloads to be polite.",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (compatible; PokemonSpriteDownloader/1.0)",
            "Accept-Language": "en-US,en;q=0.9",
        }
    )

    print(f"Fetching sprite index: {BASE_URL}")
    index_html = fetch(session, BASE_URL)
    species_urls = extract_species_urls_for_generation(index_html, args.source_generation)
    species_urls = species_urls[:151]
    print(f"Found {len(species_urls)} Gen {args.source_generation} Pokemon.")

    failures = []
    for i, species_url in enumerate(species_urls, start=1):
        try:
            pokemon_name, dest = download_sprite(
                session,
                species_url,
                out_dir,
                index=i,
                delay=args.delay,
            )
            print(f"[{i:03d}/{len(species_urls):03d}] {pokemon_name} -> {dest}")
        except Exception as exc:
            slug = slug_from_href(species_url)
            failures.append((slug, str(exc)))
            print(f"[{i:03d}/{len(species_urls):03d}] {slug} FAILED: {exc}", file=sys.stderr)

    if failures:
        print("\nSome downloads failed:", file=sys.stderr)
        for slug, reason in failures:
            print(f"- {slug}: {reason}", file=sys.stderr)
        return 1

    print(f"\nDone. PNG files are in: {out_dir.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
