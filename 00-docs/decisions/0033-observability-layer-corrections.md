# ADR-0033: Corrections from building the observability layer

- **Status:** Accepted (rule 10 resolved by ADR-0034)
- **Date:** 2026-10-21
- **Deciders:** Stan (owner), Claude (proposer)
- **Related:** ADR-0018 (resolves rule 5; supersedes the Grafana admin-password detail in rule 3), ADR-0019 (supersedes rule 1's bridge), ADR-0020 (supersedes the `ai` part of rule 2, and rule 8)

## Context

Building metrics, alerting and Kite against the real charts settled several "verify at implementation" items, and turned up one serious drift source.

## Decision

1. **No ntfy bridge.** ntfy has a built-in Alertmanager template (`?template=alertmanager`).
   - Alertmanager posts straight to the topic. Priority is set per receiver with `&priority=urgent|default`.
   - The three receiver URLs (ntfy critical, ntfy warning, the healthchecks.io ping) live in one SOPS Secret, `alertmanager-receivers`. Alertmanager reads each from a mounted file (`url_file`), so no URL appears in any config.
2. **Kite's AI assistant is off.**
   - Anthropic's terms allow Claude **subscription** credentials only in Claude Code and Anthropic's own apps. Kite is a third-party tool and needs a pay-as-you-go API key ([Claude Code: legal and compliance](https://code.claude.com/docs/en/legal-and-compliance)).
   - Athena *is* Claude Code, so it may use Stan's subscription. It is the cluster's AI.
   - Turning Kite's AI on later is one `ai:` block plus an API key in `kite-secrets`.
3. **Kite's RBAC:** `rbac.create: false`. Its ServiceAccount is bound to the built-in `view` role and `olympus-cluster-read`: everything except Secrets, and no writes. The chart's default rules are `*`/`*`/`*`. Secret values (admin password, encryption key, JWT secret) arrive through `valuesFrom` from `kite-secrets`.
4. **metrics-server runs with `--kubelet-insecure-tls`.** Talos kubelets use self-signed serving certificates, and the traffic never leaves the cluster. The alternative (`rotate-server-certificates` plus a CSR approver component) is deferred until a reason appears.
5. **Short, fixed names:** the stack runs with `fullnameOverride: vm`. Kite's Prometheus URL is `http://vmsingle-vm.victoria-metrics.svc.cluster.local:8428`.
6. **Talos scrapes:**
   - The scheduler and controller-manager are selected by `k8s-app` labels.
   - etcd, which is a Talos service rather than a pod, is scraped at `${CONTROL_PLANE_IP}:2381` over HTTP.
7. **Every remotely fetched rule and dashboard is pinned.**
   - The chart's sync job downloads about 40 rule and dashboard files at install time, and **every upstream default pointed at a floating `main`/`master` branch**. Content would change without any change in git.
   - Every source is now pinned to a release tag (kube-prometheus, VictoriaMetrics, its operator, VictoriaLogs/Traces, dotdc) or to a commit (rfmoz, monitoring-mixins, which publish no releases). That includes disabled sources.
   - The `render` check now rejects any raw-GitHub URL on `main`, `master` or `HEAD`, anywhere in rendered output.
8. **Grafana's admin account:** the chart generates a random admin password into a Helm-managed Secret. It is break-glass only; viewers are anonymous on the tailnet. ADR-0018 rule 3 had planned a SOPS-stored password; a generated one does the same job with nothing to rotate in git.
9. **Chart-internal images of the VictoriaMetrics stack are pinned by tag (by the chart), not by digest.**
   - `images-have-digest` warns about them. That policy is warn-only by design (ADR-0021).
   - Digests for images inside third-party charts arrive with Renovate's digest pinning (phase 6, ADR-0023).
   - The operator-injected `config-reloader`/`config-init` containers get explicit resources (`configReloaderResources`), so they pass the strict policies.
10. **Per-component monitoring** (ServiceMonitors and dashboards for Cilium, Flux, k8up, Tailscale and cloudflared, plus Olympus alert rules) is a separate PR. Those monitors live in each component's folder and need the stack's CRDs first.

## Consequences

- One component fewer (no bridge), and no third-party AI credentials.
- Alert rules and dashboards change only through a reviewed pin bump.

## Alternatives considered

- **Vendor all rules and dashboards into git:** fully offline, but thousands of lines to keep updated by hand. Rejected in favour of pinned URLs, which Renovate can bump.
- **Disable the sync job and write our own rules:** loses the maintained upstream rule sets. Rejected.

## Compliance

- `render`: the floating-ref rule, plus helm template + kubeconform of every chart.
- `runbooks/04-observability.md`: the alert-path test after any alerting change.
