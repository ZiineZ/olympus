# ADR-0039: Talos node config for real hardware

- **Status:** Accepted
- **Date:** 2026-10-23
- **Deciders:** Stan (owner), Claude (proposer)
- **Related:** ADR-0028 (implements rule 5, `talos:render`), ADR-0007, ADR-0009, ADR-0016

## Context

The Docker rehearsal never needed a static address, a VIP, an install disk or a disk-backed volume. zeus needs all of them. Rendering a real config with Talos 1.14.4 found three places where the documented or obvious form is wrong.

## Decision

1. **The node's own documents come from its `cluster.yaml` entry.** `talos:render` generates them:
   - `HostnameConfig` (the node's name)
   - `LinkAliasConfig` `lan`, which selects the NIC by `mac(link.permanent_addr)`
   - `LinkConfig` `lan`: the static address, plus the default route through `network.gateway`
   - `ResolverConfig` from `network.nameservers`
   - on control planes, `Layer2VIPConfig` for the endpoint's address
   - an `UnattendedInstallConfig` disk selector

   `cluster.yaml` gains `network` (prefix, gateway, nameservers) and a per-node `mac`, recorded from the live boot.
2. **The NIC is chosen by MAC address**, never by interface name. The name the kernel picks varies with hardware and firmware; the permanent address doesn't. Talos's CEL needs `mac(…)`: a plain string comparison against `permanent_addr` (bytes) is rejected.
3. **The install disk is matched with `UnattendedInstallConfig`** (`disk.transport == "<installDisk>"`). Talos 1.14 moved install settings into that document, and `gen config` writes it with the Image Factory installer image. The older `machine.install` fields conflict with it.
4. **Role patches use the role flags** (`--config-patch-control-plane` or `--config-patch-worker`). Plain `--config-patch` patches both roles even when only one is written out. On the worker, the control-plane taint delete then fails.
5. **`patches/metal/<role>/`** holds real-hardware-only documents, applied by `talos:render` and never by the rehearsal, mirroring `patches/rehearsal/`. The first is zeus's disk layout:
   - EPHEMERAL (`/var`) capped at 150 GiB
   - the `local-path` user volume on the system disk, at least 50 GiB, growing to fill the rest

   Both are calibration knobs.
6. **DNS uses public resolvers (1.1.1.1, 9.9.9.9)**, so node DNS doesn't depend on the router.
7. **Secrets:**
   - `talos:secrets` pipes `talosctl gen secrets` straight into `sops`, once per cluster.
   - `talos:render` decrypts them into the git-ignored `01-talos/clusterconfig/` for the length of the render.
   - Everything it writes there is mode 600. The rendered configs hold the same secrets, which is why the folder is git-ignored.

## Consequences

- Installing zeus is: live boot, record the MAC, then `talos:secrets`, `talos:render`, `talos:apply --insecure`, `talos:bootstrap`, then runbook 02's apps (runbook `02-bootstrap.md`).
- **Verified offline:** a rendered zeus config passes `talosctl validate --mode metal`. Talos API access, the volumes, the VIP and every existing patch apply cleanly.
- **Not verified:** a real install. The first one is zeus.

## Alternatives considered

- **Interface names in `cluster.yaml`:** they change with firmware and between models. Rejected.
- **DHCP with a router reservation:** the address would live outside git (ADR-0009 rule 1). Rejected.
- **The volume in `patches/controlplane/`:** the rehearsal applies that folder, and Docker can't partition a disk. Rejected for the metal folder.

## Compliance

- The `talos` check validates every patch file, including `patches/metal/`, and each node's `mac` format.
- `talos:render` runs `talosctl validate --mode metal` on every rendered config.
