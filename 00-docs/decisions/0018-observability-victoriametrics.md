# ADR-0018: Observability: VictoriaMetrics k8s stack, read-only Grafana, metrics-server

- **Status:** Accepted
- **Date:** 2026-10-20
- **Deciders:** Stan (owner), Claude (proposer)
- **Related:** ADR-0010, ADR-0019, ADR-0020, ADR-0022

## Context

Kite needs a Prometheus-compatible endpoint, and Stan wants live dashboards. kube-prometheus-stack is the default choice but is RAM-hungry. Weak workers make every daemon count.

## Decision

1. **`victoria-metrics-k8s-stack`** in namespace `victoria-metrics` (at decision time chart 0.96.0). It includes:
   - **VMSingle:** `retentionPeriod: 30d`, a 30 Gi `local-path` PVC on `olympus/tier=heavy`, the `platform` PriorityClass.
   - **VMAgent:** `scrapeInterval: 30s`. The VictoriaMetrics operator converts upstream `ServiceMonitor`/`PodMonitor` CRs, so charts' built-in monitors work unchanged.
   - **VMAlert + Alertmanager:** the chart's default rules (the kube-prometheus rule set) plus Olympus rules, which live next to the component they watch (ADR-0003 rule 6).
   - **node-exporter** (a DaemonSet on all nodes) and **kube-state-metrics**.
   - **Grafana** (details below).
2. **Kite compatibility.** Kite explicitly supports this stack (kite issues #260, #349, #579). Kite's `prometheusURL` is `http://vmsingle-victoria-metrics-k8s-stack.victoria-metrics.svc.cluster.local:8428`. *Verify the service name and port at implementation:* the port changed in stack 0.58.3.
3. **Grafana is read-only and fully provisioned:**
   - Dashboards come only from git: sidecar ConfigMaps labelled `grafana_dashboard: "1"` living next to their component, plus grafana.com dashboards pinned by `gnetId` + `revision` in values (Renovate bumps the revisions).
   - Provisioned dashboards have `editable: false`. `users.allow_sign_up: false`. The admin password lives in SOPS and is used only for break-glass. Viewers sign in through the tailnet with the anonymous `Viewer` role. Grafana is reachable only on the tailnet.
   - The initial dashboards: Kubernetes views from the stack, Node Exporter Full, Cilium agent/operator, Hubble, Flux (from flux-operator), VictoriaMetrics, k8up.
4. **Scrape targets that need Talos patches:** etcd, kube-scheduler, and kube-controller-manager (ADR-0007 controlplane patch).
5. **metrics-server** in `kube-system` (at decision time v0.9.0), for `kubectl top` and for Kite. Talos uses `--kubelet-insecure-tls` *only if* serving certificates aren't rotated. *Prefer Talos `rotate-server-certificates` + kubelet-serving-cert-approver; decide at implementation and record it in the runbook.*
6. **Logs:** there is no log store. Kite and `kubectl logs` stream live logs. VictoriaLogs is deferred (ADR-0026).
7. **Sizing** is a calibration knob, not a contract. Initial requests are in each `values.yaml`, and are re-sized from 7 days of data by the `audit` skill.

## Consequences

- Same dashboards and alert rules as kube-prometheus, at a fraction of the RAM.
- PromQL works; MetricsQL extensions are available but not required.
- Grafana click-ops is impossible; dashboard changes are PRs.

## Alternatives considered

- **kube-prometheus-stack:** the reference stack, but about 3–5 times the memory for this cluster size. Rejected.
- **Grafana Cloud free tier:** sends data off-site and creates an external dependency for core visibility. Rejected.

## Compliance

- The `render` check flags any ConfigMap whose name ends in `-dashboard` but lacks the `grafana_dashboard` label.
- `audit` flags dashboards in Grafana that don't exist in git.
