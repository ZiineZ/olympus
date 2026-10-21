# ADR-0020: Dashboard: Kite, declarative and read-only

- **Status:** Accepted (the `ai` part of rule 2 and rule 8 superseded by ADR-0033: Kite's AI is off)
- **Date:** 2026-10-20
- **Deciders:** Stan (owner), Claude (proposer)
- **Related:** ADR-0011, ADR-0012, ADR-0018, ADR-0024

## Context

Stan chose Kite ([kite-org/kite](https://github.com/kite-org/kite)): a lightweight Kubernetes dashboard with Prometheus charts, log streaming, and an AI assistant that supports Anthropic. Out of the box, Kite is a *write-capable* UI: it can edit YAML, scale, restart, open terminals, and install Helm releases. Used that way, it would be a click-ops drift machine.

## Decision

1. **Kite** in namespace `kite`, from the official OCI chart, at decision time v0.16.0.
2. **Configuration-file mode:**
   - `config.enabled: true`
   - `config.existingSecret: kite-config`, which is `kite-config.sops.yaml` with a `config.yaml` key
   - With this on, the clusters, AI, and RBAC sections become read-only in the UI.

   Contents:
   - `superUser`: username `stan`, password `${KITE_ADMIN_PASSWORD}` from the same Secret's env.
   - `clusters`: `[{name: olympus, inCluster: true, default: true, prometheusURL: <VMSingle URL, ADR-0018>}]`
   - `ai`: `{enabled: true, provider: anthropic, model: claude-sonnet-5-5, apiKey: ${ANTHROPIC_API_KEY}, maxTokens: 8192}`
   - `rbac`: one role, `viewer`: all clusters and namespaces, verbs `get`/`list`/`watch`/`log`. Mapped to `stan`.
3. **Kite's own ServiceAccount is read-only.** The chart's `rbac.rules` are replaced with get/list/watch on everything except Secrets, plus `pods/log`. There is no exec, no `nodes/proxy`, and no write verbs.
   - This means the pod, node, and kubectl terminals and every edit action fail by construction. The Kite AI assistant inherits the same limits.
   - *Verify in rehearsal that the UI renders fully under this role* (Helm view may need Secret read for release data; if so, Helm view is disabled, not RBAC widened).
4. **Secret values** (`encryptKey`, `jwtSecret`) come from HelmRelease `valuesFrom` the Secret `kite-secrets.sops.yaml` (ADR-0014).
5. **Persistence:** SQLite on a 1 Gi `local-path` PVC (`db.sqlite.persistence.pvc.enabled: true`), on `olympus/tier=heavy`, backed up by k8up (ADR-0017). `plugins.persistence` uses the same PVC.
6. **Plugins:** none at first. A plugin is a component change and needs a PR. Candidates are the Gateway API plugin and Resource Map.
7. **Exposure:** tailnet only, `https://kite.<tailnet>.ts.net` (ADR-0011).
8. **Kite AI vs Athena:** Kite AI is for quick, in-UI, read-only questions. Athena (ADR-0024) is the maintainer that opens PRs. They don't share credentials. Kite AI uses its own Anthropic key, `kite-ai`, so that usage can be told apart.

## Consequences

- Kite becomes a pure "watch and understand" surface.
- Any write button visible in the UI returns a permission error. That is intended, and documented in the runbook so it isn't mistaken for a bug.

## Alternatives considered

- **Headlamp:** strong too (and it has a Flux plugin), but Stan picked Kite. Its AI and Prometheus integration are built in.
- **The Kubernetes Dashboard:** dated, no metrics charts. Rejected.

## Compliance

- `audit` verifies that Kite's ClusterRole has no write verbs and no Secrets access.
- Config drift in the UI is impossible in config-file mode.
