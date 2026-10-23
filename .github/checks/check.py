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
import tempfile
import tomllib
from fnmatch import fnmatch
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=True).stdout.strip())
ALLOWED_ROOT = {"00-docs", "01-talos", "02-bootstrap", "03-cluster", "04-platform", "05-apps",
                ".claude", ".github", ".config", ".sops.yaml", ".gitignore"}
LIVING_DOCS = ["00-docs/architecture.md", "00-docs/conventions.md", "00-docs/runbooks/**", ".github/README.md"]
ADR_STATUSES = ("Accepted", "Proposed", "Deferred", "Superseded by ADR-", "Rejected")
ADR_SECTIONS = ("Context", "Decision", "Consequences", "Alternatives considered", "Compliance")
PR_TITLE_RE = re.compile(r"^(feat|fix|chore|docs|refactor|ci|revert)(\([a-z0-9./-]+\))?!?: \S.*$")
# A version string, but not part of a dotted quad (IPs, CIDRs).
VERSION_RE = re.compile(r"(?<![\d.])v?\d+\.\d+\.\d+(?![\d.])")
# Content fetched from a moving branch can change without any change in git (ADR-0033).
# Only fetchable content counts: raw files. github.com/.../blob/... links in CRD docs are web pages.
FLOATING_REF_RE = re.compile(r"(?:raw\.githubusercontent\.com/[^/\s]+/[^/\s]+|github\.com/[^/\s]+/[^/\s]+/raw)/(?:main|master|HEAD)/")
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


def yaml_docs(text):
    """All documents of a YAML stream (from a string), via yq, as Python objects."""
    out = subprocess.run(["yq", "-o=json", "-I=0", "."], input=text, capture_output=True, text=True, check=True).stdout
    return [json.loads(line) for line in out.splitlines() if line.strip() and line.strip() != "null"]


# Namespaces that upstream requires instead of the folder name (ADR-0003 rule 4).
NAMESPACE_EXCEPTIONS = {"cilium": "kube-system", "metrics-server": "kube-system",
                        "flux-operator": "flux-system", "flux-instance": "flux-system"}
COMPONENT_GLOBS = ["03-cluster/*/ks.yaml", "04-platform/*/*/ks.yaml", "05-apps/*/ks.yaml"]
KUBECONFORM = ["kubeconform", "-strict", "-summary", "-ignore-missing-schemas", "-schema-location", "default",
               "-schema-location", "https://raw.githubusercontent.com/datreeio/CRDs-catalog/main/{{.Group}}/{{.ResourceKind}}_{{.ResourceAPIVersion}}.json"]


def flux_kustomizations(files):
    """Every Flux Kustomization defined in git, plus the FluxInstance's root sync (path 03-cluster)."""
    found = [{"metadata": {"name": "flux-system"}, "spec": {"path": "./03-cluster"}}]
    for f in [f for g in COMPONENT_GLOBS for f in matches(g, files)] + matches("03-cluster/layers.yaml", files):
        found += [d for d in yaml_docs((ROOT / f).read_text()) if d.get("kind") == "Kustomization"]
    return found


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


def check_talos(files):
    """ADR-0028: cluster.yaml is consistent with the toolchain, its schematics and patch folders."""
    if "01-talos/cluster.yaml" not in files:
        return []
    cluster = yaml_load(ROOT / "01-talos/cluster.yaml")
    tools = tomllib.loads((ROOT / ".config/mise.toml").read_text())["tools"]
    errs = []
    if cluster["talosVersion"].lstrip("v") != tools["talosctl"]:
        errs.append(f"talosVersion {cluster['talosVersion']} != talosctl pin {tools['talosctl']} in .config/mise.toml")
    k8s_minor = int(cluster["kubernetesVersion"].lstrip("v").split(".")[1])
    kubectl_minor = int(tools["kubectl"].split(".")[1])
    if abs(k8s_minor - kubectl_minor) > 1:
        errs.append(f"kubectl {tools['kubectl']} is more than one minor from kubernetesVersion {cluster['kubernetesVersion']}")
    names = [n["name"] for n in cluster["nodes"]]
    errs += [f"node name '{n}' is not unique" for n in sorted({n for n in names if names.count(n) > 1})]
    for node in cluster["nodes"]:
        if node["role"] not in ("controlplane", "worker"):
            errs.append(f"node {node['name']}: role must be controlplane or worker")
        if f"01-talos/schematics/{node['schematic']}.yaml" not in files:
            errs.append(f"node {node['name']}: schematic file 01-talos/schematics/{node['schematic']}.yaml missing")
    for f in matches("01-talos/patches/*/*.yaml", files) + matches("01-talos/schematics/*.yaml", files):
        if subprocess.run(["yq", "-e", "true", str(ROOT / f)], capture_output=True).returncode != 0:
            errs.append(f"{f}: not valid YAML")
    return errs


