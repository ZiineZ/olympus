# ADR-0016: Storage: local-path on zeus, Retain, no replicated storage

- **Status:** Accepted
- **Date:** 2026-10-20
- **Deciders:** Stan (owner), Claude (proposer)
- **Related:** ADR-0007, ADR-0008, ADR-0017, ADR-0026

## Context

Future workers are weak: about 8 GB RAM, consumer SSDs, 1 GbE. Replicated block storage (Longhorn, Rook-Ceph) costs RAM on every node, hammers cheap disks, and is slow over 1 GbE. The home-operations community runs Ceph only on dedicated disks. Data durability can come from backups (ADR-0017) instead of replication.

## Decision

1. **One StorageClass, `local-path`** (rancher local-path-provisioner, namespace `local-path-provisioner`), marked as the default class:
   - `volumeBindingMode: WaitForFirstConsumer`
   - `reclaimPolicy: Retain`. Removing a component folder makes Flux prune the PVC, but the data survives on disk. The `audit` skill reports orphaned PVs.
   - The provisioner `nodePathMap` lists **zeus only**: `/var/mnt/local-path`. That is the Talos `UserVolumeConfig` named `local-path`, which uses all disk space beyond the `EPHEMERAL` cap of 100 GiB (ADR-0007).
   - There is deliberately no default path for other nodes. A PVC scheduled on a worker fails to bind, which enforces rule 2.
2. **Stateful workloads always use `nodeSelector: {olympus/tier: heavy}`.**
3. **The namespace `local-path-provisioner` is labelled Pod Security `privileged`**, because its helper pods use hostPath. This exception is recorded in `conventions.md`.
4. **Install source:** upstream manifests at a pinned tag via a `GitRepository` + kustomize, with the config patched. The project publishes no Helm chart. *Verify the install path at implementation.*
5. **Every PVC sets `storageClassName: local-path` explicitly.** A sizing note goes in the component's `values.yaml`.
6. **Replicated storage** (Longhorn, Rook-Ceph) is deferred. Trigger: a workload that genuinely needs to survive zeus being down (ADR-0026).

## Consequences

- Fast NVMe-local volumes with zero RAM overhead on the workers.
- A stateful app is unavailable while zeus is down. That is accepted (ADR-0008).
- No volume snapshots, which drives the backup choice (ADR-0017).

## Alternatives considered

- **Longhorn:** needs the iscsi extension on every node, about 0.5–1 GB RAM per node, and replication traffic over 1 GbE. Rejected for now.
- **OpenEBS ZFS/LVM LocalPV:** gives snapshots, but adds ZFS/LVM on Talos for one feature. Rejected.
- **`Delete` reclaim policy:** one wrong folder deletion would wipe data. Rejected.

## Compliance

- A ValidatingAdmissionPolicy requires `storageClassName` on every PVC (ADR-0021).
- `audit` lists Released or orphaned PVs, and stateful pods not on `olympus/tier=heavy`.
