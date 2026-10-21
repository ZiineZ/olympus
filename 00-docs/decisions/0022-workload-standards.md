# ADR-0022: Workload standards: resources, priority, security, networking, packaging

- **Status:** Accepted (Flux's PriorityClass superseded by ADR-0029)
- **Date:** 2026-10-20
- **Deciders:** Stan (owner), Claude (proposer)
- **Related:** ADR-0001, ADR-0003, ADR-0016, ADR-0017, ADR-0021

## Context

Every workload, whether a platform component now or an app later, should look and behave the same way. Weak nodes and the July 2026 memory outage make resource behavior a first-class concern. Stan prefers raw performance over quiet hardware.

## Decision

### Resources

1. Every container, including init containers and sidecars, sets `requests.cpu`, `requests.memory` and `limits.memory`.
2. **`limits.memory == requests.memory`.** The OOM kill is deterministic and there is no overcommit surprise.
3. **No CPU limits.** CPU limits throttle a pod even when the node is idle. Fairness comes from CPU requests, the weights the scheduler uses (Stan, 2026-10-20: performance over silence).
4. Sizing starts from upstream recommendations. After 7 days, requests are re-sized from VictoriaMetrics data: memory to p99 × 1.2, CPU to p95. The `audit` skill proposes these changes as PRs.

### Priority (`03-cluster/priority-classes.yaml`)

| PriorityClass | Value | For |
|---|---|---|
| *(built-in)* `system-node-critical` / `system-cluster-critical` | — | Cilium, CoreDNS, kube-system |
| `platform-critical` | 100000 | Flux, cloudflared, tailscale operator |
| `platform` | 10000 | observability, Kite, k8up, external-dns, local-path, tuppr |
| `apps` | 1000 | **`globalDefault: true`**: anything that doesn't set a class |
| `agent` | 100 | Athena. `preemptionPolicy: Never` |

Under memory pressure the kubelet evicts the agent and apps before the platform.

### Security context (target: Pod Security `restricted`)

- `runAsNonRoot: true`
- `allowPrivilegeEscalation: false`
- `capabilities.drop: [ALL]`
- `seccompProfile.type: RuntimeDefault`
- `readOnlyRootFilesystem: true` where the image allows it
- **`hostUsers: false`** (user namespaces, GA in 1.36) for Stan's own apps, and for platform charts that support it.

### Labels and metadata

- **Pods:** `app.kubernetes.io/name` (required), `app.kubernetes.io/instance`, `app.kubernetes.io/part-of`, `app.kubernetes.io/component` (when there are several), `app.kubernetes.io/managed-by` (set by Helm/Flux).
- **Each `ks.yaml`** carries the `olympus/description`, `olympus/docs`, `olympus/adr` annotations (ADR-0004).

### Images

- `registry/repo:tag@sha256:digest`, kept current by Renovate.
- Never `latest` or a bare tag.
- Stan's own images live in `ghcr.io/<stan>/…` with immutable tags.

### Scheduling and availability

- Replicas: 1 by default.
- **No PodDisruptionBudgets** while any workload has 1 replica. A PDB with `minAvailable: 1` on a single replica blocks node drains, and with them tuppr upgrades.
- Stateful workloads use `nodeSelector: {olympus/tier: heavy}` (ADR-0016).
- Probes: readiness and liveness are required for Stan's own apps. Startup probes are used for slow starters.

### Networking (`03-cluster/components/default-deny`)

- Every app namespace includes the component, which adds:
  - deny-all **ingress** by default
  - allow ingress from the same namespace
  - allow from `victoria-metrics` (scraping)
  - allow from `cloudflared` → Gateway, but only for namespaces labelled `olympus/gateway-access: public`
- Platform namespaces get the component too, with their specific allows in their own folder.
- Egress is open by default, except for `athena` (ADR-0024).

### Packaging

- **Stan's own apps:** the **bjw-s `app-template`** chart (at decision time 5.3.0). Every app's HelmRelease then has the same shape, and `add-component` is a fill-in template.
- **Third-party software:**
  - The upstream chart, if it is maintained (a release in the last 6 months) and exposes resources and securityContext in its values.
  - Otherwise `app-template` wrapping the upstream image.
- One namespace per app, named after the app folder.

### Backups

A namespace with PVCs includes `03-cluster/components/backup` (ADR-0017), or carries `olympus/backup: none` with a reason.

## Consequences

- Predictable failures, and fair CPU without throttling.
- Every app folder is reviewable against one checklist.

## Alternatives considered

- **CPU limits everywhere** (the original handoff): throttling on weak CPUs, for no benefit in a single-tenant cluster. Rejected (Stan agreed 2026-10-20).
- **Burstable memory (limit > request):** this is what made the July 2026 incident possible. Rejected.

## Compliance

- ValidatingAdmissionPolicies (ADR-0021) and `policies-offline` in CI.
- `component-shape` checks that the default-deny and backup components are included.
