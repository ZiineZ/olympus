# ADR-0023: Upgrades: Renovate proposes, tuppr executes Talos and Kubernetes upgrades

- **Status:** Accepted (the tuppr section made concrete by ADR-0037)
- **Date:** 2026-10-20
- **Deciders:** Stan (owner), Claude (proposer)
- **Related:** ADR-0004, ADR-0005, ADR-0006, ADR-0008, ADR-0013

## Context

Pinned versions only stay healthy if bumping them is routine. Upgrades must also be GitOps: the version is changed in git, and the cluster moves to it. Supply-chain attacks on fresh releases are increasingly common.

## Decision

### Renovate (Mend-hosted GitHub app, config in `.github/renovate.json5`)

1. **Extends:** `config:recommended`, `docker:pinDigests`, `helpers:pinGitHubActionDigests`, `:semanticCommits`, `:dependencyDashboard`. Timezone `Europe/Amsterdam`.
2. **Schedule:** `before 6am on saturday`. `prConcurrentLimit: 5`.
3. **`minimumReleaseAge: "3 days"`** for everything. Security advisories bypass it.
4. **Managers:** flux (OCIRepository, HelmRelease), kubernetes/regex for images, mise, github-actions. Custom regex managers cover:
   - `talconfig.yaml`: `talosVersion`, `kubernetesVersion`
   - tuppr CRs
   - Gateway API CRDs in `gateway-api-crds/ks.yaml`
   - grafana.com dashboard revisions
5. **Groups** (one PR each, so related versions never split):
   - `talos`: talconfig `talosVersion`, the tuppr `TalosUpgrade`, Image Factory references
   - `kubernetes`: talconfig `kubernetesVersion`, the tuppr `KubernetesUpgrade`
   - `cilium`: chart plus the Gateway API CRDs
   - `flux`: the flux-operator chart plus the FluxInstance `distribution.version`
   - `victoria-metrics`: the stack chart and its operator
6. **Auto-merge (after `validate` passes):**
   - digest-only and patch updates of images *outside* the platform-critical set
   - GitHub Actions minor/patch/digest
   - mise tools patch updates

   The platform-critical set is **never** auto-merged: Talos, Kubernetes, Cilium, Flux, Gateway API, tailscale, cloudflared, k8up, tuppr.
7. **Major updates** add the label `breaking` and require the `upgrade` skill's changelog review in the PR.

### tuppr (namespace `tuppr`, at decision time v0.5.9)

1. A `TalosUpgrade` named `talos` and a `KubernetesUpgrade` named `kubernetes`. They live in `04-platform/05-operations/tuppr/app/` and carry the target versions.
2. **Health gates:** all nodes Ready, and every Flux Kustomization Ready. Parallelism 1. Talos upgrades use the zeus/amd/intel schematic image matching each node.
3. **Order:** when both are pending, Talos goes first, then Kubernetes, in separate PRs. Kubernetes minors are taken one at a time (ADR-0008).
4. **Talos API access:** `kubernetesTalosAPIAccess`, `os:admin`, namespace `tuppr` only (ADR-0007).

### Rollback

- **Charts and images:** `git revert` the PR. Flux applies the previous version. HelmRelease remediation also rolls back failed upgrades automatically (ADR-0013).
- **Talos:** A/B partitions; `talosctl rollback`, per `runbooks/break-glass.md`.
- **Kubernetes:** no downgrade. That is why there is a minimum release age and the `.2`-patch bar.

## Consequences

- Stan reviews one batch of PRs a week. Low-risk bumps flow through on their own.
- The version pair duplicated between `talconfig.yaml` and tuppr is the only sanctioned duplication. It is held together by the Renovate groups and by `versions-match`.

## Alternatives considered

- **system-upgrade-controller:** the k3s/RKE2 equivalent, not used with Talos. Rejected.
- **Manual `talosctl upgrade`:** imperative, and not visible in git. Kept for break-glass only.
- **Flux image automation:** a second writer to git (ADR-0001 principle 4). Rejected.

## Compliance

- `versions-match` (ADR-0004).
- The Renovate dependency dashboard is reviewed by `audit`. PRs open longer than 30 days are reported.
