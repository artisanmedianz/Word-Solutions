#!/usr/bin/env python3
"""Build an audited, spoiler-safe history of published Wordle solutions."""
import argparse
import datetime as dt
import json
import os
import pathlib
import re
import sys
import time
import urllib.error
import urllib.request
from collections import defaultdict

START = dt.date(2021, 6, 19)  # Wordle #0
NYT = "https://www.nytimes.com/svc/wordle/v2/{}.json"
SOURCE = "https://raw.githubusercontent.com/johnfoland/nyt-wordle-played/master/played_5.json"
ROOT = pathlib.Path(__file__).parent
HISTORY = ROOT / "data" / "history.json"
OUTPUT = ROOT / "data" / "wordle-solutions.json"
WORD = re.compile(r"^[A-Z]{5}$")


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "WordSolutionsHistory/1.0", "Accept": "application/json"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=25) as response:
                return json.load(response)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)


def validate(game, word):
    if not isinstance(game, int) or game < 0 or not isinstance(word, str) or not WORD.fullmatch(word):
        raise ValueError(f"Invalid puzzle entry: {game!r}, {word!r}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--as-of", type=dt.date.fromisoformat, default=dt.datetime.now(dt.timezone.utc).date(),
                        help="Last eligible calendar date; production job uses UTC date minus one day")
    parser.add_argument("--no-network", action="store_true", help="Rebuild solely from saved history")
    args = parser.parse_args()
    # Yesterday in UTC is over everywhere by the time the scheduled job runs.
    end = args.as_of if args.no_network else min(args.as_of, dt.datetime.now(dt.timezone.utc).date() - dt.timedelta(days=1))
    max_game = (end - START).days
    if max_game < 0:
        raise ValueError("The requested date precedes Wordle #0")
    history = json.loads(HISTORY.read_text()) if HISTORY.exists() else {}
    history = {int(k): v for k, v in history.items()}
    for game, word in history.items():
        validate(game, word)
    if not args.no_network:
        # The community archive is an optional fast seed. Its earliest games may be missing.
        try:
            source = fetch(SOURCE)
            for key, raw_word in source["played"].items():
                game, word = int(key), raw_word.upper()
                validate(game, word)
                if game <= max_game and game in history and history[game] != word:
                    raise ValueError(f"Archive conflicts with saved puzzle #{game}")
                if game <= max_game:
                    history[game] = word
        except ValueError:
            raise
        except (OSError, KeyError, TypeError) as exc:
            print(f"Community seed unavailable: {exc}; checking NYT by date", file=sys.stderr)

        # Fetch every gap from the publisher; recheck recent dates for corrections.
        needed = sorted(set(range(max_game + 1)) - history.keys() | set(range(max(0, max_game - 6), max_game + 1)))
        for game in needed:
            date = START + dt.timedelta(days=game)
            try:
                puzzle = fetch(NYT.format(date.isoformat()))
            except (OSError, ValueError) as exc:
                raise RuntimeError(f"Could not verify {date}: {exc}") from exc
            word = str(puzzle.get("solution", "")).upper()
            validate(game, word)
            if puzzle.get("print_date") != date.isoformat() or puzzle.get("days_since_launch") != game:
                raise ValueError(f"Publisher metadata mismatch for #{game} / {date}")
            history[game] = word
            if game % 100 == 0:
                print(f"Verified #{game}", flush=True)
            time.sleep(0.1)

    gaps = set(range(max_game + 1)) - history.keys()
    if gaps:
        raise ValueError(f"History incomplete: {len(gaps)} gaps; first #{min(gaps)}. Nothing published.")
    if any(game > max_game for game in history):
        history = {game: word for game, word in history.items() if game <= max_game}
    uses = defaultdict(list)
    for game in sorted(history):
        uses[history[game]].append(game)
    words = []
    for word, games in sorted(uses.items()):
        last = START + dt.timedelta(days=games[-1])
        words.append({"word": word, "timesUsed": len(games), "lastUsed": last.isoformat(),
                      "puzzleNumbers": games})
    payload = {"schemaVersion": 1, "asOfDate": end.isoformat(), "firstPuzzleDate": START.isoformat(),
               "puzzleCount": len(history), "uniqueWordCount": len(words), "words": words}
    HISTORY.parent.mkdir(parents=True, exist_ok=True)
    # Only write after complete validation. Replacement is atomic.
    for path, data in [(HISTORY, {str(k): history[k] for k in sorted(history)}), (OUTPUT, payload)]:
        temp = path.with_suffix(".tmp")
        temp.write_text(json.dumps(data, separators=(",", ":"), ensure_ascii=True) + "\n")
        os.replace(temp, path)
    print(f"Published {len(history)} puzzles, {len(words)} distinct answers through {end}")


if __name__ == "__main__":
    main()
