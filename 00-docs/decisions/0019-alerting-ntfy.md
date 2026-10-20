# ADR-0019: Alerting: Alertmanager to ntfy, with an external dead man's switch

- **Status:** Accepted
- **Date:** 2026-10-20
- **Deciders:** Stan (owner), Claude (proposer)
- **Related:** ADR-0013, ADR-0017, ADR-0018

## Context

Stan uses ntfy for phone push notifications. He wants alerting that still works when the monitored host dies. ntfy has no retry-until-ack and no free-text replies, and a public ntfy topic must only ever carry alerts out, never commands in (lessons from the Sentinel design).

## Decision

1. **Path:** VMAlert → Alertmanager → **ntfy-alertmanager** bridge (namespace `ntfy-alertmanager`, image pinned by digest) → ntfy topic.
   - The topic is on `ntfy.sh` with an unguessable name, stored in `ntfy-alertmanager-config.sops.yaml`.
   - *Verify at implementation that ntfy doesn't natively accept the Alertmanager webhook format.* If it does, drop the bridge.
2. **Routing:**
   - `severity: critical` → ntfy priority 5, repeated every 1 h until resolved. Repeats are Alertmanager's job, because ntfy has no ack.
   - `severity: warning` → priority 3, repeated every 12 h.
   - `severity: info` → not paged; visible in Alertmanager and Grafana only.
   - Grouping by `alertname` and `namespace`.
3. **Dead man's switch.** The always-firing `Watchdog` alert is routed to a webhook receiver that pings **healthchecks.io** every minute. If the pings stop (cluster dead, zeus dead, internet dead), healthchecks.io itself notifies Stan through its ntfy integration. This alert survives the whole cluster dying.
4. **Alerts are out-only.** No ntfy action buttons trigger cluster changes. Any `view` action opens a tailnet URL: Grafana, Kite, or the Flux UI.
5. **Rules that must exist from day 1:**
   - node not Ready (> 5 m)
   - memory pressure on any node (Talos/kubelet eviction signals, plus PSI from node-exporter: `full avg60 > 20%`, the July 2026 signature)
   - disk > 85 %
   - Flux reconcile failure (> 15 m)
   - Flux drift corrected (info → warning if repeated)
   - HelmRelease not Ready
   - certificate expiry of the Talos/K8s PKI (< 30 days)
   - `BackupFailed`, `BackupStale` (ADR-0017)
   - Cilium agent not Ready
   - cloudflared tunnel down
   - Athena pod OOMKilled (info)

## Consequences

- Phone alerts for real problems, plus an independent signal when everything is down.
- The healthchecks.io account is an out-of-git dependency. Its check URL is in SOPS, and its configuration is documented in `runbooks/04-observability.md`.

## Alternatives considered

- **Pushover:** has retry-until-ack, but Stan has moved away from it. Rejected.
- **Grafana alerting:** a second rule engine next to VMAlert. Rejected.

## Compliance

- A synthetic test alert, `OlympusTestAlert`, is fired manually in the runbook after every change to the alerting path.
