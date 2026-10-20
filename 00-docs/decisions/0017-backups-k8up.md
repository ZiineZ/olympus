# ADR-0017: Backups: k8up (restic) to off-site object storage

- **Status:** Accepted
- **Date:** 2026-10-20
- **Deciders:** Stan (owner), Claude (proposer)
- **Related:** ADR-0001, ADR-0016, ADR-0019, ADR-0025

## Context

The cluster is disposable, but PVC data isn't (ADR-0001 principle 8). Storage is local-path, which has no CSI snapshots (ADR-0016). The plan had first assumed VolSync, but VolSync's main advantage, restoring automatically when a PVC is created (its volume populator), **requires snapshot-capable storage**. Stan suggested k8up.

## Decision

1. **k8up** (namespace `k8up`, Helm chart from the k8up project; at decision time chart 4.10.0 / operator v2.16.0). It is restic-based.
   - It backs up **every PVC in a namespace** from one `Schedule`, so a PVC can't be forgotten.
   - It handles ReadWriteOnce volumes by running one backup job per node, on the node where the PVC is mounted.
2. **Opting in:** a namespace opts in by including the kustomize component `03-cluster/components/backup`. The component adds:
   - a `Schedule` named `backup`, with `backend.s3` pointing at bucket `olympus-backups`, prefix `/<namespace>`
   - the Secret `k8up-repo.sops.yaml` (restic password + S3 credentials, one shared file referenced by the component)
   - **Schedule:**
     - backup `@daily-random`
     - check `@weekly-random`
     - prune `@weekly-random` with `retention: {keepDaily: 7, keepWeekly: 4, keepMonthly: 6}`
3. **The restic password** is also stored in Stan's password manager. Without it, the backups are unreadable.
4. **App-consistent backups** use k8up's pre-backup command annotations (`k8up.io/backupcommand`) on the workload that owns a database. Postgres under CloudNativePG uses CNPG's own backups instead (ADR-0026).
5. **Restore** is declarative: a `Restore` CR is committed by PR into the namespace's folder, then removed in a follow-up PR once it completes. The procedure is `runbooks/restore.md`.
6. **Monitoring:**
   - k8up metrics are scraped (ADR-0018).
   - Alert `BackupFailed` fires on any failed job.
   - Alert `BackupStale` fires when there has been no successful backup for a namespace in 36 hours.
   - Both go to ntfy (ADR-0019).
7. **First consumers**, since there are no apps yet:
   - namespace `athena`: session state PVC
   - namespace `kite`: SQLite PVC

   These also serve as the first restore drill (ADR-0025).
8. **Target: Cloudflare R2** (Stan, 2026-10-20). It has no egress fees, so restores are free. It reuses the Cloudflare account that already runs DNS, Tunnel, and Access.
   - **Bucket** `olympus-backups`, with an R2 API token limited to Object Read & Write on that bucket only, stored in `k8up-repo.sops.yaml`.
   - **Endpoint:** `https://<account-id>.r2.cloudflarestorage.com`.
   - **Known trade-off:** Cloudflare is now a single provider for both public ingress and backups. A Cloudflare account lockout would hit both. The restic password and the repo stay outside Cloudflare (ADR-0025).

## Consequences

- A simple, uniform backup path exists before the first real app lands.
- Restores are a reviewed PR, not an automatic process. Acceptable, since the RTO target is about 1 hour (ADR-0025).
- Backups are file-level and crash-consistent unless a pre-backup command is set.

## Alternatives considered

- **VolSync:** its populator needs snapshots (unavailable on local-path), and it needs a `ReplicationSource` per PVC. Rejected for now. It is reconsidered if snapshot-capable storage ever arrives.
- **Backblaze B2:** also fine, and it would split providers. Rejected for simplicity: one account fewer.
- **Velero:** the cluster-object backup is redundant with GitOps, and it is heavier. Rejected.
- **kopiur:** promising, but too young at decision time. Watch-listed (ADR-0026).

## Compliance

- The `BackupStale` alert.
- A quarterly restore drill (`runbooks/restore.md`).
- `audit` lists namespaces that have PVCs but no `backup` component, and requires an explicit opt-out annotation `olympus/backup: none` with a reason.