TUPPR_UPGRADES = {"talosVersion": ("04-platform/05-operations/tuppr/app/upgrades/talos.yaml", "talos"),
                  "kubernetesVersion": ("04-platform/05-operations/tuppr/app/upgrades/kubernetes.yaml", "kubernetes")}


def check_versions_match(files):
    """ADR-0023: the versions in 01-talos/cluster.yaml equal the tuppr CRs that roll them out."""
    if "01-talos/cluster.yaml" not in files:
        return []
    cluster = yaml_load(ROOT / "01-talos/cluster.yaml")
    errs = []
    for key, (path, field) in TUPPR_UPGRADES.items():
        if path not in files:
            continue
        version = yaml_load(ROOT / path)["spec"][field]["version"]
        if version != cluster[key]:
            errs.append(f"{path}: spec.{field}.version {version} != {key} {cluster[key]} in 01-talos/cluster.yaml")
    return errs


def check_component_shape(files):
    errs = []
    for ks in [f for g in COMPONENT_GLOBS for f in matches(g, files)]:
        comp_dir = str(Path(ks).parent)
        comp = Path(comp_dir).name
        entries = {f[len(comp_dir) + 1:].split("/")[0] for f in files if f.startswith(comp_dir + "/")}
        if extra := entries - {"ks.yaml", "app", "image"}:
            errs.append(f"{comp_dir}: only ks.yaml, app/ and image/ are allowed (found {sorted(extra)})")
        if f"{comp_dir}/app/kustomization.yaml" not in files:
            errs.append(f"{comp_dir}: missing app/kustomization.yaml")
        for k in [d for d in yaml_docs((ROOT / ks).read_text()) if d.get("kind") == "Kustomization"]:
            name, meta = k["metadata"]["name"], k["metadata"]
            missing = [a for a in ("olympus/description", "olympus/docs", "olympus/adr") if a not in meta.get("annotations", {})]
            if missing:
                errs.append(f"{ks}: Kustomization {name} lacks annotations {missing}")
            if meta.get("namespace") != "flux-system":
                errs.append(f"{ks}: Kustomization {name} must live in namespace flux-system")
            if not k["spec"]["path"].startswith(f"./{comp_dir}/app"):
                errs.append(f"{ks}: Kustomization {name} path must point into ./{comp_dir}/app")
            for doc in meta.get("annotations", {}).get("olympus/docs", "").split(","):
                if doc.strip() and doc.strip() not in files:
                    errs.append(f"{ks}: olympus/docs path {doc.strip()} does not exist")
        ns_file = ROOT / comp_dir / "app/namespace.yaml"
        namespaces = {d.get("spec", {}).get("targetNamespace") for d in yaml_docs((ROOT / ks).read_text())} - {None}
        if ns_file.exists():
            namespaces.add(yaml_load(ns_file)["metadata"]["name"])
        for ns in namespaces:
            if ns != NAMESPACE_EXCEPTIONS.get(comp, comp):
                errs.append(f"{comp_dir}: namespace {ns} must equal the folder name ({comp}) (ADR-0003 rule 4)")
    return errs


