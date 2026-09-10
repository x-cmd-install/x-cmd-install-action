#!/usr/bin/env python3
"""generate_readme.py — write README.md (English) and README.cn.md (Chinese)
from card / loc / scorecard YAML.

Usage:
    generate_readme.py <card.yml> <loc.yml> <scorecard.yml> \\
                      <owner_repo> <date_stamp>

Outputs two files in the current directory:
  README.md     — English version (primary, GitHub displays this by default)
  README.cn.md  — Chinese version (linked from README.md)

Why a Python script (not a bash heredoc):
  The action's YAML manifest uses a literal-block scalar for the run
  step (`run: |`). GitHub Actions' simplified YAML parser refuses to
  accept any line containing ': ' inside such a block — markdown is
  full of those. Moving the template to a standalone script sidesteps
  the parser quirk entirely.

Layout strategy:
  Front-load everything SEO-relevant on the first screen:
    1. Title + description (the actual content of the software)
    2. Logo SVG (every mirror gets https://repo.x-cmd.io/<name>.svg)
    3. Upstream + homepage links
    4. Install command
    5. Metadata block (license, release, popularity)
  Then the data block:
    6. Code size — top 5 languages with code/comments/blanks/files
    7. OpenSSF scorecard score and 3 lowest individual checks
  Skip plumbing — no "auto-maintained by" boilerplate that dilutes
  the page's keywords without adding anything for the visitor.

Note on yq usage:
  mikefarah/yq v4 in some setups refuses pipe syntax in expression
  args ('Error: | expects 2 args'). We avoid multi-step pipelines and
  do one yq call per field. Slightly slower but rock-solid.
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
    of (language, code, comments, blanks, files) sorted by code desc.
    """
    if not loc_file:
        return 0, []
    keys = yq('.loc | keys | .[]', loc_file)
    if not keys:
        return 0, []
    rows = []
    for lang in keys.splitlines():
        if not lang:
            continue
        try:
            code     = int(yq(f'.loc["{lang}"].code // 0',     loc_file) or 0)
            comments = int(yq(f'.loc["{lang}"].comments // 0', loc_file) or 0)
            blanks   = int(yq(f'.loc["{lang}"].blanks // 0',   loc_file) or 0)
            files    = int(yq(f'.loc["{lang}"].files // 0',    loc_file) or 0)
        except ValueError:
            continue
        rows.append((lang, code, comments, blanks, files))
    rows.sort(key=lambda r: -r[1])
    return sum(r[1] for r in rows), rows[:5]


def scorecard_summary(scorecard_file):
    """Return (overall_score, low_score_checks)."""
    if not scorecard_file:
        return None, []
    score = yq('.score // ""', scorecard_file)
    if not score:
        return None, []

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


# ---------- i18n strings ----------

T = {
    "en": {
        "lang_link":   "中文版本",
        "archived":    "> ⚠️ This project is archived.",
        "install_h":   "## Install",
        "install_cmd": "x install {name}",
        "source_h":    "## Source",
        "upstream":    "- **Upstream**: <https://github.com/{owner_repo}>",
        "homepage":    "- **Homepage**: <{homepage}>",
        "license":     "- **License**: {license}",
        "release_h":   "## Release",
        "latest":      "- **Latest**: `{latest}`",
        "latest_with_date": "- **Latest**: `{latest}` ({last_release})",
        "last_commit": "- **Last commit**: {last_commit}",
        "popularity_h": "## Popularity",
        "popularity":  "- **Stars**: {stars} · **Forks**: {forks} · **Open issues**: {open_issues} · **Contributors**: {contributors}",
        "code_h":      "## Code size",
        "code_total":  "Total: **{total_loc:,}** lines of code across **{total_files}** files in the top 5 languages.",
        "code_hdr":    "| Language | Code | Comments | Blanks | Files |",
        "code_sep":    "|----------|-----:|---------:|-------:|------:|",
        "code_row":    "| {lang} | {code:,} | {comments:,} | {blanks:,} | {files} |",
        "sc_h":        "## OpenSSF Scorecard",
        "sc_total":    "Overall score: **{score} / 10**",
        "sc_low_h":    "Lowest-scoring checks:",
        "sc_low_row":  "- **{name}** ({score}/10) — {reason}",
        "footer":      "_Snapshot: `data/card/{d}.yml` · {now}._",
        "logo":        "![{name}](https://repo.x-cmd.io/{name}.svg)",
    },
    "cn": {
        "lang_link":   "English version",
        "archived":    "> ⚠️ 此项目已归档（archived）。",
        "install_h":   "## 安装",
        "install_cmd": "x install {name}",
        "source_h":    "## 源代码",
        "upstream":    "- **上游仓库**: <https://github.com/{owner_repo}>",
        "homepage":    "- **官网**: <{homepage}>",
        "license":     "- **许可证**: {license}",
        "release_h":   "## 发布",
        "latest":      "- **最新版本**: `{latest}`",
        "latest_with_date": "- **最新版本**: `{latest}` ({last_release})",
        "last_commit": "- **最近提交**: {last_commit}",
        "popularity_h": "## 流行度",
        "popularity":  "- **Star**: {stars} · **Fork**: {forks} · **开放 issue**: {open_issues} · **贡献者**: {contributors}",
        "code_h":      "## 代码规模",
        "code_total":  "合计: **{total_loc:,}** 行代码（覆盖前 5 种语言、共 **{total_files}** 个文件）。",
        "code_hdr":    "| 语言 | 代码 | 注释 | 空行 | 文件数 |",
        "code_sep":    "|------|-----:|-----:|-----:|------:|",
        "code_row":    "| {lang} | {code:,} | {comments:,} | {blanks:,} | {files} |",
        "sc_h":        "## OpenSSF Scorecard 评分",
        "sc_total":    "总评分: **{score} / 10**",
        "sc_low_h":    "评分最低的几项:",
        "sc_low_row":  "- **{name}** ({score}/10) — {reason}",
        "footer":      "_数据快照: `data/card/{d}.yml` · {now}._",
        "logo":        "![{name}](https://repo.x-cmd.io/{name}.svg)",
    },
}


