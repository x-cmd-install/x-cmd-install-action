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
    import os
    if not loc_file or not os.path.isfile(loc_file):
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
    import os
    if not scorecard_file or not os.path.isfile(scorecard_file):
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


def activity_summary(card_file):
    """Return list of (window, release, mergedPR, openPR, closedIssue, openIssue, commit).

    windows: last30d, last90d, last360d — the most informative cuts.
    Returns empty list if no .recent block.
    """
    import os
    if not card_file or not os.path.isfile(card_file):
        return []
    windows = ["last30d", "last90d", "last360d"]
    rows = []
    for w in windows:
        since = yq(f'.recent["{w}"].since // ""', card_file)
        if not since:
            continue
        rel  = int(yq(f'.recent["{w}"].release // 0',     card_file) or 0)
        mpr  = int(yq(f'.recent["{w}"].mergedPR // 0',     card_file) or 0)
        opr  = int(yq(f'.recent["{w}"].openPR // 0',       card_file) or 0)
        ci   = int(yq(f'.recent["{w}"].closedIssue // 0',  card_file) or 0)
        oi   = int(yq(f'.recent["{w}"].openIssue // 0',    card_file) or 0)
        cmt  = int(yq(f'.recent["{w}"].commit // 0',       card_file) or 0)
        rows.append((w, since, rel, mpr, opr, ci, oi, cmt))
    return rows


def totals_summary(card_file):
    """Return dict of cumulative totals: release/mergedPR/openPR/closedIssue/openIssue/commit."""
    import os
    if not card_file or not os.path.isfile(card_file):
        return {}
    return {
        "release":      int(yq('.total.release // 0',      card_file) or 0),
        "mergedPR":     int(yq('.total.mergedPR // 0',     card_file) or 0),
        "openPR":       int(yq('.total.openPR // 0',       card_file) or 0),
        "closedIssue":  int(yq('.total.closedIssue // 0',  card_file) or 0),
        "openIssue":    int(yq('.total.openIssue // 0',    card_file) or 0),
        "commit":       int(yq('.total.commit // 0',       card_file) or 0),
    }


def release_assets_count(release_file):
    """Return (asset_count, published_at) for the latest release."""
    if not release_file:
        return 0, ""
    import os
    if not os.path.isfile(release_file):
        return 0, ""
    n_raw = yq('.assets // [] | length', release_file)
    try:
        n = int(n_raw)
    except ValueError:
        n = 0
    published = yq('.published_at // ""', release_file)
    return n, published


def classify_assets(classify_tsv):
    """Read the TSV produced by `x eget classify --tsv` and return a
    list of (name, url, size_bytes, target) rows.

    x eget classify emits 4 tab-separated columns:
      name<TAB>browser_download_url<TAB>size_bytes<TAB>target

    We keep the columns raw here — the caller is responsible for
    formatting size_bytes as human-readable when rendering.
    Returns [] if the file is missing or empty.
    """
    import os
    if not classify_tsv or not os.path.isfile(classify_tsv):
        return []
    rows = []
    with open(classify_tsv) as f:
        for line in f:
            line = line.rstrip("\n")
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) < 4:
                continue
            name, url, size_s, target = parts[0], parts[1], parts[2], parts[3]
            try:
                size = int(size_s)
            except ValueError:
                continue
            rows.append((name, url, size, target))
    return rows


