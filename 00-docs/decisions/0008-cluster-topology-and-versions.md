# ADR-0008: Cluster topology and Kubernetes version policy

- **Status:** Accepted
- **Date:** 2026-10-20
- **Deciders:** Stan (owner), Claude (proposer)
- **Related:** ADR-0002, ADR-0007, ADR-0009, ADR-0016, ADR-0023

## Context

There is one capable machine now (zeus, 24 GB). Later about 4 weak workers will be added (around 8 GB each, consumer SSDs, 1 GbE). The topology must work with one node today and grow without restructuring.

## Decision

1. **One control-plane node, zeus, which also runs workloads.** It runs a single etcd member.
2. **The API endpoint is the VIP `https://192.168.50.10:6443` from day 1**, never zeus's own IP. Adding control-plane nodes later then changes nothing for clients, kubeconfigs, or Cilium.
3. **Workers** have `olympus/tier=light`. Stateless workloads may be scheduled there. Stateful workloads are pinned to `olympus/tier=heavy` (ADR-0016).
4. **HA control plane** (hera, poseidon): deferred. Trigger: there are 3 machines, each with ≥16 GB RAM, an SSD, and wired gigabit. Until then, etcd stays off laptops and thin clients. Cheap consumer disks and fsync latency are the main etcd failure mode in homelabs.
5. **Kubernetes version policy:**
   - Run the newest Kubernetes minor that (a) the pinned Talos release supports, and (b) has a `.2` or later patch release.
   - Adopt a new minor within about 2 months of it meeting that bar.
   - Never skip a minor.
   - At decision time: **Kubernetes v1.36.x** on Talos v1.14.x. v1.37 is out but doesn't yet meet the bar.
6. **Scale envelope:** up to 3 control-plane nodes and 6 workers (the ADR-0009 IP plan). Going beyond that needs a new ADR.

## Consequences

- If zeus is down, the cluster is down. That is acceptable, because the heavy and stateful workloads live on zeus anyway.
- Recovery is a rebuild from git plus a data restore (ADR-0025). etcd snapshots are not part of recovery (ADR-0026).

## Alternatives considered

- **3 control planes now, including laptops:** etcd on weak disks causes more outages than it prevents. Rejected.
- **Dedicated control plane with no workloads:** wastes the only strong machine. Rejected.

## Compliance

- `talconfig.yaml` holds the endpoint. The `substitutions` check ensures manifests use the `${CLUSTER_API_VIP}` variable rather than a literal IP.
- The `upgrade` skill enforces the version policy.