def build_readme(lang, name, owner_repo, d, card, loc, scorecard):
    """Return the rendered README content for one language."""
    t = T[lang]

    desc          = yq('.about.description // ""', card)
    homepage      = yq('.about.homepage // ""', card)
    latest        = yq('.about.latestVersion // ""', card)
    license_      = yq('.about.license // ""', card)
    stars         = fmt_int(yq('.popularity.star // 0', card))
    forks         = fmt_int(yq('.popularity.fork // 0', card))
    open_issues   = fmt_int(yq('.popularity.issue // 0', card))
    contributors  = fmt_int(yq('.popularity.contributor // 0', card))
    last_commit   = yq('.timeline.lastCommit // ""', card)
    last_release  = yq('.timeline.lastRelease // ""', card)
    archived      = yq('.about.archived // false', card).lower() == "true"

    total_loc, top_langs = loc_summary(loc)
    score, low_checks = scorecard_summary(scorecard)

    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    lines = []
    lines.append(f"# {name}")
    lines.append("")

    # Cross-language link at the very top so a reader can switch
    # language without hunting for the right file. The link text is
    # the *current* file's invitation to switch — "中文版本" on the
    # English README invites the reader to go read the Chinese one,
    # "English version" on the Chinese README invites them back.
    if lang == "en":
        lines.append(f"[{T['en']['lang_link']}](./README.cn.md)")
    else:
        lines.append(f"[{T['cn']['lang_link']}](./README.md)")
    lines.append("")

    if archived:
        lines.append(t["archived"])
        lines.append("")

    if desc:
        lines.append(desc)
        lines.append("")

    lines.append(t["logo"].format(name=name))
    lines.append("")

    # Install block — first thing the visitor wants to know
    lines.append(t["install_h"])
    lines.append("")
    lines.append("```sh")
    lines.append(t["install_cmd"].format(name=name))
    lines.append("```")
    lines.append("")

    # Source block
    lines.append(t["source_h"])
    lines.append("")
    lines.append(t["upstream"].format(owner_repo=owner_repo))
    if homepage:
        lines.append(t["homepage"].format(homepage=homepage))
    if license_:
        lines.append(t["license"].format(license=license_))
    lines.append("")

    # Release block — only if we have one
    if latest or last_release:
        lines.append(t["release_h"])
        lines.append("")
        if latest:
            if last_release:
                lines.append(t["latest_with_date"].format(latest=latest, last_release=last_release))
            else:
                lines.append(t["latest"].format(latest=latest))
        if last_commit:
            lines.append(t["last_commit"].format(last_commit=last_commit))
        lines.append("")

    # Popularity block
    lines.append(t["popularity_h"])
    lines.append("")
    lines.append(t["popularity"].format(
        stars=stars, forks=forks, open_issues=open_issues, contributors=contributors,
    ))
    lines.append("")

    # LOC block — only if we have data
    if total_loc > 0:
        lines.append(t["code_h"])
        lines.append("")
        total_files = sum(t_[4] for t_ in top_langs)
        lines.append(t["code_total"].format(total_loc=total_loc, total_files=total_files))
        lines.append("")
        lines.append(t["code_hdr"])
        lines.append(t["code_sep"])
        for lang_, code, comments, blanks, files in top_langs:
            lines.append(t["code_row"].format(
                lang=lang_, code=code, comments=comments, blanks=blanks, files=files,
            ))
        lines.append("")

    # OpenSSF scorecard block — only if we have a score
    if score:
        lines.append(t["sc_h"])
        lines.append("")
        lines.append(t["sc_total"].format(score=score))
        lines.append("")
        if low_checks:
            lines.append(t["sc_low_h"])
            lines.append("")
            for name_, s, reason in low_checks:
                r = (reason[:120] + "…") if len(reason) > 120 else reason
                lines.append(t["sc_low_row"].format(name=name_, score=s, reason=r))
            lines.append("")

    lines.append(t["footer"].format(d=d, now=now))
    return "\n".join(lines) + "\n"


def main():
    if len(sys.argv) != 6:
        print(f"usage: {sys.argv[0]} <card.yml> <loc.yml> <scorecard.yml> <owner_repo> <date_stamp>",
              file=sys.stderr)
        sys.exit(2)
    card, loc, scorecard = sys.argv[1], sys.argv[2], sys.argv[3]
    owner_repo, d = sys.argv[4], sys.argv[5]
    name = owner_repo.split("/", 1)[-1]

    en = build_readme("en", name, owner_repo, d, card, loc, scorecard)
    cn = build_readme("cn", name, owner_repo, d, card, loc, scorecard)

    with open("README.md", "w") as f:
        f.write(en)
    with open("README.cn.md", "w") as f:
        f.write(cn)


if __name__ == "__main__":
    main()
