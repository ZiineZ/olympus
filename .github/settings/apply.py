#!/usr/bin/env python3
"""Make the GitHub repo match .github/settings/ (ADR-0005 rule 8). Python stdlib + `gh`.

  apply.py diff    report drift, exit 1 if any
  apply.py apply   push the settings to GitHub (needs an admin token: Stan)

Only keys present in the files are compared, so GitHub's extra read-only fields never count as drift.
"""
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
SETTINGS = json.loads((HERE / "settings.json").read_text())
RULESETS = [json.loads(p.read_text()) for p in sorted((HERE / "rulesets").glob("*.json"))]


def gh(method, path, body=None, missing_ok=False):
    cmd = ["gh", "api", "-X", method, path, "-H", "Accept: application/vnd.github+json"]
    if body is not None:
        cmd += ["--input", "-"]
    r = subprocess.run(cmd, input=None if body is None else json.dumps(body), capture_output=True, text=True)
    if r.returncode != 0:
        # 404: feature off (e.g. vulnerability alerts); 409: selected-actions while all actions are allowed;
        # 403/422: feature unavailable at the current visibility (code scanning, fork approval on a private repo)
        status = json.loads(r.stdout).get("status") if r.stdout.startswith("{") else None
        if missing_ok and (status in ("403", "404", "409", "422") or "HTTP 404" in r.stderr):
            return None
        sys.exit(f"gh api {method} {path} failed:\n{r.stdout}{r.stderr}")
    return json.loads(r.stdout) if r.stdout.strip() else {}


def diff(want, have, path=""):
    if isinstance(want, dict):
        if not isinstance(have, dict):
            return [f"{path}: want {want!r}, have {have!r}"]
        return [d for k, v in want.items() for d in diff(v, have.get(k), f"{path}.{k}")]
    if isinstance(want, list) and want and isinstance(want[0], dict):
        if not isinstance(have, list) or len(want) != len(have):
            return [f"{path}: want {len(want)} items, have {have!r}"]
        return [d for i, (w, h) in enumerate(zip(want, have)) for d in diff(w, h, f"{path}[{i}]")]
    if isinstance(want, list):
        return [] if sorted(want) == sorted(have or []) else [f"{path}: want {sorted(want)}, have {sorted(have or [])}"]
    return [] if want == have else [f"{path}: want {want!r}, have {have!r}"]


def by_type(ruleset):
    return {**ruleset, "rules": sorted(ruleset.get("rules", []), key=lambda r: r["type"])}


def live(repo):
    """Current state, shaped like settings.json + rulesets."""
    labels = gh("GET", f"/repos/{repo}/labels?per_page=100")
    fixes = gh("GET", f"/repos/{repo}/automated-security-fixes", missing_ok=True) or {}
    rulesets = {}
    for summary in gh("GET", f"/repos/{repo}/rulesets?includes_parents=false"):
        rulesets[summary["name"]] = gh("GET", f"/repos/{repo}/rulesets/{summary['id']}")
    info = gh("GET", f"/repos/{repo}")
    pvr = gh("GET", f"/repos/{repo}/private-vulnerability-reporting", missing_ok=True) or {}
    return {
        "repo": info,
        "security_and_analysis": info.get("security_and_analysis"),
        "code_scanning_default_setup": gh("GET", f"/repos/{repo}/code-scanning/default-setup", missing_ok=True),
        "private_vulnerability_reporting": bool(pvr.get("enabled", False)),
        "fork_pr_approval": gh("GET", f"/repos/{repo}/actions/permissions/fork-pr-contributor-approval", missing_ok=True),
        "topics": gh("GET", f"/repos/{repo}/topics")["names"],
        "actions": gh("GET", f"/repos/{repo}/actions/permissions"),
        "selected_actions": gh("GET", f"/repos/{repo}/actions/permissions/selected-actions", missing_ok=True),
        "workflow_permissions": gh("GET", f"/repos/{repo}/actions/permissions/workflow"),
        "vulnerability_alerts": gh("GET", f"/repos/{repo}/vulnerability-alerts", missing_ok=True) is not None,
        "automated_security_fixes": bool(fixes.get("enabled", False)),
        "labels": sorted(({k: l[k] for k in ("name", "color", "description")} for l in labels), key=lambda l: l["name"]),
        "rulesets": rulesets,
    }


def report(repo):
    have = live(repo)
    want = {**SETTINGS, "labels": sorted(SETTINGS["labels"], key=lambda l: l["name"])}
    drift = [d for k, v in want.items() for d in diff(v, have[k], k)]
    for rs in RULESETS:
        current = have["rulesets"].get(rs["name"])
        drift += [f"ruleset {rs['name']}: missing"] if current is None else diff(by_type(rs), by_type(current), f"ruleset {rs['name']}")
    drift += [f"ruleset {name}: not in git" for name in have["rulesets"].keys() - {r["name"] for r in RULESETS}]
    return drift, have


def apply(repo, have):
    s = SETTINGS
    gh("PATCH", f"/repos/{repo}", s["repo"])  # visibility first: the features below depend on it
    gh("PATCH", f"/repos/{repo}", {"security_and_analysis": s["security_and_analysis"]})
    gh("PATCH", f"/repos/{repo}/code-scanning/default-setup", s["code_scanning_default_setup"])
    gh("PUT" if s["private_vulnerability_reporting"] else "DELETE", f"/repos/{repo}/private-vulnerability-reporting")
    gh("PUT", f"/repos/{repo}/actions/permissions/fork-pr-contributor-approval", s["fork_pr_approval"])
    gh("PUT", f"/repos/{repo}/topics", {"names": s["topics"]})
    gh("PUT", f"/repos/{repo}/actions/permissions", s["actions"])
    gh("PUT", f"/repos/{repo}/actions/permissions/selected-actions", s["selected_actions"])
    gh("PUT", f"/repos/{repo}/actions/permissions/workflow", s["workflow_permissions"])
    gh("PUT" if s["vulnerability_alerts"] else "DELETE", f"/repos/{repo}/vulnerability-alerts")
    gh("PUT" if s["automated_security_fixes"] else "DELETE", f"/repos/{repo}/automated-security-fixes")
    want_labels = {l["name"]: l for l in s["labels"]}
    for label in have["labels"]:
        if label["name"] not in want_labels:
            gh("DELETE", f"/repos/{repo}/labels/{label['name']}")
    have_names = {l["name"] for l in have["labels"]}
    for name, label in want_labels.items():
        if name in have_names:
            gh("PATCH", f"/repos/{repo}/labels/{name}", label)
        else:
            gh("POST", f"/repos/{repo}/labels", label)
    for rs in RULESETS:
        current = have["rulesets"].get(rs["name"])
        if current:
            gh("PUT", f"/repos/{repo}/rulesets/{current['id']}", rs)
        else:
            gh("POST", f"/repos/{repo}/rulesets", rs)


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "diff"
    repo = subprocess.run(["gh", "repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"],
                          capture_output=True, text=True, check=True).stdout.strip()
    drift, have = report(repo)
    if mode == "apply" and drift:
        apply(repo, have)
        drift, _ = report(repo)
    for d in drift:
        print(f"drift: {d}")
    print(f"{repo}: {'in sync' if not drift else f'{len(drift)} difference(s)'}")
    sys.exit(1 if drift else 0)


if __name__ == "__main__":
    main()
