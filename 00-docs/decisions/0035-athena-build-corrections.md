# ADR-0035: Corrections from building Athena

- **Status:** Accepted
- **Date:** 2026-10-22
- **Deciders:** Stan (owner), Claude (proposer)
- **Related:** ADR-0024 (amends rules 1, 9, 10 and 14), ADR-0022, ADR-0025

## Context

Building Athena and rehearsing it settled the details ADR-0024 left open. The rehearsal also found two gaps that would have made Athena useless on zeus:
- kubectl in the pod had no credentials
- Athena's own pre-push check could never pass

## Decision

1. **The ServiceAccount token is mounted explicitly** (`automountServiceAccountToken: true`). `app-template` turns it off by default, so kubectl inside the pod had no in-cluster credentials.
2. **Athena's egress also allows the chart sources, read-only.**
   - Its pre-push hook runs `mise run check`, and the `render` step pulls every chart. With ADR-0024's list, the check hung until it was killed, so the hook would have blocked every push.
   - Added:
     - `ghcr.io` and its blob host `pkg-containers.githubusercontent.com`
     - `quay.io` and `*.quay.io`
     - `k8up-io.github.io`, `kubernetes-sigs.github.io`, `pkgs.tailscale.com`
     - `release-assets.githubusercontent.com`, where GitHub release downloads now redirect
   - This widens no write path: GitHub was already reachable.
   - **The `athena-egress` check** fails when any `OCIRepository`, `HelmRepository` or `GitRepository` in the repo points at a host missing from `athena-egress`. A new chart source can't silently break Athena.
3. **The image** (`athena/image/`):
   - Claude Code's native binary, pinned by version and checksum, downloaded straight from Anthropic's release bucket (no Node.js).
   - mise, pinned by version and checksum, installs `.config/mise.toml` with its lockfile into `/opt/mise`. The tools are linked into `/opt/tools/bin`, so they work in any directory. `/home/athena` is the PVC and would hide anything installed there.
   - About 1.2 GB, almost all of it the toolchain. Slimming it is deferred until pull time matters.
   - The `athena-image` workflow also builds and pushes for same-repo PRs, tagged with the PR's commit, so a PR can be rehearsed with its own image.
   - The GHCR package is **public**. It holds no secrets, and the cluster pulls without a pull secret. Making it public is a one-time click (GitHub's API can't change package visibility).
4. **The GitHub App** is `athena-ziinez`. Its App ID is plain config in the HelmRelease; only the private key is secret.
   - `athena-token` looks the installation up at runtime (`/repos/<repo>/installation`), so no installation ID is configured.
   - Each token is limited to the one repository and cached for 55 of its 60 minutes.
   - Commits use the bot identity `athena-ziinez[bot]`.
5. **`.claude/settings.json` binds every Claude Code session in this repo**, Stan's own included: the deny list, and the pre-push hook through `mise exec`. That's intended. The same guardrails apply whoever runs Claude here.

## Consequences

- ADR-0024's guarantees held in the rehearsal:
  - Athena reads everything but Secrets, and can't delete, patch, create or exec.
  - Its pushes that touch `.github/workflows/` are refused by GitHub.
  - Its pushes to `main` are refused by the ruleset.
  - It reaches nothing outside its allow list.
  - Viewers can exec into Athena and into nothing else.
- The rehearsal node's 9.25 GiB allocatable holds the platform's requests or Athena's 2 GiB, not both. Athena then waits in Pending: lowest priority and `preemptionPolicy: Never`, as designed. zeus has room for both.

## Alternatives considered

- **Run only the offline checks in the hook:** keeps ADR-0024's short egress list, but lets Athena push PRs that fail CI's `render`. Rejected; a few read-only chart hosts cost less.
- **A private package with a pull secret:** one more secret to rotate, for an image without secrets. Rejected.
- **Claude Code through npm:** pulls in Node.js and the npm dependency tree. The native binary is a single checksummed file. Rejected.

## Compliance

- `athena-egress` check in `mise run check` and CI.
- The `audit` skill verifies the GitHub App's permissions (ADR-0024) and the package's visibility.
