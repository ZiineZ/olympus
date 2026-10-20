#!/usr/bin/env python3
"""Olympus repo checks (ADR-0004). Python stdlib only; YAML is read through the pinned `yq`.

  check.py             repo checks (also run on every push to main)
  check.py --pr        repo checks + PR checks (needs env BASE_REF, PR_TITLE, PR_BODY)
  check.py --selftest  assert-based self-test of the matching logic

ADR-0004 lists the full target set of checks. Each check is added here in the PR that adds
the first thing it checks (e.g. `component-shape` arrives with the first component).
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=True).stdout.strip())
ALLOWED_ROOT = {"00-docs", "01-talos", "02-bootstrap", "03-cluster", "04-platform", "05-apps",
                ".claude", ".github", ".config", ".sops.yaml", ".gitignore"}
LIVING_DOCS = ["00-docs/architecture.md", "00-docs/conventions.md", "00-docs/runbooks/**", ".github/README.md"]
ADR_STATUSES = ("Accepted", "Proposed", "Deferred", "Superseded by ADR-", "Rejected")
ADR_SECTIONS = ("Context", "Decision", "Consequences", "Alternatives considered", "Compliance")
PR_TITLE_RE = re.compile(r"^(feat|fix|chore|docs|refactor|ci|revert)(\([a-z0-9./-]+\))?!?: \S.*$")
# A version string, but not part of a dotted quad (IPs, CIDRs).
VERSION_RE = re.compile(r"(?<![\d.])v?\d+\.\d+\.\d+(?![\d.])")
ESCAPE_RE = re.compile(r"^No doc change:\s*`?([^`\s]+)`?\s+(?:—|--|-)\s+\S", re.M)


def glob_re(pattern):
    """`*` = within one path segment, `**` = any depth (including none)."""
    out, i = "", 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out, i = out + "(?:.*/)?", i + 3
        elif pattern.startswith("**", i):
            out, i = out + ".*", i + 2
        elif pattern[i] == "*":
            out, i = out + "[^/]*", i + 1
        else:
            out, i = out + re.escape(pattern[i]), i + 1
    return re.compile(out + r"\Z")


def matches(pattern, paths):
    rx = glob_re(pattern)
    return [p for p in paths if rx.match(p)]


def tracked():
    out = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    return sorted({p for p in out.split("\0") if p and (ROOT / p).exists()})


def yaml_load(path):
    out = subprocess.run(["yq", "-o=json", ".", str(path)], capture_output=True, text=True, check=True).stdout
    return json.loads(out)


# --- repo checks -------------------------------------------------------------------------

def check_root_clean(files):
    extra = sorted({f.split("/")[0] for f in files} - ALLOWED_ROOT)
    return [f"{e}: not allowed at the repo root (ADR-0003 rule 1)" for e in extra]


def check_adr_format(files):
    errs, numbers = [], []
    for f in matches("00-docs/decisions/*.md", files):
        name = Path(f).name
        m = re.match(r"^(\d{4})-[a-z0-9]+(?:-[a-z0-9]+)*\.md$", name)
        if not m:
            errs.append(f"{f}: file name must be NNNN-kebab-case.md")
            continue
        numbers.append(int(m.group(1)))
        text = (ROOT / f).read_text()
        if not text.startswith(f"# ADR-{m.group(1)}: "):
            errs.append(f"{f}: first line must be '# ADR-{m.group(1)}: <title>'")
        for field in ("Status", "Date", "Deciders", "Related"):
            if not re.search(rf"^- \*\*{field}:\*\* \S", text, re.M):
                errs.append(f"{f}: missing header field '{field}'")
        status = re.search(r"^- \*\*Status:\*\* (.+)$", text, re.M)
        if status and not status.group(1).startswith(ADR_STATUSES):
            errs.append(f"{f}: status '{status.group(1)}' not one of {ADR_STATUSES}")
        for section in ADR_SECTIONS:
            if not re.search(rf"^## {section}\s*$", text, re.M):
                errs.append(f"{f}: missing section '## {section}'")
    if numbers and sorted(numbers) != list(range(len(numbers))):
        errs.append(f"ADR numbers must be 0000..{len(numbers) - 1:04d} without gaps or duplicates")
    return errs


def strip_code(text):
    return re.sub(r"^```.*?^```", "", text, flags=re.M | re.S)


def check_doc_links(files):
    errs, present = [], set(files) | {str(Path(f).parent) for f in files}
    for f in [f for f in files if f.endswith(".md")]:
        for target in re.findall(r"\]\(([^)\s]+)\)", strip_code((ROOT / f).read_text())):
            target = target.split("#")[0]
            if not target or re.match(r"^[a-z]+:", target):
                continue
            resolved = os.path.normpath(os.path.join(os.path.dirname(f), target))
            if resolved not in present:
                errs.append(f"{f}: broken link -> {target}")
    return errs


def check_no_versions_in_docs(files):
    errs = []
    for pattern in LIVING_DOCS:
        for f in matches(pattern, files):
            for n, line in enumerate((ROOT / f).read_text().splitlines(), 1):
                for v in VERSION_RE.findall(line):
                    errs.append(f"{f}:{n}: version string '{v}' in a living doc (versions live in manifests)")
    return errs


# --- PR checks ---------------------------------------------------------------------------

def changed_files(base):
    out = subprocess.run(["git", "diff", "--name-status", "--no-renames", f"origin/{base}...HEAD"],
                         cwd=ROOT, capture_output=True, text=True, check=True).stdout
    changes = {"A": set(), "M": set(), "D": set()}
    for line in out.splitlines():
        status, path = line.split("\t", 1)
        changes.setdefault(status[0], set()).add(path)
    return changes


def check_sync_rules(changes, body):
    rules = yaml_load(ROOT / ".github/sync-rules.yaml")["rules"]
    every = set().union(*changes.values())
    escaped = set(ESCAPE_RE.findall(body or ""))
    errs = []
    for rule in rules:
        hit = (any(matches(p, every) for p in rule.get("when", []))
               or any(matches(p, changes["A"]) for p in rule.get("when_added", []))
               or any(matches(p, changes["D"]) for p in rule.get("when_removed", [])))
        if not hit:
            continue
        for req in rule.get("require", []):
            if not matches(req, every) and req not in escaped:
                errs.append(f"rule '{rule['name']}': PR must also change {req} (or add 'No doc change: {req} — <reason>')")
        anyof = rule.get("require_any", [])
        if anyof and not any(matches(r, every) for r in anyof) and not escaped & set(anyof):
            errs.append(f"rule '{rule['name']}': PR must also change one of {anyof} (or justify one with 'No doc change:')")
    return errs


def check_pr_title(title):
    if PR_TITLE_RE.match(title or ""):
        return []
    return [f"PR title '{title}' is not a Conventional Commit: type(scope): summary (ADR-0005)"]


# --- runner ------------------------------------------------------------------------------

def selftest():
    assert glob_re("04-platform/*/*/ks.yaml").match("04-platform/01-network/cilium/ks.yaml")
    assert not glob_re("04-platform/*/*/ks.yaml").match("04-platform/01-network/cilium/app/ks.yaml")
    assert glob_re("01-talos/**").match("01-talos/patches/global/a.yaml")
    assert glob_re("00-docs/runbooks/**").match("00-docs/runbooks/01-talos.md")
    assert glob_re("a/**/b.md").match("a/b.md") and glob_re("a/**/b.md").match("a/x/y/b.md")
    assert VERSION_RE.findall("Talos v1.14.4 and 2.9.6") == ["v1.14.4", "2.9.6"]
    assert VERSION_RE.findall("LAN 192.168.50.0/24, pods 10.244.0.0/16, date 2026-10-20") == []
    assert ESCAPE_RE.findall("x\nNo doc change: `00-docs/architecture.md` — only a typo\n") == ["00-docs/architecture.md"]
    assert ESCAPE_RE.findall("No doc change: 00-docs/architecture.md\n") == []  # a reason is mandatory
    assert PR_TITLE_RE.match("feat(kite)!: add tailnet ingress") and PR_TITLE_RE.match("chore(deps): update x")
    assert not PR_TITLE_RE.match("Add stuff")
    print("selftest ok")


def main():
    if "--selftest" in sys.argv:
        return selftest()
    files = tracked()
    results = {
        "root-clean": check_root_clean(files),
        "adr-format": check_adr_format(files),
        "doc-links": check_doc_links(files),
        "no-versions-in-docs": check_no_versions_in_docs(files),
    }
    if "--pr" in sys.argv:
        results["sync-rules"] = check_sync_rules(changed_files(os.environ["BASE_REF"]), os.environ.get("PR_BODY", ""))
        results["pr-title"] = check_pr_title(os.environ.get("PR_TITLE", ""))
    gha = os.environ.get("GITHUB_ACTIONS") == "true"
    for name, errs in results.items():
        print(f"{'✘' if errs else '✔'} {name}")
        for e in errs:
            print(f"::error title={name}::{e}" if gha else f"    {e}")
    sys.exit(1 if any(results.values()) else 0)


if __name__ == "__main__":
    main()