LOCK_PLATFORMS = ("linux-x64", "macos-arm64", "macos-x64")


def check_mise_lock(files):
    """ADR-0006/ADR-0038: .config/mise.lock pins every tool version in mise.toml, for every platform."""
    tools = tomllib.loads((ROOT / ".config/mise.toml").read_text())["tools"]
    lock = tomllib.loads((ROOT / ".config/mise.lock").read_text()).get("tools", {})
    errs = []
    for name, version in tools.items():
        entry = next((e for e in lock.get(name, []) if e.get("version") == version), None)
        if entry is None:
            errs.append(f"{name} {version} is not in .config/mise.lock: run `mise lock --platform {','.join(LOCK_PLATFORMS)}`")
            continue
        missing = [pl for pl in LOCK_PLATFORMS if f"platforms.{pl}" not in entry]
        if missing:
            errs.append(f"{name} {version}: .config/mise.lock has no checksum for {', '.join(missing)}: run `mise lock --platform {','.join(LOCK_PLATFORMS)}`")
    return errs


def check_orphans(files):
    errs = []
    def listed(kustomization):
        return set(yaml_load(ROOT / kustomization).get("resources", []))
    for group in sorted({str(Path(f).parent.parent) for f in matches("04-platform/*/*/ks.yaml", files)}):
        want = {f"{Path(f).parent.name}/ks.yaml" for f in matches(f"{group}/*/ks.yaml", files)}
        have = listed(f"{group}/kustomization.yaml") if f"{group}/kustomization.yaml" in files else set()
        errs += [f"{group}/kustomization.yaml: {r} is not listed" for r in sorted(want - have)]
        errs += [f"{group}/kustomization.yaml: {r} does not exist" for r in sorted(have - want)]
        layer = f"layer-{Path(group).name}"
        if "03-cluster/layers.yaml" not in files or not any(
                k["metadata"]["name"] == layer and k["spec"]["path"] == f"./{group}"
                for k in yaml_docs((ROOT / "03-cluster/layers.yaml").read_text())):
            errs.append(f"03-cluster/layers.yaml: no Kustomization {layer} with path ./{group}")
    if "03-cluster/kustomization.yaml" in files:
        want = {f"{Path(f).parent.name}/ks.yaml" for f in matches("03-cluster/*/ks.yaml", files)}
        errs += [f"03-cluster/kustomization.yaml: {r} is not listed" for r in sorted(want - listed("03-cluster/kustomization.yaml"))]
    return errs


def check_bootstrap_literals(files):
    errs = []
    for f in matches("02-bootstrap/*", files):
        for n, line in enumerate((ROOT / f).read_text().splitlines(), 1):
            if re.match(r"^\s*(version|chart):\s*[^{\s]", line):
                errs.append(f"{f}:{n}: literal '{line.strip()}': versions and charts must come from ocirepository.yaml (ADR-0015)")
    return errs


ATHENA_EGRESS = "04-platform/06-agent/athena/app/networkpolicy.yaml"


def check_athena_egress(files):
    """ADR-0035: every chart source is in Athena's egress allow list, so `mise run check` works in its pod."""
    if ATHENA_EGRESS not in files:
        return []
    allowed = [f.get("matchName") or f.get("matchPattern")
               for doc in yaml_docs((ROOT / ATHENA_EGRESS).read_text())
               for rule in doc["spec"].get("egress", []) for f in rule.get("toFQDNs", [])]
    errs = []
    for f in [f for f in files if re.match(r"0[0-9]-.*\.yaml$", f)]:
        text = (ROOT / f).read_text()
        if not re.search(r"^kind: (OCIRepository|HelmRepository|GitRepository)$", text, re.M):
            continue
        for doc in yaml_docs(text):
            if doc.get("kind") in ("OCIRepository", "HelmRepository", "GitRepository"):
                host = urlparse(doc["spec"]["url"]).hostname
                if not any(fnmatch(host, a) for a in allowed):
                    errs.append(f"{f}: chart source {host} is missing from {ATHENA_EGRESS} (ADR-0035)")
    return errs


