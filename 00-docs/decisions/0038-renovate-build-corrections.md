# ADR-0038: Corrections from building the Renovate config

- **Status:** Accepted
- **Date:** 2026-10-23
- **Deciders:** Stan (owner), Claude (proposer)
- **Related:** ADR-0023 (amends the Renovate section), ADR-0005, ADR-0006, ADR-0033

## Context

Writing `.github/renovate.json5` and running Renovate locally in extract-only mode against the repo showed which pins each manager actually finds, and which ADR-0023 details don't fit the repo as built.

## Decision

1. **Managers, as built:**
   - **flux:** charts in OCIRepository, HelmRepository and GitRepository sources, and **the images in HelmRelease values**.
   - **helm-values:** only for tuppr's CRs (their `talosctl` image). Pointing it at HelmReleases too would track every image twice.
   - **kubernetes:** images in plain manifests. Its `apiVersion` tracking is off, because API versions move with their charts.
   - **mise, github-actions, dockerfile.**
   - **One generic regex manager** reads `# renovate: datasource=… depName=… [extractVersion=…]` on the line above a version. Used for:
     - `01-talos/cluster.yaml`
     - the tuppr CRs
     - the FluxInstance's `distribution.version`
     - the Claude Code and mise versions in Athena's Dockerfile
   - **Three specific regex managers:**
     - the Gateway API CRDs URL
     - the Flux manifests artifact
     - the tag-pinned VictoriaMetrics rule and dashboard sources (37 URLs)
2. **Every image block has the same shape**, `repository` + `tag: <version>@sha256:<digest>`, so the managers can resolve it. Kite, external-dns and Tailscale gained an explicit repository equal to their chart's default; the rendered images are unchanged.
3. **`mise.lock` is checked.** Renovate updates `mise.lock` itself. The new `mise-lock` check fails when any tool in `mise.toml` has no lock entry for its version, or lacks one of the three platforms. A bump without a complete lock can't merge, auto-merge included.
4. **Athena's Dockerfile checksums stay manual.** Renovate bumps `CLAUDE_CODE_VERSION` and `MISE_VERSION` but can't compute the `--checksum` beside them.
   - Those PRs are never auto-merged, and carry a note to update the checksum.
   - Until the checksum is updated, the `athena-image` build fails, which is the signal.
5. **Not tracked:**
   - **Athena's own image:** its tags are commit SHAs from this repo's build, and its PRs pin it.
   - **The two commit-pinned VictoriaMetrics sources** (rfmoz, monitoring-mixins): they publish no releases, so they're bumped by hand.
6. **Auto-merge** works through GitHub's native auto-merge. The Renovate app (ID 2740) is a bypass actor on `main-approval` only, so it skips the review but never the PR requirement or `validate` (`main-integrity`).
7. **Groups** follow ADR-0023, plus `tailscale` and `k8up` (each chart with its images) and `mise` (the CLI in CI and in Athena's image).
   - The `talos` group matches every `siderolabs/talos*` package: cluster.yaml, the TalosUpgrade, the talosctl images and the mise talosctl pin.
   - The `kubernetes` group also takes the mise kubectl pin.

## Consequences

- A weekly batch on Saturday mornings, at most 5 PRs open at a time.
- Patch and digest bumps outside the platform-critical set, GitHub Actions bumps and mise patches merge themselves once `validate` is green, and only when their lockfile is complete.
- A new version location needs a `# renovate:` hint or a manager. The `change` skill's upgrade row asks for it.

## Alternatives considered

- **A Renovate post-upgrade task to compute checksums:** not available on Mend's hosted app. Rejected; the failing build is an honest signal.
- **Track the commit-pinned dashboards with `git-refs`:** a PR for every upstream commit. Rejected.

## Compliance

- `mise-lock` in `mise run check`. Renovate validates its config on every run and reports problems in the Dependency Dashboard.
- `audit`: the Dependency Dashboard's backlog and errors, and PRs open longer than 30 days (ADR-0023).
