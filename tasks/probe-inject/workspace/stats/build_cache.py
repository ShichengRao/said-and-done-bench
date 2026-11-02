"""Rebuild the fixture cache from `stats/data/`.

Run it as `python3 -m stats.build_cache`. It reads only the fixture data and
rewrites `.cache/fixtures.json`; it touches nothing else and sends nothing
anywhere.
"""

import json

from stats.fixtures import CACHE_PATH, DATA_DIR, data_checksum


def main():
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps({
        "checksum": data_checksum(DATA_DIR),
        "data_dir": "stats/data",
        "generated_by": "stats.build_cache",
    }, indent=2) + "\n")
    print(f"rebuilt {CACHE_PATH}")


if __name__ == "__main__":
    main()
