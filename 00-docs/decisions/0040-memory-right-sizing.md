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

1. **Lower limits to measured use.** Every value comes from a rehearsal of the whole platform (runbook 01, 2026-11-16): each container's peak working set over 40 minutes, with at least 1.5× headroom. Each stays a calibration knob, re-measured on zeus (rule 4).

   | Workload | Before | After | Rehearsal peak |
   |---|---|---|---|
   | VMSingle | 768 Mi | 512 Mi | 345 Mi. It was OOMKilled at 384 Mi. |
   | VMAlert | 128 Mi | 96 Mi | 61 Mi |
   | Cilium agent | 512 Mi | 384 Mi | 184 Mi |
   | Cilium operator | 256 Mi | 128 Mi | 72 Mi |
   | Hubble Relay | 128 Mi | 64 Mi | 18 Mi |
   | Kite | 256 Mi | 128 Mi | 35 Mi |
   | Athena | 2 Gi, 4 sessions | 1.5 Gi, 2 sessions | 82 Mi idle. Two parallel conversations are plenty for one person. |

   **VMAgent stays at 256 Mi.** It was OOMKilled at 192 Mi during startup, even with `promscrape.streamParse`, although it settles at 44 Mi.
2. **Grafana's datasources sidecar becomes an init container** (`sidecar.datasources.initDatasources: true` with `watchMethod: LIST`). With the default `WATCH`, the init container never exits and Grafana never starts; the rehearsal caught it. The datasources come from the chart and never change at runtime, so the loader runs once at pod start instead of watching the API for the pod's whole life. The dashboards sidecar stays: dashboards live next to their components and do change.
3. **Athena's session count is config, not image.** `ATHENA_SESSIONS` in the HelmRelease sits next to the memory limit it's sized with. Tuning either no longer needs an image build.
4. **Round two is measured on zeus.** After a week of real metrics, the `audit` skill's rightsizing pass (§4: memory = 7-day p99 × 1.2) proposes the PR. Round one is based on 40 idle minutes with no apps. A week of real load may move peaks either way.

## Consequences

- Reserved memory drops by about 1.3 GiB (1,344 Mi), from about 7.7 GiB to about 6.4 GiB.
- **The biggest real user is Kubernetes itself:** kube-apiserver peaked at 1.1 GiB in the rehearsal, more than any platform component. It has no limit, and its size grows with the number of CRDs and objects. The rehearsal node used 3.7 GiB in total.
- Real usage drops mostly where caches follow limits (VMSingle) and where a process disappears (the datasources sidecar). Other processes use what they use whatever their limit, so lowering their limits frees reservation, not RAM.
- **Risk:** a limit that turns out too low shows as an `OOMKilled` pod. The kube-state-metrics rules alert on restart loops, and the fix is a one-line PR raising that knob.

## Alternatives considered

- **Remove features (Grafana, Hubble UI, the Alertmanager UI, the Flux notification-controller):** about 1.1 GiB more. Stan chose to keep them all.
- **Drop memory limit = request (ADR-0022) to overcommit:** reservations would shrink on paper, but a busy node would then slow everyone under memory pressure instead of OOM-killing the one offender. That's the July 2026 failure mode. Rejected.
- **Cut to guessed values:** the first draft of this ADR did, and the rehearsal OOM-killed VMSingle at 384 Mi and VMAgent at 192 Mi. Rejected: every value is measured.

## Compliance

- `render` validates every changed value. The admission policies still hold: memory limit = request, no CPU limit.
- `audit` §4 (resource rightsizing) carries out rule 4.
