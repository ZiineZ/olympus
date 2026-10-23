# ADR-0031: Corrections from building the storage and security layer

- **Status:** Accepted (one per-policy exemption, `tuppr` from `memory-limit-equals-request`, added by ADR-0037)
- **Date:** 2026-10-21
- **Deciders:** Stan (owner), Claude (proposer)
- **Related:** ADR-0002 (supersedes the `olympus/policy` label), ADR-0016, ADR-0021 (supersedes rule 3's exemption mechanism and the `pvc-explicit-storage-class` row)

## Context

Writing the first storage component and the admission policies against the real charts and the real cluster surfaced two details:

1. **ADR-0021 rule 3 exempts namespaces labelled `olympus/policy: exempt`.** That label would have to be put on `kube-system`, which Kubernetes creates, not Flux. To label it from git, Flux would have to manage the `kube-system` Namespace object. Removing that object from git would then make Flux try to **delete `kube-system`**. That is a dangerous coupling just to carry one label.
2. **ADR-0016 rule 4 marked local-path-provisioner's install path "verify at implementation".** The project publishes no chart repository. Its chart lives only inside its git repo.

## Decision

1. **Policy exemptions are matched on the built-in label `kubernetes.io/metadata.name`.** Kubernetes sets it on every namespace and keeps it read-only. Each `ValidatingAdmissionPolicyBinding` lists its exemptions explicitly: `NotIn [kube-system, flux-system]`.
   - The custom label `olympus/policy` no longer exists. It is removed from the custom-keys table.
   - The exemption list lives in the binding files (`04-platform/03-security/admission-policies/app/`), the only place it exists.
2. **local-path-provisioner is installed by a HelmRelease from a `GitRepository` source,** pinned to the project's release tag, using the chart folder inside it.
   - A git-hosted chart is the third allowed chart source, after OCI and classic Helm repositories (ADR-0013 rule 5).
   - The `render` check templates it from a shallow clone at that tag.
3. **`pvc-explicit-storage-class` is a CI rule, not an admission policy.** The `DefaultStorageClass` admission plugin fills in `storageClassName` *before* validating policies run, so the policy could never fire (proven in the rehearsal). The `render` check now rejects any PVC or StatefulSet `volumeClaimTemplate` in git without an explicit `storageClassName`. This supersedes that row of ADR-0021's policy table.
4. **The rehearsal's user volume is a Docker-only stand-in.** `01-talos/patches/rehearsal/` holds a `UserVolumeConfig` of type `directory`, which Talos 1.14 supports. Only `mise run rehearsal:up` applies it. zeus gets the partition-backed volume of the same name in phase 2. This extends ADR-0028's "the folder is the list" with one folder that never reaches real nodes.
5. **The node that provides volumes is the `${STORAGE_NODE}` variable** (`zeus`) in `cluster-settings.yaml`. The rehearsal sets it to its own node name inside its allowed three-file diff (ADR-0025).

## Consequences

- Flux never owns `kube-system` or other namespaces it didn't create.
- The exemption list is visible in exactly the files that enforce it.

## Alternatives considered

- **Keep `olympus/policy` and manage `kube-system` with `prune: disabled`:** works, but one forgotten annotation away from deleting `kube-system`. Rejected.
- **Install local-path from raw upstream manifests:** loses Helm values (`Retain`, `nodePathMap`, resources, pinned images). Rejected.

## Compliance

- `render` validates the policies and templates the git-hosted chart.
- The rehearsal checks that each policy warns on a violating object and stays quiet on a compliant one.