def fmt_bytes(n):
    """1024-based: 0 → '0 B', 1024 → '1.0 KiB', 1536 → '1.5 KiB'."""
    if n < 1024:
        return f"{n} B"
    for unit in ("KiB", "MiB", "GiB", "TiB"):
        n /= 1024.0
        if abs(n) < 1024:
            return f"{n:.1f} {unit}"
    return f"{n:.1f} PiB"



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
        "assets":      "- **Assets in release**: {n}",
        "published":   "- **Published**: {ts}",
        "assets_h":    "## Release assets",
        "assets_hdr":  "| Asset | Size | Target |",
        "assets_sep":  "|-------|-----:|--------|",
        "assets_row":  "| [{name}]({url}) | {size} | `{target}` |",
        "popularity_h": "## Popularity",
        "popularity":  "- **Stars**: {stars} · **Forks**: {forks} · **Open issues**: {open_issues} · **Contributors**: {contributors}",
        "totals_h":    "## Totals (cumulative)",
        "totals_row":  "- **Releases**: {release} · **Merged PRs**: {mergedPR} · **Open PRs**: {openPR} · **Closed issues**: {closedIssue} · **Open issues**: {openIssue} · **Commits**: {commit}",
        "activity_h":  "## Recent activity",
        "activity_hdr":  "| Window | Since | Releases | Merged PRs | Open PRs | Closed issues | Open issues | Commits |",
        "activity_sep":  "|---|---|---:|---:|---:|---:|---:|---:|",
        "activity_row":  "| {window} | {since} | {rel} | {mpr} | {opr} | {ci} | {oi} | {cmt} |",
        "code_h":      "## Code size",
        "code_total":  "Total: **{total_loc:,}** lines of code across **{total_files}** files in the top 5 languages.",
        "code_hdr":    "| Language | Code | Comments | Blanks | Files |",
        "code_sep":    "|----------|-----:|---------:|-------:|------:|",
        "code_row":    "| {lang} | {code:,} | {comments:,} | {blanks:,} | {files} |",
        "sc_h":        "## OpenSSF Scorecard",
        "sc_total":    "Overall score: **{score} / 10**",
        "sc_low_h":    "Lowest-scoring checks:",
        "sc_low_row":  "- **{name}** ({score}/10) — {reason}",
        "improve_h":   "## Improve this data",
        "improve_body": "Install metadata for {name} lives in the [x-cmd/install](https://github.com/x-cmd/install) index — a curated YAML package list that x-cmd consumes at install time. If `{name}` is missing, out of date, or installs incorrectly, please open an issue or PR there:\n\n- **Open an issue**: <https://github.com/x-cmd/install/issues/new>\n- **Edit the package entry**: <https://github.com/x-cmd/install/edit/main/{name}.yml> (or whichever path the index uses)\n\nThe data on this page (card / loc / scorecard / release) is auto-collected by [x-cmd-install-action](https://github.com/x-cmd-install/x-cmd-install-action) and is regenerated daily. Improvements to *install behaviour* (which version gets installed, platform-specific quirks, dependencies) belong upstream in the index.",
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
        "assets":      "- **Release 含资产**: {n} 个",
        "published":   "- **发布时间**: {ts}",
        "assets_h":    "## Release 资产",
        "assets_hdr":  "| 资产 | 大小 | 目标平台 |",
        "assets_sep":  "|------|-----:|----------|",
        "assets_row":  "| [{name}]({url}) | {size} | `{target}` |",
        "popularity_h": "## 流行度",
        "popularity":  "- **Star**: {stars} · **Fork**: {forks} · **开放 issue**: {open_issues} · **贡献者**: {contributors}",
        "totals_h":    "## 累计统计",
        "totals_row":  "- **发布数**: {release} · **已合并 PR**: {mergedPR} · **开放 PR**: {openPR} · **已关闭 issue**: {closedIssue} · **开放 issue**: {openIssue} · **提交数**: {commit}",
        "activity_h":  "## 最近活动",
        "activity_hdr":  "| 时间窗口 | 起始 | 发布 | 已合并 PR | 开放 PR | 已关闭 issue | 开放 issue | 提交 |",
        "activity_sep":  "|---|---|---:|---:|---:|---:|---:|---:|",
        "activity_row":  "| {window} | {since} | {rel} | {mpr} | {opr} | {ci} | {oi} | {cmt} |",
        "code_h":      "## 代码规模",
        "code_total":  "合计: **{total_loc:,}** 行代码（覆盖前 5 种语言、共 **{total_files}** 个文件）。",
        "code_hdr":    "| 语言 | 代码 | 注释 | 空行 | 文件数 |",
        "code_sep":    "|------|-----:|-----:|-----:|------:|",
        "code_row":    "| {lang} | {code:,} | {comments:,} | {blanks:,} | {files} |",
        "sc_h":        "## OpenSSF Scorecard 评分",
        "sc_total":    "总评分: **{score} / 10**",
        "sc_low_h":    "评分最低的几项:",
        "sc_low_row":  "- **{name}** ({score}/10) — {reason}",
        "improve_h":   "## 改进这些数据",
        "improve_body": "{name} 的安装元数据由 [x-cmd/install](https://github.com/x-cmd/install) 索引维护——这是一份由 x-cmd 在安装时读取的精选 YAML 包列表。如果 `{name}` 缺失、过期，或安装行为有问题，欢迎在该 repo 提 issue 或 PR：\n\n- **提交 issue**: <https://github.com/x-cmd/install/issues/new>\n- **编辑包条目**: <https://github.com/x-cmd/install/edit/main/{name}.yml>（或索引实际使用的路径）\n\n本页面的数据（card / loc / scorecard / release）由 [x-cmd-install-action](https://github.com/x-cmd-install/x-cmd-install-action) 自动采集，每日重新生成。**安装行为**（版本选择、平台差异、依赖处理）的改进应提交到上游索引。",
        "footer":      "_数据快照: `data/card/{d}.yml` · {now}._",
        "logo":        "![{name}](https://repo.x-cmd.io/{name}.svg)",
    },
}


