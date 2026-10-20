# ADR-0007: Operating system: Talos Linux on every node

- **Status:** Accepted
- **Date:** 2026-10-20
- **Deciders:** Stan (owner), Claude (proposer)
- **Related:** ADR-0008, ADR-0009, ADR-0012, ADR-0023

## Context

Zero drift has to start at the OS. Today `lab` runs Debian 13 with Docker, about 55 containers, host services (Sentinel, Reactor, dsh, Hermes) and hand-edited config, which shows what a mutable host turns into. The future nodes are mixed and weak: 2016–2019 laptops, Wyse 5070, HP t630/t640, ThinkCentre Tiny, EliteDesk Mini.

## Decision

1. **Talos Linux on every node.** It is immutable and API-driven, with no SSH, no shell, and no package manager. At decision time: Talos v1.14.4, Linux 6.18.
2. **Machine config comes only from git.** `01-talos/talconfig.yaml` plus `patches/`, rendered by **talhelper**. Secrets live in `talsecret.sops.yaml`. Config is applied with `mise run talos:apply`, never with hand-written `talosctl patch`.
3. **Images come from Talos Image Factory**, with three schematics declared in `talconfig.yaml`:

   | Schematic | Extensions | Extra kernel args | Used by |
   |---|---|---|---|
   | `zeus` | `siderolabs/amd-ucode`, `siderolabs/realtek-firmware`, `siderolabs/tailscale` | `amd_pstate=active`, `cpufreq.default_governor=performance` | zeus |
   | `amd` | `siderolabs/amd-ucode`, `siderolabs/realtek-firmware` | `cpufreq.default_governor=performance` | AMD workers (HP t630/t640, AMD laptops) |
   | `intel` | `siderolabs/intel-ucode`, `siderolabs/realtek-firmware` | `cpufreq.default_governor=performance` | Intel workers (Wyse 5070, ThinkCentre, EliteDesk, Intel laptops) |

   `realtek-firmware` covers zeus's RTL8125 2.5 GbE and RTL8153-class USB Ethernet adapters. GPU extensions are left out on purpose: no workload needs a GPU.
4. **Global patches** (`patches/global/`):
   - **Cluster:** `cluster.network.cni.name: none` and `cluster.proxy.disabled: true` (Cilium replaces both, ADR-0010). Pod subnet `10.244.0.0/16`, service subnet `10.96.0.0/12`, `discovery.enabled: true`.
   - **Features:** KubePrism enabled on `7445`, and `hostDNS.enabled` with `forwardKubeDNSToHost`.
   - **Nameservers:** `1.1.1.1` and `9.9.9.9`, so nodes don't depend on dorm or router DNS. Time servers stay at the Talos default (`time.cloudflare.com`).
   - **Kubelet:**
     - `nodeIP.validSubnets: [192.168.50.0/24]`, so the kubelet never picks the tailscale interface
     - `serializeImagePulls: false`
     - `evictionHard: {memory.available: 500Mi, nodefs.available: 10%, imagefs.available: 10%}`
     - `evictionSoft: {memory.available: 1Gi}` with `evictionSoftGracePeriod: {memory.available: 1m}`
   - **Reservations, heavy node:** `systemReserved: {cpu: 500m, memory: 1Gi}`, `kubeReserved: {cpu: 500m, memory: 1Gi}`.
   - **Reservations, light nodes** (set in `patches/worker/`): `systemReserved: {cpu: 250m, memory: 512Mi}`, `kubeReserved: {cpu: 250m, memory: 512Mi}`.
   - **Sysctls:**
     - `fs.inotify.max_user_instances: 8192`, `fs.inotify.max_user_watches: 1048576`
     - `net.core.rmem_max: 7500000`, `net.core.wmem_max: 7500000` (cloudflared QUIC buffers)
   - **No swap.** Talos has none by default and none is configured (ADR-0001 principle 12).
   - **Pod Security defaults:** `cluster.apiServer.admissionControl` sets the cluster-wide default to `enforce: restricted` (ADR-0021).
5. **Control-plane patches** (`patches/controlplane/`):
   - `allowSchedulingOnControlPlanes: true`
   - The VIP `192.168.50.10` on the physical interface (`deviceSelector: {physical: true}`)
   - `apiServer.certSANs` includes the VIP, `zeus`, and `zeus.<tailnet>.ts.net`; `machine.certSANs` likewise
   - Scheduler and controller-manager `bind-address: 0.0.0.0`, and etcd `listen-metrics-urls: http://0.0.0.0:2381`, so they can be scraped (ADR-0018)
   - `kubernetesTalosAPIAccess` enabled for namespace `tuppr` with role `os:admin` (ADR-0023)
6. **zeus-only patch:**
   - The tailscale `ExtensionServiceConfig`, with its auth key from SOPS, hostname `zeus`, tag `tag:olympus-node` (ADR-0012)
   - A `UserVolumeConfig` named `local-path` (ADR-0016)
   - The `EPHEMERAL` volume is capped at `maxSize: 100GiB`
7. **Only wired Ethernet.** Talos WiFi isn't supported for nodes.
8. **Access:**
   - Stan's `talosconfig` (role `os:admin`) is kept in his password manager and on his Mac.
   - Remote access goes over the tailnet to zeus only.
   - No other human or agent gets Talos API access.
9. **Hardware gate:** before a machine joins, it must pass the live-boot check in `runbooks/08-add-node.md`. Talos boots from USB in maintenance mode, and `talosctl get links,disks` must show its NIC and target disk.
10. **Disk encryption and SecureBoot** are deferred (ADR-0026). The trigger is re-evaluating before the first worker joins.

## Consequences

- The OS can't drift. Every node can be reproduced from git plus the age key.
- Host-level services (Sentinel, Reactor, dsh, Hermes, Coolify) can't run beside Kubernetes on zeus. They are dropped, or they come back later as apps.
- There is no SSH for debugging. Diagnosis uses `talosctl dmesg/logs/get/services` and Kubernetes itself, which is a different habit for Stan to learn.
- Talos runs upstream Kubernetes. Its control plane costs a little more RAM than k3s, which is negligible on zeus.

## Alternatives considered

- **k3s on Debian:** friendlier, and it keeps a shell. But keeping the host drift-free needs Ansible, and SSH is a permanent drift vector. Rejected for this goal.
- **Talos via Omni (SaaS):** adds an external dependency and a subscription for a 1–7 node cluster. Rejected.
- **Running Talos in VMs:** an extra layer that brings I/O contention. Rejected; bare metal.

## Compliance

- `mise run talos:diff node=<n>` shows any node-vs-git difference. A weekly automated comparison is deferred (ADR-0026).
- `versions-match` (ADR-0004).
