# Runbook 04 · Observability

Metrics, dashboards and alerts (ADR-0018, ADR-0019, ADR-0020). Everything here is tailnet-only and read-only.

## The UIs

| URL (on the tailnet) | What it is |
|---|---|
| `https://grafana.<tailnet>.ts.net` | dashboards. You're an anonymous Viewer; dashboards come only from git. |
| `https://kite.<tailnet>.ts.net` | the cluster dashboard. Sign in as `stan` (password in your password manager). Edit buttons fail on purpose. |
| `https://alertmanager.<tailnet>.ts.net` | what's firing right now, and where it was routed |
| `https://vmui.<tailnet>.ts.net/vmui` | raw PromQL/MetricsQL queries against VictoriaMetrics |
| `https://hubble.<tailnet>.ts.net`, `https://flux.<tailnet>.ts.net` | live network flows, and Flux (network layer) |

## Alert path

VMAlert → Alertmanager →
- `severity=critical` → ntfy `priority=urgent`, repeated every hour until resolved
- `severity=warning` → ntfy `priority=default`, repeated every 12 hours
- `Watchdog` (always firing) → a healthchecks.io ping every minute

**The dead man's switch:** if the pings stop because the cluster, zeus or the internet is down, healthchecks.io notices on its own and alerts you through ntfy.

The three URLs live only in `victoria-metrics/app/alertmanager-receivers.sops.yaml`. Change them with `mise run secret:new` (keys `ntfy-critical`, `ntfy-warning`, `healthchecks`).

## One-time setup outside git (done 2026-10-21)

- **ntfy:** the phone app subscribes to the topic on `ntfy.sh`. The topic name is in your password manager; anyone who knows it can read it.
- **healthchecks.io:** check `olympus-watchdog`, with a Period of 5 minutes and a Grace time of 5 minutes, and the ntfy integration pointing at the same topic (down = Max priority, up = Default).

## Test the whole path

Run this after any change to alerting (ADR-0019 compliance):

```bash
kubectl -n victoria-metrics exec deploy/vmalertmanager-vm -c alertmanager -- \
  amtool alert add OlympusTestAlert severity=warning --annotation=summary="test from runbook 04" \
  --alertmanager.url=http://localhost:9093
```

Within about a minute your phone shows "🚨 Alert: OlympusTestAlert". It resolves by itself after a few minutes. This needs the admin kubeconfig (break-glass). From the read-only tailnet `kubectl`, `exec` is refused by design.
