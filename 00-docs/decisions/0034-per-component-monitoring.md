# ADR-0034: Per-component monitoring

- **Status:** Accepted
- **Date:** 2026-10-21
- **Deciders:** Stan (owner), Claude (proposer)
- **Related:** ADR-0003 (rule 6, cohesion), ADR-0017, ADR-0018 (narrows the initial dashboard list), ADR-0033 (resolves rule 10)

## Context

The observability layer brought the upstream rule sets for Kubernetes, nodes and VictoriaMetrics itself. Olympus's own components were still unwatched. Nothing would tell Stan that:
- Flux has stopped applying git
- backups have stopped or failed
- the tunnel behind every public site is down
- a node is alive but starved of memory (the failure mode that took `lab` down in July 2026)

Two constraints shape where these monitors live:
- Rules and dashboards live next to the component they watch (ADR-0003 rule 6). Most of those components sit in lower layers than the monitoring stack.
- Monitoring objects are CRs. Their CRDs come with the VictoriaMetrics operator in layer 04. Cilium is also installed by helmfile before Flux exists.

## Decision

1. **Every watched component gets `app/monitoring/`**, applied by a second Flux Kustomization `<component>-monitoring` in the component's own `ks.yaml`.
   - It `dependsOn` the component and `victoria-metrics`.
   - This is the **one allowed dependency on a higher layer**. It can't deadlock: the layer Kustomizations don't wait on their children (`wait: false`), so only the monitoring Kustomization waits.
2. **Only VictoriaMetrics CRs:** `VMPodScrape`, `VMServiceScrape` and `VMRule`.
   - No Prometheus Operator CRDs are installed, so charts' own `serviceMonitor`/`prometheusRule` switches stay off. They would fail on a fresh cluster, because the CRDs arrive later.
   - Pod scrapes are preferred: they need no Service.
3. **The first set:**

   | Component | Scrapes | Alerts |
   |---|---|---|
   | Cilium | agent, Hubble flow metrics, operator | `CiliumBpfMapPressure`, `CiliumUnreachableNodes` (warning) |
   | Flux (via the Flux Operator's `flux_resource_info`) | flux-operator | `FluxResourceNotReady` after 15 min, `FluxResourceSuspended` after 24 h (warning: a suspended resource ignores git) |
   | k8up | operator job counters, plus restic results pushed by every backup pod | `BackupStale` (no backup in 26 h), `BackupErrors`, `BackupJobFailed` (warning) |
   | cloudflared | its metrics port | `CloudflaredTunnelDown` (critical: every public site is down) |
   | nodes (in `victoria-metrics`) | already scraped by node-exporter | `NodeMemoryPressure` (warning), `NodeMemoryStall` (critical) from PSI |

4. **k8up pushes into VMSingle.**
   - VMSingle has a Pushgateway-compatible endpoint, and the operator-wide `BACKUP_PROMURL` points there. No Pushgateway is deployed.
   - Before this, every backup pod pushed to k8up's default `http://127.0.0.1/` and logged an error.
   - `BackupStale` uses MetricsQL's `lag()`, so it starts watching a namespace after its first backup. A brand-new namespace doesn't alert during its first day.
5. **Dashboards:** only Cilium's and Hubble's, which the Cilium chart ships as `grafana_dashboard` ConfigMaps for the running version.
6. **Not now:** each item comes back on its trigger.

   | Item | Trigger |
   |---|---|
   | Flux and k8up Grafana dashboards (in ADR-0018's initial list) | Stan finds the Flux Web UI, Kite or the alerts not enough to answer a question |
   | Tailscale proxy metrics | A tailnet UI is unreachable while its pod is Running |
   | Flux controller metrics (reconcile durations) | A slow reconcile needs explaining |

## Consequences

- Each new component brings its own scrapes and rules in its own folder. Deleting the folder deletes its monitoring.
- Cilium's agent serves metrics on host port 9962, and Cilium's dashboards follow the chart version.
- The PSI rules cannot fire in the OrbStack rehearsal: its kernel has no PSI. Talos's kernel enables PSI by default (`CONFIG_PSI=y`).
- cloudflared's monitoring is verified on zeus only, like cloudflared itself (ADR-0025).

## Alternatives considered

- **All Olympus rules in `victoria-metrics/`:** no upward dependency, but rules drift away from the component they describe. Rejected (ADR-0003 rule 6).
- **Prometheus Operator CRDs, so charts can ship their ServiceMonitors:** dozens more CRDs, and charts in lower layers still install before them. Rejected.
- **A Pushgateway for k8up:** one more workload to run and back up. VMSingle already accepts the same pushes. Rejected.
- **k8up's chart rules:** they depend on kube-state-metrics job labels that aren't exported here, and on the Prometheus Operator CRDs. Rejected; Olympus's rules use metrics that exist.

## Compliance

- The `render` check validates every `VMPodScrape`/`VMRule` against its CRD schema.
- VMAlert reports each rule's health. The rehearsal checks all rules are `ok` and all targets are `up`.
- `audit` flags a `<component>-monitoring` Kustomization without a `victoria-metrics` dependency.
