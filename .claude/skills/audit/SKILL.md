---
name: audit
description: Periodic read-only review of the Olympus cluster and repo covering drift, health, repo hygiene, security posture, resource rightsizing, backups and restore drills, docs-vs-reality, deferred-decision triggers and GitHub settings. Use when Stan asks for an audit, a cleanup, a health check, "what should we improve?", a weekly or monthly review, or when the olympus skill notices something stale. It only reports, as a GitHub issue or a chat report, with each finding mapped to a proposed PR or a Stan action. It never fixes anything itself.
---

# Audit (report only)

**Output:** a GitHub issue titled `audit: <YYYY-MM-DD>` (or a chat report, if Stan prefers). **The repo is public (ADR-0027 rule 6):** findings from §3 "Security posture" and anything exploitable go to Stan in chat, or into a private draft security advisory, **never into the public issue**. Scrub tokens and personal data from every excerpt. Each finding is listed as: severity (🔴 act now / 🟠 this week / 🟢 nice to have), evidence, and a proposed action. **Never fix anything during an audit.** Fixes are separate PRs through `change`, one per finding, after Stan picks which ones.

## 1. Drift and health

- `flux get all -A`: anything not Ready or suspended (suspended = drift, ADR-0013).
- Drift corrections in the last 7 days: `kubectl get events -A --field-selector reason=DriftDetected` plus Flux alert history. Each one means someone changed the cluster by hand. Find out what and why.
- Nodes: Ready, kubelet versions equal, conditions clean.
- Pods restarting (`increase(kube_pod_container_status_restarts_total[7d]) > 3`), and any OOMKills in the last 7 days.

## 2. Repo hygiene

- `mise run check` on `main`: it must be green.
- Open PRs older than 30 days. The Renovate dependency dashboard backlog.
- Stale branches (merged or abandoned).
- Proposed ADRs (`grep -l 'Status:\*\* Proposed' 00-docs/decisions/*.md`) still waiting on Stan.
- Living docs vs reality: every component in `04-platform/` and `05-apps/` appears in `architecture.md`, and nothing in `architecture.md` has disappeared from the repo.
- `.claude/skills/*` and `.claude/CLAUDE.md`: every path they reference exists, and nothing contradicts `conventions.md`.

## 3. Security posture

- **Athena:** bindings are exactly `view` + `olympus-cluster-read` (+ nothing else). `olympus-cluster-read` has no `*`, no secrets, no write verbs. The `athena-egress` CiliumNetworkPolicy exists and is unchanged.
- **Kite's ClusterRole:** read-only, no secrets.
- **`olympus:viewers`:** read-only, apart from `athena-exec`.
- **Pod Security:** the namespaces with exception labels match the exceptions table in `conventions.md` exactly.
- **VAP audit/warn events** (`kubectl get events -A --field-selector reason=FailedAdmission` and the API server audit annotations): images without a digest, memory limit ≠ request, CPU limits present.
- **No** NodePort Services, no non-tailscale Ingresses, no `hostNetwork` outside the documented platform pods.
- **GitHub:**
  - rulesets match ADR-0005: `gh api repos/{owner}/olympus/rulesets` plus each ruleset's detail
  - the Athena app's permissions have no `workflows` and no `administration`
  - CODEOWNERS is present

## 4. Resources (rightsizing)

For every container, compare 7-day usage with its requests:

```promql
quantile_over_time(0.99, container_memory_working_set_bytes{container!=""}[7d])
quantile_over_time(0.95, rate(container_cpu_usage_seconds_total{container!=""}[5m])[7d:5m])
```

- Propose memory = p99 × 1.2 (request = limit) and CPU request = p95, wherever the current value is off by more than 30% either way.
- Node headroom: the sum of requests vs allocatable per node. Flag above 80%.

## 5. Data

- Namespaces with PVCs that have neither the `backup` component nor `olympus/backup: none` + a reason.
- Backup freshness per namespace (k8up metrics): anything older than 36 hours.
- Released or orphaned PVs (`Retain` leftovers): list them with their size, and ask Stan to keep or delete each.
- Date of the last restore drill in `runbooks/disaster-recovery.md`: flag it if older than 100 days. Date of the last full rehearsal: flag it if older than 1 year.

## 6. Deferred register (ADR-0026)

Evaluate every trigger you can observe and report the ones that have fired:

- node count (Spegel, SecureBoot re-evaluation before the first worker, HA control plane)
- apps needing Postgres (CloudNativePG)
- number of Cloudflare Access apps, from the runbook (OpenTofu)
- PR volume (review bot)
- a missing log history that blocked a past debug (VictoriaLogs)

## 7. Calibration

- Eviction events and PSI peaks in the last 30 days. Are the reservations and thresholds in `01-talos/patches/` still right?
- Reconcile durations (Flux metrics): are the intervals still sensible?
- VMSingle disk usage vs the retention setting.

## Report skeleton

```markdown
# audit: <date>
Summary: <n> 🔴, <n> 🟠, <n> 🟢. <one-line overall state>

## 🔴 Act now
- **<finding>**: evidence: `<cmd>` → <excerpt>. Proposed: <PR title> | Stan: <action>

## 🟠 This week
…
## 🟢 Nice to have
…
## Checked and clean
<sections with no findings, so Stan knows they were checked>
```
