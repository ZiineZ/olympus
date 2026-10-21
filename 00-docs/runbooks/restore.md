# Runbook · Restore a volume from backup

Backups are restic snapshots, made by k8up, of every PVC in a namespace that includes `03-cluster/components/backup`. They go to `<BACKUP_BUCKET>/<namespace>` on Cloudflare R2 (ADR-0017). A restore is a **PR**, like every other change (ADR-0001 principle 3).

## 1. Find the snapshot

```bash
kubectl -n <namespace> get snapshots.k8up.io --sort-by=.spec.date
```

Each row is one restic snapshot: its date, and the PVC path it holds. Leave `snapshot:` out of the Restore to use the newest.

## 2. Restore by PR

Add `restore.yaml` to the namespace's `app/` folder, list it in `app/kustomization.yaml`, and open a PR.

- **Drill or inspection:** restore into a new, empty claim `restore-drill`, so nothing running is touched.
- **Real recovery:** first scale the app to 0 (same PR), then restore into the app's own claim.

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: restore-drill
spec:
  storageClassName: local-path
  accessModes: [ReadWriteOnce]
  resources: {requests: {storage: 1Gi}} # at least the size of the original
---
apiVersion: k8up.io/v1
kind: Restore
metadata:
  name: restore-YYYYMMDD # unique per restore
spec:
  podConfigRef: {name: backup} # runs as restricted, like the backups
  # snapshot: <id>           # optional: a specific snapshot from step 1
  restoreMethod:
    folder:
      claimName: restore-drill # or the app's own claim, for a real recovery
  backend: # the same as 03-cluster/components/backup/schedule.yaml
    repoPasswordSecretRef: {name: k8up-repo, key: RESTIC_PASSWORD}
    s3:
      endpoint: ${BACKUP_S3_ENDPOINT}
      bucket: ${BACKUP_BUCKET}/<namespace>
      accessKeyIDSecretRef: {name: k8up-repo, key: AWS_ACCESS_KEY_ID}
      secretAccessKeySecretRef: {name: k8up-repo, key: AWS_SECRET_ACCESS_KEY}
```

**Merging is the restore.** Flux applies the Restore, and k8up runs it once.

```bash
kubectl -n <namespace> get restores.k8up.io   # Completed?
```

## 3. Clean up by PR

Remove `restore.yaml` (and `restore-drill`) in a follow-up PR. If it was a real recovery, scale the app back up in the same PR.

## Quarterly drill (ADR-0025)

Restore the newest `backup-canary` snapshot into `restore-drill` in namespace `backup-canary`. Then compare: the restored `heartbeat.log` must end with a timestamp from the last backup, within 25 hours. Record the date here:

| Date | Snapshot | Newest timestamp in the restore | Result |
|---|---|---|---|