def check_render(files):
    """kustomize build every Flux path, substitute ${VARS}, validate; helm template every HelmRelease."""
    if "03-cluster/kustomization.yaml" not in files:
        return []
    errs, used = [], set()
    settings = yaml_load(ROOT / "03-cluster/cluster-settings.yaml")["data"]
    kube_version = yaml_load(ROOT / "01-talos/cluster.yaml")["kubernetesVersion"].lstrip("v")
    rendered = []
    for k in flux_kustomizations(files):
        path = k["spec"]["path"].lstrip("./")
        build = subprocess.run(["kustomize", "build", str(ROOT / path)], capture_output=True, text=True)
        if build.returncode:
            errs.append(f"kustomize build {path}: {build.stderr.strip().splitlines()[-1]}")
            continue
        def substitute(m):
            used.add(m.group(1))
            if m.group(1) not in settings:
                errs.append(f"{path}: ${{{m.group(1)}}} is not defined in 03-cluster/cluster-settings.yaml")
            return settings.get(m.group(1), "")
        text = re.sub(r"\$\{([A-Z0-9_]+)\}", substitute, build.stdout)
        errs += [f"{path}: floating ref {m.group(0)} (pin a tag or commit, ADR-0033)" for m in FLOATING_REF_RE.finditer(text)]
        rendered.append((path, k.get("spec", {}).get("targetNamespace"), text))
    errs += [f"cluster-settings: {v} is defined but never used" for v in sorted(set(settings) - used)]
    for path, target_ns, text in rendered:
        # validate what Flux applies: the sops block is removed when Flux decrypts a Secret
        text = subprocess.run(["yq", "del(.sops)"], input=text, capture_output=True, text=True, check=True).stdout
        check = subprocess.run(KUBECONFORM, input=text, capture_output=True, text=True)
        if check.returncode:
            errs += [f"{path}: {l}" for l in check.stdout.splitlines() if "is invalid" in l or "failed" in l.lower()][:10]
        docs = yaml_docs(text)
        # ADR-0031: the default-StorageClass admission plugin fills this in before any policy runs,
        # so explicitness can only be enforced here, in git.
        for d in docs:
            claims = [d] if d.get("kind") == "PersistentVolumeClaim" else (
                d.get("spec", {}).get("volumeClaimTemplates", []) if d.get("kind") == "StatefulSet" else [])
            errs += [f"{path}: PVC {c.get('metadata', {}).get('name')} must set spec.storageClassName (ADR-0016)"
                     for c in claims if not c.get("spec", {}).get("storageClassName")]
        oci = {d["metadata"]["name"]: d for d in docs if d.get("kind") == "OCIRepository"}
        repos = {d["metadata"]["name"]: d for d in docs if d.get("kind") == "HelmRepository"}
        gits = {d["metadata"]["name"]: d for d in docs if d.get("kind") == "GitRepository"}
        for hr in [d for d in docs if d.get("kind") == "HelmRelease"]:
            name, spec = hr["metadata"]["name"], hr["spec"]
            if "chartRef" in spec and spec["chartRef"]["name"] in oci:  # OCI chart (preferred, ADR-0013)
                src = oci[spec["chartRef"]["name"]]["spec"]
                chart = [src["url"], "--version", src["ref"]["tag"]]
            elif spec.get("chart", {}).get("spec", {}).get("sourceRef", {}).get("name") in repos:  # classic Helm repository
                cs = spec["chart"]["spec"]
                chart = [cs["chart"], "--repo", repos[cs["sourceRef"]["name"]]["spec"]["url"], "--version", cs["version"]]
            elif spec.get("chart", {}).get("spec", {}).get("sourceRef", {}).get("name") in gits:  # chart inside a git tag
                cs, git = spec["chart"]["spec"], gits[spec["chart"]["spec"]["sourceRef"]["name"]]["spec"]
                checkout = tempfile.mkdtemp(prefix="olympus-chart-")
                subprocess.run(["git", "-c", "advice.detachedHead=false", "clone", "-q", "--depth", "1", "--branch", git["ref"]["tag"], git["url"], checkout], check=True)
                chart = [str(Path(checkout) / cs["chart"])]
            else:
                errs.append(f"{path}: HelmRelease {name} has no OCI/Helm/Git repository source in the same folder")
                continue
            ns = target_ns or hr["metadata"].get("namespace", "default")
            tpl = subprocess.run(["helm", "template", name, *chart, "--namespace", ns, "--kube-version", kube_version,
                                  "--include-crds", "-f", "-"],
                                 input=json.dumps(spec.get("values", {})), capture_output=True, text=True)
            if tpl.returncode:
                errs.append(f"{path}: helm template {name}: {tpl.stderr.strip().splitlines()[-1]}")
                continue
            errs += [f"{path} (helm {name}): floating ref {m.group(0)} (pin a tag or commit, ADR-0033)" for m in FLOATING_REF_RE.finditer(tpl.stdout)]
            # Flux post-renders every chart through kustomize, which rejects e.g. duplicate keys that helm lets through
            post = tempfile.mkdtemp(prefix="olympus-post-")
            (Path(post) / "out.yaml").write_text(tpl.stdout)
            (Path(post) / "kustomization.yaml").write_text("resources: [out.yaml]\n")
            kz = subprocess.run(["kustomize", "build", post], capture_output=True, text=True)
            if kz.returncode:
                errs.append(f"{path} (helm {name}): post-render (kustomize) fails: {kz.stderr.strip().splitlines()[-1]}")
            check = subprocess.run(KUBECONFORM, input=tpl.stdout, capture_output=True, text=True)
            if check.returncode:
                errs += [f"{path} (helm {name}): {l}" for l in check.stdout.splitlines() if "is invalid" in l][:10]
    return errs


