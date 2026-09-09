#!/usr/bin/env python3
"""generate_readme.py — write README.md from card / loc / scorecard YAML.

Usage:
    generate_readme.py <card.yml> <loc.yml> <scorecard.yml> \\
                      <owner_repo> <date_stamp> > README.md

Why this is a Python script rather than a bash heredoc:
  The action's YAML manifest uses a literal-block scalar for the run
  step (`run: |`). GitHub Actions' simplified YAML parser refuses to
  accept any line that contains ': ' (colon-space) inside such a
  block — README markdown is full of those. Moving the README template
  out of the action.yml and into a standalone script sidesteps that
  parser quirk entirely.

Layout strategy:
  Front-load everything SEO-relevant on the first screen:
    1. Title + description (the actual content of the software)
    2. Upstream + homepage links
    3. Install command
    4. Metadata block (license, release, popularity)
  Then the data block:
    5. LOC summary (top 5 languages by code size + grand total)
    6. OpenSSF scorecard score (single number) and top failing checks
  Skip anything that's pure plumbing — no "auto-maintained by" boilerplate.

Note on yq usage:
  mikefarah/yq v4 in some setups refuses pipe syntax in expression
  args ('| expects 2 args'). We avoid multi-step pipelines and do one
  yq call per field. Slightly slower but rock-solid.
"""
import datetime
import subprocess
import sys


def yq(expr, file, default=""):
    """yq expression → string. Returns default on empty/null/error."""
    if not file:
        return default
    try:
        r = subprocess.run(
            ["yq", "-r", expr, file],
            capture_output=True, text=True, check=True,
        )
        out = r.stdout.rstrip("\n")
        return out if out and out != "null" else default
    except (subprocess.CalledProcessError, FileNotFoundError):
        return default


def fmt_int(n):
    try:
        return f"{int(str(n).replace(',', '')):,}"
    except (ValueError, TypeError):
        return "0"


def loc_summary(loc_file):
    """Return (total_code, top_langs) where top_langs is up to 5 entries
    of (language, code_lines, file_count) sorted by code desc.
    """
    if not loc_file:
        return 0, []
    # Get the list of language keys first, then read each individually.
    keys = yq('.loc | keys | .[]', loc_file)
    if not keys:
        return 0, []
    rows = []
    for lang in keys.splitlines():
        if not lang:
            continue
        try:
            code = int(yq(f'.loc["{lang}"].code // 0', loc_file) or 0)
            files = int(yq(f'.loc["{lang}"].files // 0', loc_file) or 0)
        except ValueError:
            continue
        rows.append((lang, code, files))
    rows.sort(key=lambda r: -r[1])
    return sum(r[1] for r in rows), rows[:5]


def scorecard_summary(scorecard_file):
    """Return (overall_score, low_score_checks)."""
    if not scorecard_file:
        return None, []
    score = yq('.score // ""', scorecard_file)
    if not score:
        return None, []

    # We can't use a yq pipe expression to enumerate checks safely, so
    # read the count first, then index in. This caps at 30 checks
    # (more than enough — scorecard has ~18 in practice).
    count_raw = yq('.checks // [] | length', scorecard_file)
    try:
        n = int(count_raw)
    except ValueError:
        return score, []
    n = min(n, 30)

    lows = []
    for i in range(n):
        name = yq(f'.checks[{i}].name // ""', scorecard_file)
        s = yq(f'.checks[{i}].score // 0', scorecard_file)
        reason = yq(f'.checks[{i}].reason // ""', scorecard_file)
        try:
            si = int(s)
        except ValueError:
            continue
        if si < 5 and len(lows) < 3:
            lows.append((name, si, reason))
    return score, lows


def main():
    card, loc, scorecard = sys.argv[1], sys.argv[2], sys.argv[3]
    owner_repo, d = sys.argv[4], sys.argv[5]
    name = owner_repo.split("/", 1)[-1]

    desc          = yq('.about.description // ""',           card)
    homepage      = yq('.about.homepage // ""',              card)
    latest        = yq('.about.latestVersion // ""',         card)
    license_      = yq('.about.license // ""',               card)
    stars         = fmt_int(yq('.popularity.star // 0',       card))
    forks         = fmt_int(yq('.popularity.fork // 0',       card))
    open_issues   = fmt_int(yq('.popularity.issue // 0',      card))
    contributors  = fmt_int(yq('.popularity.contributor // 0', card))
    last_commit   = yq('.timeline.lastCommit // ""',          card)
    last_release  = yq('.timeline.lastRelease // ""',        card)
    archived      = yq('.about.archived // false',           card).lower() == "true"

    total_loc, top_langs = loc_summary(loc)
    score, low_checks = scorecard_summary(scorecard)

    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    lines = []
    lines.append(f"# {name}")
    lines.append("")

    if archived:
        lines.append("> ⚠️ This project is archived.")
        lines.append("")

    if desc:
        lines.append(desc)
        lines.append("")

    # Install block — first thing the visitor wants to know
    lines.append("## Install")
    lines.append("")
    lines.append("```sh")
    lines.append(f"x install {name}")
    lines.append("```")
    lines.append("")

    # Source block
    lines.append("## Source")
    lines.append("")
    lines.append(f"- **Upstream**: <https://github.com/{owner_repo}>")
    if homepage:
        lines.append(f"- **Homepage**: <{homepage}>")
    if license_:
        lines.append(f"- **License**: {license_}")
    lines.append("")

    # Release block — only if we have one
    if latest or last_release:
        lines.append("## Release")
        lines.append("")
        if latest:
            rline = f"- **Latest**: `{latest}`"
            if last_release:
                rline += f" ({last_release})"
            lines.append(rline)
        if last_commit:
            lines.append(f"- **Last commit**: {last_commit}")
        lines.append("")

    # Popularity block
    lines.append("## Popularity")
    lines.append("")
    lines.append(f"- **Stars**: {stars} · **Forks**: {forks} · **Open issues**: {open_issues} · **Contributors**: {contributors}")
    lines.append("")

    # LOC block — only if we have data
    if total_loc > 0:
        lines.append("## Code size")
        lines.append("")
        total_files = sum(t[2] for t in top_langs)
        lines.append(f"Total: **{total_loc:,}** lines of code across {total_files} of the top files.")
        lines.append("")
        lines.append("| Language | Code | Files |")
        lines.append("|----------|-----:|------:|")
        for lang, code, files in top_langs:
            lines.append(f"| {lang} | {code:,} | {files} |")
        lines.append("")

    # OpenSSF scorecard block — only if we have a score
    if score:
        lines.append("## OpenSSF Scorecard")
        lines.append("")
        lines.append(f"Overall score: **{score} / 10**")
        lines.append("")
        if low_checks:
            lines.append("Lowest-scoring checks:")
            lines.append("")
            for name_, s, reason in low_checks:
                r = (reason[:120] + "…") if len(reason) > 120 else reason
                lines.append(f"- **{name_}** ({s}/10) — {r}")
            lines.append("")

    # Footnote — small, plain, no SEO-damaging boilerplate
    lines.append(f"_Snapshot: `data/card/{d}.yml` · {now}._")

    sys.stdout.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
