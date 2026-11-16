# ADR-0040: Memory right-sizing, round one

- **Status:** Accepted
- **Date:** 2026-11-16
- **Deciders:** Stan (owner), Claude (proposer)
- **Related:** ADR-0022 (memory limit = request), ADR-0024 (amends rule 2), ADR-0036 (amends the session capacity), ADR-0018, ADR-0010

## Context

Stan found the platform's memory footprint too large. Rendering every component from the repo shows about **7.7 GiB reserved**, before Kubernetes' own control plane. Under ADR-0022 every pod reserves its full limit. Yet the observability rehearsal *used* only about 3.5 GiB in total, so most of the reservation was over-sized limits set before any measurement.

The biggest reservations were:
- the VictoriaMetrics stack (2.3 GiB, VMSingle 768 Mi alone)
- Athena (2 GiB)
- Cilium (1.2 GiB)

Stan asked to keep every feature and only tune settings.

## Decision

1. **Lower limits that were set well above what these components use at this scale.** Every value stays a calibration knob, re-measured on zeus (rule 4).

   | Workload | Before | After | Why it's safe |
   |---|---|---|---|
   | VMSingle | 768 Mi | 384 Mi | VictoriaMetrics sizes its caches from its own memory limit (60% by default). Olympus's few tens of thousands of active series need far less. |
   | VMAlert | 128 Mi | 96 Mi | it holds rule state for a few dozen groups |
   | Cilium operator | 256 Mi | 128 Mi | on one to a few nodes it manages a handful of IPs and leases |
   | Hubble Relay | 128 Mi | 64 Mi | it only relays flows from one or a few agents |
   | Athena | 2 Gi, 4 sessions | 1.5 Gi, 2 sessions | two parallel conversations are plenty for one person |

2. **Grafana's datasources sidecar becomes an init container** (`sidecar.datasources.initDatasources: true`). The datasources come from the chart and never change at runtime, so the loader runs once at pod start instead of watching the API for the pod's whole life. The dashboards sidecar stays: dashboards live next to their components and do change.
3. **Athena's session count is config, not image.** `ATHENA_SESSIONS` in the HelmRelease sits next to the memory limit it's sized with. Tuning either no longer needs an image build.
4. **Round two is measured on zeus.** After a week of real metrics, the `audit` skill's rightsizing pass (§4: memory = 7-day p99 × 1.2) proposes the PR. The rest of the reservation sits there: Grafana, Kite, Cilium's agent and Envoy, the Tailscale proxies, and flux-operator. Round one cuts only what is clearly over-sized without measurements.

## Consequences

- Reserved memory drops by about 1.3 GiB, from about 7.7 GiB to about 6.4 GiB.
- Real usage drops mostly where caches follow limits (VMSingle) and where a process disappears (the datasources sidecar). Other processes use what they use whatever their limit, so lowering their limits frees reservation, not RAM.
- **Risk:** a limit that turns out too low shows as an `OOMKilled` pod. The kube-state-metrics rules alert on restart loops, and the fix is a one-line PR raising that knob.

## Alternatives considered

- **Remove features (Grafana, Hubble UI, the Alertmanager UI, the Flux notification-controller):** about 1.1 GiB more. Stan chose to keep them all.
- **Drop memory limit = request (ADR-0022) to overcommit:** reservations would shrink on paper, but a busy node would then slow everyone under memory pressure instead of OOM-killing the one offender. That's the July 2026 failure mode. Rejected.
- **Cut everything to guessed values now:** limits below real peaks would cause OOM loops. Rejected in favour of measuring (rule 4).

## Compliance

- `render` validates every changed value. The admission policies still hold: memory limit = request, no CPU limit.
- `audit` §4 (resource rightsizing) carries out rule 4.
