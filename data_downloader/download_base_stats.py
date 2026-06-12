#!/usr/bin/env python3
"""
Download base stats for the Generation 1 roster from PokemonDB and save them as JSON.

The script:
1. Scrapes the Generation 1 section from https://pokemondb.net/sprites
2. Visits each Pokemon's Pokédex page
3. Extracts the base stats block
4. Writes a JSON file with one entry per Pokemon
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List, Optional
from urllib.parse import urljoin

import requests


BASE_URL = "https://pokemondb.net/sprites"
DEFAULT_OUT_FILE = Path(__file__).resolve().parent / "pokemon_base_stats.json"


def fetch(session: requests.Session, url: str) -> str:
    response = session.get(url, timeout=30)
    response.raise_for_status()
    return response.text


def extract_species_urls_for_generation(html_text: str, generation: int) -> List[str]:
    next_generation = generation + 1
    match = re.search(
        rf"<h2[^>]*>\s*Generation {generation}\s*</h2>(.*?)(?:<h2[^>]*>\s*Generation {next_generation}\s*</h2>|</body>)",
        html_text,
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


def slug_from_href(href: str) -> str:
    return href.rstrip("/").rsplit("/", 1)[-1]


def filename_safe_name(name: str) -> str:
    cleaned = re.sub(r'[\\/:*?"<>|]', "", name)
    cleaned = re.sub(r"\s+", "_", cleaned)
    return cleaned


def pokemon_name_from_slug(slug: str) -> str:
    special_cases = {
        "nidoran-f": "Nidoran♀",
        "nidoran-m": "Nidoran♂",
        "mr-mime": "Mr. Mime",
        "farfetchd": "Farfetch'd",
        "type-null": "Type: Null",
    }
    if slug in special_cases:
        return special_cases[slug]

    parts = slug.split("-")
    return " ".join(part.capitalize() for part in parts)


def text_from_html(html_text: str) -> str:
    text = re.sub(r"<script\b.*?</script>", " ", html_text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<style\b.*?</style>", " ", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = text.replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_pokemon_name(html_text: str) -> str:
    match = re.search(r"<h1[^>]*>\s*([^<]+?)\s+Pokédex", html_text, re.IGNORECASE)
    if match:
        return html.unescape(match.group(1).strip())

    match = re.search(r"<h1[^>]*>\s*([^<]+?)\s+Pokedex", html_text, re.IGNORECASE)
    if match:
        return html.unescape(match.group(1).strip())

    raise RuntimeError("Could not determine the Pokémon name from the Pokédex page.")


def extract_base_stats(html_text: str) -> Dict[str, int]:
    text = text_from_html(html_text)

    match = re.search(
        r"Base stats\s+HP\s+(\d+)\s+\d+\s+\d+\s+Attack\s+(\d+)\s+\d+\s+\d+\s+"
        r"Defense\s+(\d+)\s+\d+\s+\d+\s+Sp\. Atk\s+(\d+)\s+\d+\s+\d+\s+"
        r"Sp\. Def\s+(\d+)\s+\d+\s+\d+\s+Speed\s+(\d+)\s+\d+\s+\d+\s+Total\s+(\d+)",
        text,
        re.IGNORECASE,
    )
    if not match:
        raise RuntimeError("Could not parse base stats from the Pokédex page.")

    hp, attack, defense, sp_atk, sp_def, speed, total = map(int, match.groups())
    return {
        "hp": hp,
        "attack": attack,
        "defense": defense,
        "sp_atk": sp_atk,
        "sp_def": sp_def,
        "speed": speed,
        "total": total,
    }


def extract_catch_rate(html_text: str) -> Dict[str, object]:
    text = text_from_html(html_text)
    match = re.search(
        r"Catch rate\s+(\d+)\s*(?:\(([^)]+)\))?",
        text,
        re.IGNORECASE,
    )
    if not match:
        raise RuntimeError("Could not parse catch rate from the Pokédex page.")

    catch_rate = int(match.group(1))
    return {"value": catch_rate}


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Download Gen 1 base stats from PokemonDB as JSON.")
    parser.add_argument(
        "--out",
        default=str(DEFAULT_OUT_FILE),
        help="Output JSON file path.",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.15,
        help="Optional delay in seconds between downloads to be polite.",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    out_file = Path(args.out)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (compatible; PokemonStatsDownloader/1.0)",
            "Accept-Language": "en-US,en;q=0.9",
        }
    )

    print(f"Fetching sprite index: {BASE_URL}")
    index_html = fetch(session, BASE_URL)
    species_urls = extract_species_urls_for_generation(index_html, 1)[:151]
    print(f"Found {len(species_urls)} Gen 1 Pokemon.")

    results: Dict[str, Dict[str, object]] = {}
    failures = []

    for i, species_url in enumerate(species_urls, start=1):
        slug = slug_from_href(species_url)
        pokedex_url = species_url.replace("/sprites/", "/pokedex/")

        try:
            page_html = fetch(session, pokedex_url)
            pokemon_name = pokemon_name_from_slug(slug)
            base_stats = extract_base_stats(page_html)
            catch_rate = extract_catch_rate(page_html)
            entry_key = f"{i:03d}_{filename_safe_name(pokemon_name)}"
            results[entry_key] = {
                "dex_number": i,
                "name": pokemon_name,
                "slug": slug,
                "url": pokedex_url,
                "image_file": f"{entry_key}.png",
                "base_stats": base_stats,
                "catch_rate": catch_rate,
            }
            print(f"[{i:03d}/{len(species_urls):03d}] {pokemon_name}")
        except Exception as exc:
            failures.append((slug, str(exc)))
            print(f"[{i:03d}/{len(species_urls):03d}] {slug} FAILED: {exc}", file=sys.stderr)

        if args.delay > 0:
            time.sleep(args.delay)

    payload = {
        "source": "https://pokemondb.net/pokedex",
        "generation": 1,
        "count": len(results),
        "pokemon": results,
    }

    out_file.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nWrote JSON to: {out_file.resolve()}")

    if failures:
        print("\nSome downloads failed:", file=sys.stderr)
        for slug, reason in failures:
            print(f"- {slug}: {reason}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
