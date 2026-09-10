#!/usr/bin/env python3
"""classify_assets.py — read a GitHub release JSON on stdin, synthesize
the per-asset download URL, classify each asset, and emit a TSV
mirroring the output shape of `x eget classify --tsv`.

Output: one row per asset, 4 tab-separated columns:
    name<TAB>browser_download_url<TAB>size_bytes<TAB>target

where `target` is x-cmd's native-platform identifier (e.g.
`native/darwin/arm64`, `native/linux/x64`, `runtime/deb/x64`,
etc.). The classification rules here are a small, deliberate subset
of what x eget classify does — we only need the target column for
display, not for actual install decisions.

Usage:
    classify_assets.py <owner_repo> < input.json > output.tsv

We originally piped through `x eget classify --tsv`, but its awk
implementation crashes on certain GNU awk versions in GitHub
Actions runners with 'illegal reference to array tokens'. Doing
the tiny classification in Python is more portable and gives full
control over output shape.
"""
import json
import re
import sys


# Pre-compiled regex for asset name classification. Each pattern is
# (compiled_regex, target_string). The first match wins; an asset
# that matches none is reported as 'other'.
_CLASSIFIERS = [
    # Deb packages (Debian / Ubuntu). Names look like 'foo_1.2.3_amd64.deb'
    (re.compile(r"_(?P<arch>amd64|arm64|armhf|i386|riscv64|ppc64el|s390x)\.deb$"),
     lambda m: f"runtime/deb/{m.group('arch')}"),
    # RPM packages (Fedora / RHEL). Names like 'foo-1.2.3-1.x86_64.rpm'
    (re.compile(r"\.(?P<arch>x86_64|aarch64|armv7hl|i686|ppc64le|s390x)\.rpm$"),
     lambda m: f"runtime/rpm/{m.group('arch')}"),
    # tar.gz / tgz — most common Unix release artifact
    (re.compile(r"\.(tar\.gz|tgz|txz)$", re.I), "native/unknown"),
]


def classify_target(name):
    """Return the target platform identifier for an asset name."""
    n = name.lower()

    # Apple / macOS — distinguish arch
    if "darwin" in n or "macos" in n or "osx" in n:
        arch = "arm64" if ("aarch64" in n or "arm64" in n) else "x64"
        return f"native/darwin/{arch}"
    # Windows
    if "windows" in n or "win64" in n or "win32" in n or "msvc" in n:
        arch = "arm64" if "arm64" in n or "aarch64" in n else "x64"
        return f"native/win/{arch}"
    # Linux — distinguish arch + libc
    if "linux" in n or n.endswith((".tar.gz", ".tgz", ".txz", ".AppImage")):
        arch = "arm64" if ("aarch64" in n or "arm64" in n) else \
               "arm"   if "arm" in n else \
               "x64"   if ("x86_64" in n or "amd64" in n) else \
               "x86"   if ("i386" in n or "i686" in n) else \
               "riscv64" if "riscv" in n else \
               "unknown"
        if arch != "unknown":
            if "musl" in n:
                return f"native/linux/{arch}/musl"
            if "gnu" in n:
                return f"native/linux/{arch}/glibc"
            # No explicit libc hint — emit just arch.
            return f"native/linux/{arch}"

    # Fall through to other classifiers (deb / rpm)
    for pat, target in _CLASSIFIERS:
        m = pat.search(name)
        if m:
            return target(m) if callable(target) else target

    return "other"


def main():
    if len(sys.argv) != 2:
        print(f"usage: {sys.argv[0]} <owner_repo>", file=sys.stderr)
        sys.exit(2)
    owner_repo = sys.argv[1]

    data = json.load(sys.stdin)
    tag = data.get("tag_name", "")
    for a in data.get("assets", []):
        name = a.get("name", "")
        size = a.get("size", 0)
        url = f"https://github.com/{owner_repo}/releases/download/{tag}/{name}"
        target = classify_target(name)
        print(f"{name}\t{url}\t{size}\t{target}")


if __name__ == "__main__":
    main()
