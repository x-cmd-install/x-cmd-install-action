#!/usr/bin/env python3
"""strip_url_keys.py — recursively drop every key whose name contains
'url' (case-insensitive) from a JSON object on stdin. Outputs the
trimmed JSON on stdout (YAML's safe_dump produces the body).

The GitHub release API JSON has many URL fields (url, html_url,
assets_url, upload_url, tarball_url, zipball_url, and per-asset
download/browser URLs). They're large and not useful for downstream
consumers — this script removes them so the merged report.yml
stays compact.

We emit YAML (via yaml.safe_dump) instead of JSON because the
caller concatenates the output with the 3 card documents into a
multi-doc YAML file, and that file must be valid YAML end-to-end.
(Inline JSON would also be valid YAML since JSON ⊂ YAML, but the
explicit block-style YAML is much easier to read and grep.)

Usage:
    python3 strip_url_keys.py < input.json > output.yaml
"""
import json
import sys

import yaml


def strip_url_keys(d):
    if isinstance(d, dict):
        return {k: strip_url_keys(v) for k, v in d.items()
                if not (isinstance(k, str) and "url" in k.lower())}
    if isinstance(d, list):
        return [strip_url_keys(x) for x in d]
    return d


if __name__ == "__main__":
    data = json.load(sys.stdin)
    # emit safe_dump — block style (default), no anchors, full width
    print(
        yaml.safe_dump(
            strip_url_keys(data),
            default_flow_style=False,
            sort_keys=False,
            allow_unicode=True,
            width=10**9,
        ),
        end="",
    )
