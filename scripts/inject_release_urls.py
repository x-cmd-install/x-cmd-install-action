#!/usr/bin/env python3
"""inject_release_urls.py — read a stripped GitHub release JSON from
stdin, synthesize browser_download_url for every asset, write the
patched JSON to stdout.

Used in the action's Generate README step. The mirror's data/ file
is not touched — this only runs in the runner, where x eget classify
needs the URL field to render the link column. We rebuild the URL
from the well-known GitHub release layout:
    https://github.com/{owner_repo}/releases/download/{tag}/{asset_name}

Usage:
    inject_release_urls.py <owner_repo> < input.json > output.json
"""
import json
import sys


def main():
    if len(sys.argv) != 2:
        print(f"usage: {sys.argv[0]} <owner_repo>", file=sys.stderr)
        sys.exit(2)
    owner_repo = sys.argv[1]

    data = json.load(sys.stdin)
    tag = data.get("tag_name", "")
    for a in data.get("assets", []):
        name = a.get("name", "")
        a["browser_download_url"] = (
            f"https://github.com/{owner_repo}/releases/download/{tag}/{name}"
        )
    json.dump(data, sys.stdout)


if __name__ == "__main__":
    main()
