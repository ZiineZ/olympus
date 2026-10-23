---
name: change
description: Mandatory workflow for ANY modification to the Olympus repo, whether manifests, Helm values, Talos config, docs, ADRs, skills, CI or Renovate config, including one-line fixes. Use it before editing a single file. It finds every related file that must change in the same PR (config, dependents, docs, ADRs, skills), makes the edits in the right order, runs the checks and opens a correctly formatted PR. Nothing is ever left ahead of or behind the rest.
---

# The change workflow

**Goal: a PR in which every related file has changed together.** CI (`mise run check` + `.github/sync-rules.yaml`) blocks the merge otherwise. Follow the steps in order, and don't skip any because a change looks small.

> **Early phases:** if a `mise run …` task named here isn't implemented yet, do its manual equivalent. List what you did under **How verified**, and say that the task was missing.

## 0. Scope it

- **One concern per PR.** If the request covers two concerns, split it and tell Stan.
- Start from fresh `main`: `git fetch origin && git switch -c athena/<type>/<slug> origin/main`. `type` is a Conventional Commit type (ADR-0005). Stan uses the `stan/` prefix instead.

## 1. Understand before touching anything

- Read every file you expect to change, in full.
- Read the component's `ks.yaml` annotations:
  - `olympus/docs`: docs that must co-change
  - `olympus/adr`: decisions that govern it
- Read those ADRs.
- Trace the real flow. Ask what consumes this, and what this consumes. Think about service names, ports, labels, `${VAR}`s, dependsOn, routes, policies, and dashboards.

## 2. Impact scan: find ALL related files

Run `mise run impact paths="<every path you plan to touch>"`. **Then always do the manual sweep below as well.** The tool can't know everything.

```bash
# Every mention of the component, its service name, old values you're changing, ports, labels
grep -rn --exclude-dir=.git -e '<component>' -e '<old-value>' -e '<service-name>' .
# Every Kustomization that depends on it
grep -rn 'dependsOn' -A3 --include=ks.yaml . | grep -B1 '<component>'
```

Walk this checklist, which defines what "related" means. Mark every item **changed** or **not affected — why**:

| # | Category | Look at |
|---|---|---|
| a | The component itself | `helmrelease.yaml` (values inline), `ocirepository.yaml`, `*.sops.yaml`, `namespace.yaml`, network policies, ServiceMonitors, alert rules, dashboards |
| b | Dependents | other `ks.yaml` with `dependsOn` on it; HTTPRoutes and Gateways; network policies allowing it; Kite `prometheusURL`; Grafana datasources; Athena's egress policy; anything using its service DNS name or port |
| c | Shared cluster primitives | `03-cluster/cluster-settings.yaml` (a new or renamed `${VAR}`?), `priority-classes.yaml`, `components/`, admission policies (does the change pass them, or need an exception?) |
| d | Node level | `01-talos/cluster.yaml`, `01-talos/patches/` (sysctls, kubelet, extensions, scrape bind addresses) |
| e | Bootstrap | Is the component bootstrapped (cilium, flux-operator, flux-instance, Gateway API CRDs)? If so, `02-bootstrap/` reads its files; check that it still renders |
| f | Upgrades | `.github/renovate.json5`: groups, auto-merge set, regex managers (a new version location needs a manager or a `# renovate:` hint, ADR-0038); image blocks written `repository` + `tag@digest`; the tuppr CRs vs `01-talos/cluster.yaml` (`versions-match`) |
| g | CI and checks | `.github/checks/`, `.github/sync-rules.yaml`, `.github/workflows/` (you can't edit workflows: write the patch into the PR description for Stan) |
| h | Living docs | `.github/README.md` (front page: stack mind map, roadmap), `00-docs/architecture.md` (which section?), `00-docs/conventions.md`, `00-docs/runbooks/*`, and the paths in `olympus/docs`. `00-docs/inventory.md` is never edited by hand; regenerate it. |
| i | Decisions | Does this need an ADR? (ADR-0000 §2: a new tool/chart/CRD/external service, a changed convention/default/addressing/security boundary/workflow.) Does it supersede one? Does it adopt an item from the deferred register (ADR-0026)? |
| j | Agent config | `.claude/CLAUDE.md`, any `.claude/skills/*/SKILL.md` that names the thing, `.claude/settings.json` |
| k | Outside git | GitHub repo settings and rulesets (they're in git: `.github/settings/`; Stan applies them), the tailnet policy (it's in git: `tailscale/tailnet-policy.hujson`), Cloudflare Access (runbook), GitHub settings (runbook). Add a step for Stan in the PR if any of these must change. |

Write the result as the **Impact checklist** for the PR body.

## 3. Edit, in this order

1. **Config:** the manifests and values.
2. **Generated files:** `mise run docs:gen`.
3. **Living docs:** describe the *new current state*. Never write version numbers in living docs.
4. **ADR:** a new file if needed (ADR-0000 format). Never edit an Accepted ADR except to set `Status: Superseded by ADR-XXXX`.
5. **Skills and CLAUDE.md:** if they reference anything you changed.

Rules while editing:
- **Smallest diff.** Match the style of the surrounding files.
- **Copy shapes from existing components.** Never write a manifest from memory.
- **Pin versions** (`tag@sha256:` for images).
- Set **requests + memory limit = request, and no CPU limit**.

## 4. Verify

```bash
mise run check        # render, schemas, policies, shape, orphans, substitutions, sops, docs, sync rules, inventory
```

- Read the flate/render diff for the Kustomizations you touched. The rendered result must contain exactly the change you intended, and nothing more.
- For anything checks can't see (upstream changelog, chart behavior, the live cluster state you compared against), say under **How verified** how you confirmed it.
- If `check` fails, fix the cause. Never add a `No doc change:` line just to get past a sync rule that is actually right.

## 5. Commit and open the PR

```bash
git add -A && git commit -m "<type>(<scope>): <summary>"
git push -u origin HEAD
gh pr create --fill-first --body-file <(cat <<'EOF'
## Why
<the problem, in plain words; link the issue/alert/ADR>

## What changed
<bullets; one concern>

## Impact checklist
- [x] a. component: …
- [x] b. dependents: … / not affected: <why>
- … (all of a–k)

No doc change: <path> — <reason>      # only if needed, one line per path

## How verified
- `mise run check` ✅
- <render diff reviewed / changelog read / live state compared>

## Learn more
- <upstream doc links that explain the concepts touched>
EOF
)
```

The PR title must be a valid Conventional Commit. Explain for a Kubernetes beginner: define any new term in one sentence.

## 6. After Stan merges

Verify the rollout, read-only:

```bash
flux get kustomizations -A | grep -v True
flux get helmreleases -A | grep -v True
kubectl get events -n <ns> --sort-by=.lastTimestamp | tail
```

Report the result to Stan. If it failed, **don't improvise live**. Diagnose with the `debug` skill, then open a fix PR, or recommend `git revert` of the merge commit as a PR.

## Hard stops

Never do any of these:
- push to `main`, or force-push a shared branch
- bundle unrelated changes
- skip `mise run check`
- hand-edit `inventory.md`
- decrypt a `*.sops.yaml`
- add a tool, chart, or operator Stan didn't ask for
- leave a doc describing the old state
