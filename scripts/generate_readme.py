#!/usr/bin/env python3
"""generate_readme.py — write README.md from card YAML fields.

Usage:
    generate_readme.py <card.yml> <owner_repo> <date_stamp> > README.md

Why this is a Python script rather than a bash heredoc:
  The action's YAML manifest uses a literal-block scalar for the run
  step (`run: |`). GitHub Actions' simplified YAML parser refuses to
  accept any line that contains `: ` (colon-space) inside such a
  block — README markdown is full of those. Moving the README template
  out of the action.yml and into a standalone script sidesteps that
  parser quirk entirely.
"""
import datetime
import os
import subprocess
import sys


def yq(expr, file):
    r = subprocess.run(
        ["yq", "-r", expr, file],
        capture_output=True, text=True, check=True,
    )
    return r.stdout.rstrip("\n")


def main():
    card = sys.argv[1]
    owner_repo = sys.argv[2]
    d = sys.argv[3]
    name = owner_repo.split("/", 1)[-1]

    fields = {
        "desc":          yq('.about.description // "n/a"',         card),
        "homepage":      yq('.about.homepage // ""',                card),
        "latest":        yq('.about.latestVersion // "n/a"',        card),
        "license":       yq('.about.license // "n/a"',              card),
        "stars":         yq('.popularity.star // 0',                card),
        "forks":         yq('.popularity.fork // 0',                card),
        "open_issues":   yq('.popularity.issue // 0',               card),
        "contributors":  yq('.popularity.contributor // 0',         card),
        "last_commit":   yq('.timeline.lastCommit // "n/a"',        card),
        "last_release":  yq('.timeline.lastRelease // "n/a"',       card),
    }

    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    out = f"""# {name}

{fields['desc']}

- **Upstream**: <https://github.com/{owner_repo}>
- **Homepage**: <{fields['homepage']}>
- **Latest release**: `{fields['latest']}` ({fields['last_release']})
- **Last commit**: {fields['last_commit']}
- **License**: {fields['license']}
- **Stars**: {fields['stars']} · **Forks**: {fields['forks']} · **Open issues**: {fields['open_issues']} · **Contributors**: {fields['contributors']}

## Installation

```sh
x install {name}
```

See <https://x-cmd.com/install/{name}> for details.

## Data

This mirror is auto-maintained by [x-cmd-install-action](https://github.com/x-cmd-install/x-cmd-install-action). Latest card snapshot: `data/card/{d}.yml`. Merged card+release view: `data/latest.report.yml`.

_Last regenerated: {now}._
"""
    sys.stdout.write(out)


if __name__ == "__main__":
    main()
