# ADR-0025: Disaster recovery and the rehearsal environment

- **Status:** Accepted (rule 6's `values.yaml` is `helmrelease.yaml` per ADR-0029)
- **Date:** 2026-10-20
- **Deciders:** Stan (owner), Claude (proposer)
- **Related:** ADR-0001, ADR-0014, ADR-0015, ADR-0017

## Context

"The cluster is cattle" only holds if a full rebuild actually works and has been practiced. Stan also wants to validate the entire stack on his MacBook before zeus is wiped, and **only when he says "go"**.

## Decision

### Disaster recovery

1. **Targets:** RPO 24 h (daily backups, ADR-0017). RTO about 1 h for platform plus data on replacement hardware.
2. **What must survive outside the cluster** (the full list, nothing else is needed):
   - the GitHub repo `olympus`
   - the age private key (password manager + paper, ADR-0014)
   - the restic password (password manager, ADR-0017)
   - accounts: GitHub, Cloudflare, Tailscale, healthchecks.io, Anthropic, the object storage provider

   `talosconfig` and the admin kubeconfig are **regenerated** from `talsecret.sops.yaml`, so they aren't needed.
3. **Procedure (`runbooks/disaster-recovery.md`):**
   1. Bootstrap per ADR-0015 on the replacement zeus.
   2. Flux rebuilds every component.
   3. A PR adds a `Restore` CR per backed-up namespace.
   4. Verify, then remove the Restore CRs in a follow-up PR.
4. **Drills:**
   - **Quarterly:** restore `athena-home` into a scratch PVC `restore-drill` and compare the files. Record the date in the runbook.
   - **Yearly, or before any risky change:** a full rebuild in the rehearsal environment.

### Rehearsal environment

5. **Where:** Stan's MacBook, with `talosctl cluster create` using the Docker provisioner (Docker Desktop or OrbStack, ≥8 GB RAM assigned).
   - Cluster name `olympus-rehearsal`, 1 control plane, optionally 1 worker.
   - Only the global Talos patches are applied, as `--config-patch` files. The hardware-specific ones (VIP, UserVolume, extensions, kernel args) aren't.
   - **It starts only on Stan's explicit "go".**
6. **Branch:** a throwaway branch `rehearsal/<yyyy-mm-dd>`, never merged and deleted afterwards. Its diff against `main` is limited to **exactly these files**:
   - `03-cluster/cluster-settings.yaml`: LB pool on the Docker network, `TS_HOST_SUFFIX=-rehearsal`
   - `03-cluster/flux-instance/app/values.yaml`: `sync.ref` points at the branch
   - `04-platform/01-network/kustomization.yaml`: drops `cloudflared` and `external-dns`, so the rehearsal can never touch public DNS
7. **What the rehearsal proves:**
   - the bootstrap ordering, and the Flux handover
   - Cilium core, Hubble, the Gateway
   - the admission policies vs real charts
   - the VictoriaMetrics stack
   - Kite in config-file mode with read-only RBAC
   - Athena's RBAC and egress policy
   - the k8up backup + restore round trip
   - the CI checks against a real render
8. **What it can't prove** (this is checked on zeus in phase 2):
   - L2 announcements on the real router
   - Talos extensions and kernel args
   - the UserVolume layout
   - the tailscale extension on the node
   - real disk and NIC drivers
9. **Teardown:** `talosctl cluster destroy`, delete the branch, delete the `-rehearsal` tailnet devices.

## Consequences

- Recovery is a practiced procedure, not a hope.
- The first real install on zeus reuses a path that already worked once.

## Alternatives considered

- **etcd snapshots as the primary DR:** restores state that git already defines, and can bring back drift. Deferred as an optional speed-up (ADR-0026).
- **Rehearsing in a VM on `lab`:** `lab` is already memory-tight, at about 12 GiB used plus swap. Rejected.

## Compliance

- Each drill date is recorded in `runbooks/disaster-recovery.md`. `audit` flags a drill older than 100 days.
- `audit` flags a rehearsal branch diff touching any file outside rule 6.
