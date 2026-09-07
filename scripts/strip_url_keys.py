#!/usr/bin/env python3
"""strip_url_keys.py — recursively drop every key whose name contains
'url' (case-insensitive) from a JSON object on stdin. Outputs the
trimmed JSON on stdout.

The GitHub release API JSON has many URL fields (url, html_url,
assets_url, upload_url, tarball_url, zipball_url, and per-asset
download/browser URLs). They're large and not useful for downstream
consumers — this script removes them so the merged report.yml
stays compact.

Usage:
    python3 strip_url_keys.py < input.json > output.json
"""
import json
import sys


def strip_url_keys(d):
    if isinstance(d, dict):
        return {k: strip_url_keys(v) for k, v in d.items()
                if not (isinstance(k, str) and "url" in k.lower())}
    if isinstance(d, list):
        return [strip_url_keys(x) for x in d]
    return d


if __name__ == "__main__":
    data = json.load(sys.stdin)
    print(json.dumps(strip_url_keys(data), separators=(",", ":")))