def check_sops_encrypted(files):
    """ADR-0014: every *.sops.yaml is encrypted; no plaintext Secret lives anywhere else."""
    errs = []
    for f in [f for f in files if f.endswith(".sops.yaml") and Path(f).name != ".sops.yaml"]:  # not the sops config
        text = (ROOT / f).read_text()
        if not re.search(r"^sops:", text, re.M) or "mac: ENC[" not in text:
            errs.append(f"{f}: not SOPS-encrypted (no sops metadata/mac)")
            continue
        if not f.startswith("01-talos/"):
            for doc in yaml_docs(text):
                for field in ("data", "stringData"):
                    plain = [k for k, v in (doc.get(field) or {}).items() if not str(v).startswith("ENC[")]
                    if plain:
                        errs.append(f"{f}: {field} keys {plain} are not encrypted")
    for f in [f for f in files if f.endswith((".yaml", ".yml")) and not f.endswith(".sops.yaml")]:
        if re.search(r"^kind:\s*Secret\s*$", (ROOT / f).read_text(), re.M):
            errs.append(f"{f}: a Secret must live in a *.sops.yaml file (ADR-0014)")
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
    assert FLOATING_REF_RE.search("https://raw.githubusercontent.com/a/b/main/x.yaml")
    assert FLOATING_REF_RE.search("https://raw.githubusercontent.com/a/b/master/x.json")
    assert not FLOATING_REF_RE.search("https://raw.githubusercontent.com/a/b/v1.2.3/x.yaml")
    assert not FLOATING_REF_RE.search("see https://github.com/grpc/grpc/blob/master/doc/health.md")
    assert not FLOATING_REF_RE.search("https://raw.githubusercontent.com/a/b/6599fbd7ce10924377a7b1d113281c7ae7c03043/x.json")
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
        "talos": check_talos(files),
        "versions-match": check_versions_match(files),
        "component-shape": check_component_shape(files),
        "orphans": check_orphans(files),
        "mise-lock": check_mise_lock(files),
        "bootstrap-literals": check_bootstrap_literals(files),
        "render": check_render(files),
        "athena-egress": check_athena_egress(files),
        "sops-encrypted": check_sops_encrypted(files),
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
