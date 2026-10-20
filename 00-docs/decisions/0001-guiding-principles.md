# ADR-0001: Guiding principles

- **Status:** Accepted
- **Date:** 2026-10-20
- **Deciders:** Stan (owner), Claude (proposer)
- **Related:** every other ADR

## Context

Many small choices are never worth a dedicated ADR, but they still need a consistent answer. These principles are the tie-breakers. When two options both satisfy the ADRs, the one that better follows these principles wins.

## Decision

1. **Git is the only source of truth.** Olympus follows the four [OpenGitOps](https://opengitops.dev) principles: declarative, versioned and immutable, pulled automatically, continuously reconciled.
2. **Every fact lives exactly once.** Anything that summarizes it is generated (ADR-0004).
3. **Every change goes through a PR.** Every UI is read-only: Kite, Grafana, Flux Web UI, Hubble. If you want to click something, write it in git instead.
4. **There is one writer per kind of change.** Humans and Athena write through PRs; Renovate writes version bumps. No in-cluster bot writes to git, so there is no Flux image automation.
5. **Structural limits beat instructions.** RBAC, rulesets, admission policies, and network policies are the real boundaries. Prompts and hooks are defense in depth only.
6. **Boring by default.** The innovation budget is spent on Talos, Cilium, and VictoriaMetrics. Any other new tool needs an ADR and a reason that existing tools can't cover.
7. **Upstream conventions over our own.** Use Gateway API, the Kubernetes recommended labels, home-operations patterns, and chart defaults where they fit. Every answer on kubesearch.dev should apply to this repo.
8. **The cluster is cattle, the data is a pet.** The cluster can be rebuilt from git at any time. Only PVC data needs backups (ADR-0017, ADR-0025).
9. **Smallest diff, one concern per PR, always explain why.** This is a learning project, so every PR explains its change in beginner-friendly terms.
10. **Minimal by default.** If something isn't clearly needed now, it goes into the deferred register (ADR-0026) with a trigger condition. It is not scaffolded "for later".
11. **Performance over silence.** Devices may be loud: no power capping, performance CPU governor (Stan, 2026-10-20).
12. **Deterministic failure over degraded crawl.** Memory request equals memory limit, there is no swap, and platform workloads have a higher priority than apps. A runaway process gets OOM-killed promptly instead of starving the node. This is the lesson from the July 2026 `lab` outage.

## Consequences

- Reviews can point at a principle number instead of re-arguing taste.
- Some upstream conveniences are refused, for example click-ops in UIs and image automation.

## Alternatives considered

- **No written principles:** decisions drift with mood and with the model of the day. Rejected.

## Compliance

- Athena's `olympus` skill applies these principles as tie-breakers.
- PR reviews cite them by number.