def build_readme(lang, name, owner_repo, d, card, loc, scorecard, classify_tsv):
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
    activity_rows = activity_summary(card)
    totals = totals_summary(card)
    asset_rows = classify_assets(classify_tsv)

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
        if asset_rows:
            lines.append(t["assets"].format(n=len(asset_rows)))
        lines.append("")

    # Release assets table — only if x eget classify produced rows.
    # Each row: name is a hyperlink to the GitHub release download URL,
    # size is human-readable (KiB/MiB/GiB), target is x-cmd's native
    # platform identifier (e.g. native/darwin/arm64).
    if asset_rows:
        lines.append(t["assets_h"])
        lines.append("")
        lines.append(t["assets_hdr"])
        lines.append(t["assets_sep"])
        for aname, aurl, asize, atarget in asset_rows:
            lines.append(t["assets_row"].format(
                name=aname, url=aurl, size=fmt_bytes(asize), target=atarget,
            ))
        lines.append("")

    # Popularity block
    lines.append(t["popularity_h"])
    lines.append("")
    lines.append(t["popularity"].format(
        stars=stars, forks=forks, open_issues=open_issues, contributors=contributors,
    ))
    lines.append("")

    # Totals (cumulative) — only if we have data
    if totals:
        lines.append(t["totals_h"])
        lines.append("")
        lines.append(t["totals_row"].format(**totals))
        lines.append("")

    # Recent activity — only if we have data
    if activity_rows:
        lines.append(t["activity_h"])
        lines.append("")
        lines.append(t["activity_hdr"])
        lines.append(t["activity_sep"])
        # Format window labels for display
        win_label = {"last30d": "30d", "last90d": "90d", "last360d": "360d"}
        for w, since, rel, mpr, opr, ci, oi, cmt in activity_rows:
            lines.append(t["activity_row"].format(
                window=win_label.get(w, w), since=since, rel=rel, mpr=mpr,
                opr=opr, ci=ci, oi=oi, cmt=cmt,
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

    # Improve section — always present, invites contribution
    lines.append(t["improve_h"])
    lines.append("")
    lines.append(t["improve_body"].format(name=name))
    lines.append("")

    lines.append(t["footer"].format(d=d, now=now))
    return "\n".join(lines) + "\n"


def main():
    if len(sys.argv) != 7:
        print(f"usage: {sys.argv[0]} <card.yml> <loc.yml> <scorecard.yml> <classify.tsv> <owner_repo> <date_stamp>",
              file=sys.stderr)
        sys.exit(2)
    card, loc, scorecard, classify_tsv = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
    owner_repo, d = sys.argv[5], sys.argv[6]
    name = owner_repo.split("/", 1)[-1]

    en = build_readme("en", name, owner_repo, d, card, loc, scorecard, classify_tsv)
    cn = build_readme("cn", name, owner_repo, d, card, loc, scorecard, classify_tsv)

    with open("README.md", "w") as f:
        f.write(en)
    with open("README.cn.md", "w") as f:
        f.write(cn)


if __name__ == "__main__":
    main()
