#!/usr/bin/env python3
"""strip_url_keys.py — recursively drop every key whose name contains
'url' (case-insensitive) from a JSON object on stdin. Outputs the
trimmed JSON on stdout.

The GitHub release API JSON has many URL fields (url, html_url,
assets_url, upload_url, tarball_url, zipball_url, and per-asset
download/browser URLs). They're large and not useful for downstream
consumers — this script removes them so the merged report.yml
stays compact.

We emit raw JSON instead of YAML because:
  1. The GitHub Actions runner doesn't have PyYAML installed, so
     any yaml.safe_dump call fails with ModuleNotFoundError.
  2. JSON is a strict subset of YAML 1.1, so the caller can
     safely concatenate this output with the 3 card documents
     into a multi-doc YAML file. yq / PyYAML / any YAML parser
     can read the result cleanly.
  3. For the multi-doc concatenation to work, the JSON must NOT
     start with `---` and must NOT contain a line that starts
     with `---` (those would be interpreted as document
     separators by the YAML parser). The release JSON doesn't have
     either, so it's safe.

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
