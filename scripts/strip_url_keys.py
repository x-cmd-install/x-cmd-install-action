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
     with `---` (those would be interpreted as document separators
     by the YAML parser). The release JSON doesn't have either, so
     it's safe.

  NB on (2): "JSON is a subset of YAML" only holds for the ASCII
  subset. With ensure_ascii=True (json.dumps' default) any non-ASCII
  character is emitted as a \\uXXXX escape — and for code points
  outside the BMP that escape is a *surrogate pair* (\\ud83d\\udee0 for
  U+1F6E0 🛠). YAML's \\u escape takes exactly one code point and
  rejects surrogate halves, so Go's yaml parser (and therefore yq)
  fails with "found invalid Unicode character escape code". The
  release body of e.g. envd v1.3.6 contains such an emoji, which
  made data/latest.report.yml unparseable as YAML and silently
  dropped the .json mirror downstream.

  ensure_ascii=False emits the characters literally as UTF-8 instead.
  The result is still valid JSON (json.load round-trips it) and is
  valid YAML, because a literal character in a YAML double-quoted
  scalar needs no escape processing at all.

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
    print(json.dumps(strip_url_keys(data), separators=(",", ":"),
                     ensure_ascii=False))
