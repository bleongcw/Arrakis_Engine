#!/usr/bin/env python3
# ArrakisEngine — Chess Coaching AI
# Copyright (C) 2026 Bernard Leong
# Licensed under AGPL-3.0. See LICENSE file.
"""Build the openings + traps data files from the Lichess chess-openings TSV source.

Lichess publishes a CC0 (public domain) database of ~3,209 named openings at:
    https://github.com/lichess-org/chess-openings

This script:
1. Downloads a.tsv, b.tsv, c.tsv, d.tsv, e.tsv (one per ECO volume).
2. Parses each into structured entries.
3. Writes two output files:
   - frontend/public/data/openings.json  (full opening book, replaces existing 440-entry file)
   - frontend/public/data/traps.json     (filtered: named traps, gambits, attacks, mates)

Usage:
    python scripts/build_traps.py            # download + write
    python scripts/build_traps.py --dry-run  # download + report counts only
    python scripts/build_traps.py --offline  # use cached TSVs in scripts/.lichess_cache/

The output files are vendored (committed to the repo) so runtime has no
network dependency. Re-run this script if Lichess updates the upstream
database (typically a few times per year).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path

LICHESS_BASE = "https://raw.githubusercontent.com/lichess-org/chess-openings/master"
VOLUMES = ["a", "b", "c", "d", "e"]

REPO_ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = REPO_ROOT / "scripts" / ".lichess_cache"
OPENINGS_OUT = REPO_ROOT / "frontend" / "public" / "data" / "openings.json"
TRAPS_OUT = REPO_ROOT / "frontend" / "public" / "data" / "traps.json"

# A "trap" for the You-Fall-For UI is a recognizable named opening line that
# catches beginners. Keyword filtering ("Gambit", "Attack") is too noisy
# because many mainline opening systems use those words (Queen's Gambit,
# Smith-Morra Gambit, King's Indian Attack).
#
# Strategy: explicit CURATED allowlist of trap names. Each entry below is
# a substring matched against the Lichess opening name. Includes all entries
# whose name contains the substring (so "Stafford" catches both
# "Petrov's Defense: Stafford Gambit" and its variations).
#
# Grow this list as we discover more traps that bleed ELO from kids.
TRAP_NAME_PATTERNS = (
    # Well-known beginner gambits
    "Stafford Gambit",
    "Elephant Gambit",
    "Latvian Gambit",
    "Englund Gambit",
    "Halloween Gambit",
    "Cochrane Gambit",
    "Damiano Defense",          # 2...f6 — punished hard
    "Tennison Gambit",
    "From's Gambit",
    "Blackburne Shilling",      # Blackburne Shilling Gambit
    "Albin Counter",            # Albin Counter-Gambit
    # Aggressive king attacks vs unprepared opponents
    "Wayward Queen Attack",     # Scholar's Mate setup
    "Fried Liver Attack",       # Two Knights Defense
    "Lolli Attack",             # Italian — early Ng5/Bxf7+ ideas
    "Max Lange Attack",         # Italian — sharp tactics
    "Traxler",                  # Traxler Counterattack
    # Named TRAPS proper
    "Fishing Pole",
    "Légal",
    "Legal Trap",
    "Lasker Trap",
    "Noah's Ark",
    "Magnus Smith Trap",
    "Marshall Trap",
    "Monticelli Trap",
    "Mortimer Trap",
    "Wormald",
    "Tarrasch Trap",
    "Siberian Trap",
    "Réti Endgame",
    # Quick-mate setups
    "Fool's Mate",
    "Scholar's Mate",
)

# Cap on how deep into the opening a trap signature can extend. Traps that
# fire later than this aren't beginner traps — they're deep theoretical lines.
MAX_TRAP_DEPTH = 16  # plies (~8 moves per side)


def _strip_san_annotations(san: str) -> str:
    """Remove move-number prefixes, periods, and result tokens from a SAN string."""
    # Remove "1.", "2.", "1...", etc.
    s = re.sub(r"\d+\.+", " ", san)
    # Remove result tokens
    s = re.sub(r"(1-0|0-1|1/2-1/2|\*)", " ", s)
    return s.strip()


def _moves_to_list(san: str) -> list[str]:
    """Parse a SAN move string from the Lichess TSV into a flat list of moves.
    Example input: '1. e4 e5 2. Nf3 Nc6'
    Output:        ['e4', 'e5', 'Nf3', 'Nc6']
    """
    cleaned = _strip_san_annotations(san)
    return [m for m in cleaned.split() if m]


def _fetch_tsv(volume: str, offline: bool) -> str:
    """Fetch one volume's TSV. Caches to scripts/.lichess_cache/<volume>.tsv.
    With --offline, only reads from cache and errors if missing.
    """
    cache_path = CACHE_DIR / f"{volume}.tsv"
    if cache_path.exists():
        return cache_path.read_text(encoding="utf-8")
    if offline:
        raise FileNotFoundError(
            f"--offline set but cache miss: {cache_path}. Run without --offline first."
        )
    url = f"{LICHESS_BASE}/{volume}.tsv"
    print(f"  fetching {url}")
    with urllib.request.urlopen(url, timeout=30) as resp:
        text = resp.read().decode("utf-8")
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(text, encoding="utf-8")
    return text


def _parse_tsv(text: str) -> list[dict]:
    """Parse one TSV into a list of {eco, name, moves_san, moves, depth} dicts.
    The Lichess TSV format is: eco<TAB>name<TAB>pgn (with header row)."""
    entries = []
    lines = text.splitlines()
    if not lines:
        return entries
    # Skip header if present
    start = 1 if lines[0].lower().startswith("eco\t") else 0
    for line in lines[start:]:
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        eco, name, pgn = parts[0].strip(), parts[1].strip(), parts[2].strip()
        if not eco or not name or not pgn:
            continue
        moves = _moves_to_list(pgn)
        entries.append({
            "eco": eco,
            "name": name,
            "moves_san": pgn,
            "moves": moves,
            "depth": len(moves),
        })
    return entries


def _is_trap(entry: dict) -> bool:
    """Return True if this opening matches the curated trap allowlist
    AND its move sequence is shallow enough to qualify as a beginner trap.
    """
    if entry["depth"] > MAX_TRAP_DEPTH:
        return False
    name = entry["name"]
    return any(pattern in name for pattern in TRAP_NAME_PATTERNS)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--dry-run", action="store_true",
                    help="Download/parse but don't write output files")
    ap.add_argument("--offline", action="store_true",
                    help="Use cached TSVs only; fail if cache missing")
    args = ap.parse_args()

    print(f"Building from Lichess chess-openings (CC0).")
    if args.offline:
        print(f"  --offline: reading cache from {CACHE_DIR}")

    all_entries = []
    for vol in VOLUMES:
        print(f"Volume {vol.upper()}:")
        text = _fetch_tsv(vol, offline=args.offline)
        entries = _parse_tsv(text)
        print(f"  parsed {len(entries)} openings")
        all_entries.extend(entries)

    # Slim entries for openings.json (drop the parsed `moves` list to keep file
    # size down — the frontend only needs eco, name, and the SAN string).
    openings_payload = [
        {"eco": e["eco"], "name": e["name"], "moves": e["moves_san"]}
        for e in all_entries
    ]

    # Trap subset
    traps_payload = [
        {
            "eco": e["eco"],
            "name": e["name"],
            "moves_san": e["moves_san"],
            "moves": e["moves"],
            "depth": e["depth"],
        }
        for e in all_entries
        if _is_trap(e)
    ]
    # Sort traps deepest-first so longest-prefix matching naturally picks the
    # most-specific variant when a game matches multiple entries.
    traps_payload.sort(key=lambda e: (-e["depth"], e["eco"], e["name"]))

    print(f"\nTotals:")
    print(f"  openings: {len(openings_payload)}")
    print(f"  traps:    {len(traps_payload)}")
    print(f"\nSample traps (first 10):")
    for t in traps_payload[:10]:
        print(f"  {t['eco']}  depth={t['depth']:>2}  {t['name']}")

    if args.dry_run:
        print("\n--dry-run: skipping write.")
        return

    OPENINGS_OUT.parent.mkdir(parents=True, exist_ok=True)
    OPENINGS_OUT.write_text(
        json.dumps(openings_payload, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    TRAPS_OUT.write_text(
        json.dumps(traps_payload, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    print(f"\nWrote:")
    print(f"  {OPENINGS_OUT.relative_to(REPO_ROOT)}  ({OPENINGS_OUT.stat().st_size:,} bytes)")
    print(f"  {TRAPS_OUT.relative_to(REPO_ROOT)}  ({TRAPS_OUT.stat().st_size:,} bytes)")


if __name__ == "__main__":
    sys.exit(main() or 0)
