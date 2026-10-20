# ADR-0026: Deferred decisions register

- **Status:** Accepted
- **Date:** 2026-10-20
- **Deciders:** Stan (owner), Claude (proposer)
- **Related:** ADR-0001 principle 10

## Context

Minimal-by-default only works if "not now" is written down together with *when* it becomes "now". Otherwise good ideas resurface randomly as unplanned scope, or get scaffolded early "for later".

## Decision

Each item below is **not** part of Olympus until its trigger fires *and* a new ADR is accepted. Nothing is pre-scaffolded. Athena's `audit` skill checks the triggers and reports any that have fired. The register itself is updated only by superseding this ADR, or by an ADR that adopts an item and references it.

| Item | Trigger | Likely choice when triggered |
|---|---|---|
| Postgres operator | First app that needs Postgres | CloudNativePG, with its own S3 backups |
| Log storage | Stan needs logs older than what live streaming shows, or post-mortems lack data | VictoriaLogs single + collector |
| Image P2P mirror | A second node joins | Spegel |
| HA control plane (hera, poseidon) | 3 machines with ≥16 GB, an SSD and wired GbE | Talos control-plane join at the same VIP |
| SSO for UIs | More than 3 UIs need logins beyond the tailnet, or sharing with another person | Pocket ID (OIDC, passkeys) |
| LAN hostnames + certificates | The first LAN-only service | cert-manager (DNS-01, Cloudflare) + split DNS |
| Envoy Gateway | Cilium Gateway lacks a needed feature | Envoy Gateway |
| Cloudflare as code (Access apps, tunnel) | More than 3 Access apps, or the first drift incident there | OpenTofu in a new `.github` workflow |
| SecureBoot + TPM disk encryption | **Re-evaluate before the first worker joins** (dorm theft risk) | Talos SecureBoot UKI + TPM-sealed STATE/EPHEMERAL |
| Weekly Talos drift job | After phase 6 is complete | CronJob with Talos `os:reader`, comparing the running config to git, reporting to ntfy |
| etcd snapshots off-box | The first app where rebuild time matters more than about 1 h | Talos etcd snapshot CronJob to object storage |
| Formatter | The first PR about formatting inconsistency | yamlfmt or prettier, pinned in mise, in `check` |
| Git hooks for humans | Stan pushes a PR that fails CI on something a hook would have caught, 3 times | lefthook running `mise run check` |
| Commit signing | The repo goes public, or a second human contributor | Required signed commits ruleset |
| PR review bot | Weekly PR volume exceeds Stan's review time | anthropics/claude-code-action, read-only reviewer |
| Flux MCP server for Athena | Athena repeatedly struggles to reason about Flux state with the CLI | flux-operator MCP, read-only mode |
| Web terminal for Athena (phone) | Stan wants to talk to Athena from his phone | ttyd behind a Tailscale Ingress |
| Replicated block storage | A workload must survive zeus being down | Longhorn (with dedicated disks) |
| Kopia-based backups | kopiur reaches 1.0 and offers a clear advantage | kopiur, superseding ADR-0017 |
| VolSync | Snapshot-capable storage is adopted | VolSync with the volume populator |
| Kyverno | A need for generate or verifyImages that CEL can't cover | Kyverno |
| Dual-stack IPv6 | The ISP or dorm gives usable IPv6, and a service needs it | Cilium dual-stack |
| "Gitless" Flux (OCI artifacts) | CI signs and pushes manifests for a reason git can't serve | Flux OCI sync |
| CI full-rebuild e2e | The quarterly rehearsal becomes a burden | Weekly `talosctl cluster create` job in GitHub Actions |
| App migration from `lab` | Stan says the foundation is done | One app per PR, through `add-component` |

## Consequences

- Scope stays explicit, and "should we add X?" has a standing answer.

## Alternatives considered

- **A TODO list in an issue:** lives outside git, with no triggers. Rejected.

## Compliance

- The `audit` skill evaluates every trigger it can observe: node count, number of Access apps, app requirements, open PR volume. It reports any that have fired.
