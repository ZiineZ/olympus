# ADR-0032: A backup canary as the first backup consumer

- **Status:** Accepted
- **Date:** 2026-10-21
- **Deciders:** Stan (owner), Claude (proposer)
- **Related:** ADR-0017 (amends rule 7's first consumers), ADR-0019, ADR-0025

## Context

ADR-0017 rule 7 named Athena's and Kite's PVCs as the first backup consumers and restore-drill targets. They arrive in later layers, so k8up would land with nothing to back up, and the reusable `backup` component would have no user. That means:
- nothing to test end to end
- nothing for `BackupStale` to watch
- nothing safe to restore in the quarterly drill

## Decision

1. **Component `04-platform/02-storage/backup-canary`** (namespace `backup-canary`):
   - a pinned busybox pod that appends a UTC timestamp to `/data/heartbeat.log` every hour, keeping the last 1000 lines
   - a 64 Mi `local-path` volume
   - restricted security context and UID 1000 (the backup pods' UID), at `platform` priority
2. **It includes `03-cluster/components/backup`,** so it is backed up daily like any app. It is also the template for how apps opt in.
3. **It is the target of the quarterly restore drill** (`runbooks/restore.md`). A restore is correct when its newest timestamp is at most 25 hours old.
4. **`BackupStale`** (ADR-0019, observability layer) watches it from day one.
5. **Athena and Kite opt in when they arrive,** as ADR-0017 planned. The canary stays as the always-present, data-free consumer.

## Consequences

- Backups and restores are proven continuously, before any real data exists.
- Cost: one tiny pod (8 Mi) and a few KB of R2 storage.

## Alternatives considered

- **Wait for Athena/Kite:** backups stay untested until then. Rejected.
- **A one-off manual test:** proves it once, then rots. Rejected.

## Compliance

- `render` builds the canary with the component, including the per-namespace bucket path.
- The drill table in `runbooks/restore.md`, and `audit`'s 100-day check (ADR-0025).
