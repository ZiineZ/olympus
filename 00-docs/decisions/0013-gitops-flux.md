# ADR-0013: GitOps engine: Flux, installed and managed by the Flux Operator

- **Status:** Accepted
- **Date:** 2026-10-20
- **Deciders:** Stan (owner), Claude (proposer)
- **Related:** ADR-0003, ADR-0004, ADR-0014, ADR-0015

## Context

Every cluster object must come from git. Manual changes must be reverted, and removed manifests must be deleted. The engine should be lean on 8 GB nodes and decrypt SOPS natively. It should also give a beginner a visible picture of what is happening.

## Decision

1. **Flux v2 via the Flux Operator**, with a single `FluxInstance` named `flux`. At decision time: Flux v2.9.6, operator v0.61.0.
2. **FluxInstance spec:**
   - `distribution.version` pinned to an exact patch; registry `ghcr.io/fluxcd`
   - Components: `source-controller`, `kustomize-controller`, `helm-controller`, `notification-controller`. **No** image-reflector or image-automation controllers (ADR-0001 principle 4).
   - `cluster.networkPolicy: true`, `cluster.domain: cluster.local`
   - **Sync:** `kind: GitRepository`, `url: ssh://git@github.com/<stan>/olympus`, `ref: refs/heads/main`, `path: 03-cluster`, `interval: 1m`, `pullSecret: flux-system`. The pull secret is a **read-only deploy key**, kept as a SOPS secret in `02-bootstrap/resources/`.
3. **Defaults for every Flux `Kustomization`**, applied by kustomize patches in the FluxInstance, so they are written once:
   - `interval: 10m`, `retryInterval: 2m`, `timeout: 5m`
   - `prune: true`, `wait: true`
   - `decryption: {provider: sops, secretRef: {name: sops-age}}`
   - `postBuild.substituteFrom: [{kind: ConfigMap, name: cluster-settings}]`
4. **Defaults for every `HelmRelease`**, applied the same way:
   - `interval: 30m`
   - `driftDetection.mode: enabled`
   - `install.crds: CreateReplace`, `upgrade.crds: CreateReplace`
   - `install.remediation.retries: 3`
   - `upgrade.remediation: {retries: 3, strategy: rollback}`, `upgrade.cleanupOnFail: true`
   - `rollback.cleanupOnFail: true`
5. **Charts** come from `OCIRepository` sources wherever the publisher offers OCI, pinned to an exact tag. Cosign verification (`spec.verify`) is enabled where the publisher signs. `HelmRepository` is used only where no OCI registry exists.
6. **Ordering** uses `dependsOn` between Flux Kustomizations. `03-cluster/layers.yaml` chains `01-network → 02-storage → 03-security → 04-observability → 05-operations → 06-agent → apps`. Inside a group, components declare their own `dependsOn`.
7. **Instant sync:** a `Receiver` of type `github` is exposed publicly at `flux-webhook.${PUBLIC_DOMAIN}` through tier 1 (ADR-0011). It is HMAC-protected with a secret stored in SOPS, and triggers a GitRepository reconcile on push to `main`.
8. **Flux Web UI** (built into the operator) is exposed on the tailnet (ADR-0011). Its RBAC for humans is view-only (ADR-0012).
9. **Notifications:** a Flux `Alert` sends to an Alertmanager `Provider` for any failed reconcile and any drift correction. Those reach ntfy (ADR-0019).

## Consequences

- Manual cluster changes are reverted within 10 minutes for Kustomizations and 30 minutes for HelmReleases. Every revert is alerted.
- Deleting a component folder deletes its objects. PVC data is protected by the `Retain` reclaim policy (ADR-0016).
- With no image automation, bumps for Stan's own app images arrive as Renovate PRs (ADR-0023).

## Alternatives considered

- **Argo CD:** a richer UI, but heavier (repo-server, Redis, app-controller, server). Its Helm support is template-only, and it has no native SOPS. Kite + Hubble + the Flux Web UI cover the "watch it work" goal. Rejected.
- **The `flux bootstrap` CLI** (which commits `gotk-components.yaml`): an older pattern. The operator manages Flux declaratively instead. Rejected.

## Compliance

- `helmrelease-defaults` and `render` checks (ADR-0004).
- `audit` reports any Flux object that is suspended or not Ready.
