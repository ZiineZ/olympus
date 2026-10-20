# ADR-0009: Network addressing and hardware requirements

- **Status:** Accepted
- **Date:** 2026-10-20
- **Deciders:** Stan (owner), Claude (proposer)
- **Related:** ADR-0002, ADR-0007, ADR-0010, ADR-0011

## Context

Stan lives in a dorm. Internet arrives over a WiFi repeater on the dorm network `192.168.0.0/24`, whose DHCP he doesn't control. Today zeus (`lab`) itself is on WiFi, and its 2.5 GbE port is unplugged. Stan's own router (in router mode, behind the repeater) and an 8-port gigabit switch are planned.

## Decision

### Subnet plan

The LAN is `192.168.50.0/24`. It must not overlap the dorm `192.168.0.0/24`, the pod CIDR `10.244.0.0/16`, the service CIDR `10.96.0.0/12`, or the tailnet `100.64.0.0/10`.

| Range | Use |
|---|---|
| `.1` | router |
| `.2`–`.9` | network gear (switch management, if any) |
| `.10` | Kubernetes API VIP (`CLUSTER_API_VIP`) |
| `.11`–`.13` | control planes: zeus `.11`, hera `.12`, poseidon `.13` |
| `.21`–`.26` | workers: ares `.21`, artemis `.22`, apollo `.23`, hephaestus `.24`, demeter `.25`, dionysus `.26` |
| `.100`–`.199` | router DHCP pool (laptops, phones), the **only** dynamic range |
| `.200`–`.229` | Cilium LoadBalancer IP pool (`LB_POOL_START`/`LB_POOL_END`) |
| `.230`–`.254` | spare |

### Rules

1. **Node IPs are static in `talconfig.yaml`.** No router DHCP reservations are used, since those would live outside git. The router's only job is to keep its DHCP pool inside `.100`–`.199`.
2. **Router requirements:**
   - router mode, with the WAN taking DHCP from the repeater
   - double NAT is accepted, because all remote access is outbound (Tailscale, Cloudflare Tunnel)
   - it must accept gratuitous ARP for the LB pool (tested in rehearsal, runbook `00-prep.md`)
   - **No port forwarding, ever.**
3. **Switch:** any unmanaged 8-port gigabit switch. No VLANs are needed (a TL-SG108E or GS308E is fine but not required). MTU is 1500.
4. **Every node is wired.** No WiFi on nodes.
5. **IPv4 only.** Dual-stack is deferred (ADR-0026).

### Hardware requirements for any new node

- x86-64 and UEFI USB boot.
- **RAM:** ≥8 GB (4 GB is the hard minimum).
- **Disk:** an SSD ≥120 GB. eMMC is never the system disk; thin clients get a cheap M.2 SATA SSD.
- **Network:** gigabit Ethernet, built in or a USB 3 RTL8153-class adapter.
- **BIOS:** power-on after AC loss, performance or max-fan profile allowed (ADR-0001 principle 11), and boot from the SSD after install.
- **Laptops:** a healthy battery is kept, since it acts as a small UPS. Use a charge limit if the BIOS offers one. A swollen battery is removed.
- **zeus BIOS:**
  - set the UMA frame buffer to the minimum: 24 GB is installed but only about 19 GiB is visible today, because roughly 5 GB is reserved for the iGPU
  - power-on after AC loss
  - performance mode
  - SecureBoot off until ADR-0026 says otherwise

## Consequences

- With static IPs from git, the router can be swapped without touching the cluster.
- LoadBalancer IPs are reachable on the LAN, but nothing depends on that yet (ADR-0011).

## Alternatives considered

- **DHCP reservations on the router:** that would be config outside git. Rejected.
- **Bridging onto the dorm network:** no control, and a collision risk. Rejected.

## Compliance

- `talconfig.yaml` is the only place node IPs appear. The `substitutions` check catches literal IPs in manifests outside `cluster-settings.yaml`.
- The hardware gate is in `runbooks/08-add-node.md`.
