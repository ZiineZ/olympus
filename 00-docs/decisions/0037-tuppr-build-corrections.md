# ADR-0037: Corrections from building tuppr

- **Status:** Accepted
- **Date:** 2026-10-23
- **Deciders:** Stan (owner), Claude (proposer)
- **Related:** ADR-0023 (amends the tuppr section), ADR-0021 and ADR-0031 (one exemption), ADR-0007

## Context

Building tuppr 0.5.9 against Talos 1.14 and Olympus's admission policies settled the details ADR-0023 left open, and found two conflicts.

## Decision

1. **Talos API access uses the Talos 1.14 document `KubeTalosAPIAccessConfig`**, in `01-talos/patches/controlplane/talos-api-access.yaml`: role `os:admin`, namespace `tuppr` only.
   - tuppr's docs still show the older `machine.features.kubernetesTalosAPIAccess` field "on every node". In 1.14 the document is control-plane only: `talosctl validate` rejects it on workers. That's enough, because pods reach the Talos API through the control plane.
2. **The `tuppr` namespace is exempt from `memory-limit-equals-request`, and from no other policy.** tuppr's upgrade Jobs hard-code memory 64 Mi request / 512 Mi limit with no override. Once the policy switches to Deny, every upgrade Job would be refused. The other policies hold:
   - the Jobs set CPU and memory requests, a memory limit, no CPU limit, and the `app.kubernetes.io/name` label
   - their `talosctl` image is pinned by tag and digest in both CRs (`spec.talosctl.image`)
3. **Health gates:** before each node, every Node Ready and every Flux Kustomization Ready, as CEL checks in both CRs.
   - Parallelism is tuppr's default of 1. It isn't written out because the schema catalog's copy of the CRD predates the field.
   - Talos images keep each node's own Image Factory schematic: tuppr swaps only the version of the node's current install image, so no per-node image is configured.
4. **The chart** comes from `oci://ghcr.io/home-operations/charts/tuppr`, verified with cosign against tuppr's release workflow.
   - Its controller image is pinned by digest, at priority `platform` (the chart defaults to `system-node-critical`).
   - Upgrade Jobs keep tuppr's default, `system-node-critical`, so an upgrade isn't starved on a full node.
5. **Monitoring** follows ADR-0034: a `VMPodScrape` and three of the chart's alerts, as a `VMRule`:
   - `TalosUpgradeFailed`, `KubernetesUpgradeFailed` (critical)
   - `UpgradeJobRunningTooLong` (warning)
6. **`versions-match`** is implemented in `mise run check`. `01-talos/cluster.yaml`'s versions must equal the CRs.
7. **Not rehearsed:** Talos-in-Docker can't upgrade itself, and the rehearsal cluster was already torn down. The manifests are validated by CI, and the Talos patch by `talosctl validate` on the full rendered config. The first real run happens on zeus.

## Consequences

- A Talos bump touches five values in four files: cluster.yaml, the TalosUpgrade version, the talosctl image in both CRs, and the mise talosctl pin. Renovate's `talos` group bumps them together, and two checks catch a split.
- Upgrades are blocked while any Kustomization is unhealthy. That's intended: an upgrade never starts on a broken cluster.

## Alternatives considered

- **Exempt `tuppr` from all policies:** hides the four policies its Jobs already satisfy. Rejected.
- **Keep `memory-limit-equals-request` at Warn forever:** weakens it for every app. Rejected.
- **Set `parallelism: 1` and skip schema validation for tuppr CRs:** loses validation of every other field. Rejected.

## Compliance

- `versions-match`, `talos` and `render` in `mise run check`.
- `audit`: the `memory-limit-equals-request` binding exempts exactly `kube-system`, `flux-system` and `tuppr`.
