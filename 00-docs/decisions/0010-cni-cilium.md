# ADR-0010: CNI: Cilium for networking, load balancing, Gateway API, policy and flow visibility

- **Status:** Accepted
- **Date:** 2026-10-20
- **Deciders:** Stan (owner), Claude (proposer)
- **Related:** ADR-0007, ADR-0009, ADR-0011, ADR-0022, ADR-0024

## Context

Olympus needs several things:

- pod networking and kube-proxy replacement
- LoadBalancer IPs on bare metal
- an ingress controller now that ingress-nginx is retired (March 2026)
- network policies, including FQDN egress rules for Athena
- traffic flows that are satisfying to watch

Each would normally be a separate component.

## Decision

**Cilium** covers all of them. At decision time: v1.20.3. It is installed by bootstrap and then owned by Flux (ADR-0015). Values (`04-platform/01-network/cilium/app/values.yaml`):

- **Talos integration:**
  - `k8sServiceHost: localhost`, `k8sServicePort: 7445` (KubePrism)
  - `cgroup.autoMount.enabled: false`, `cgroup.hostRoot: /sys/fs/cgroup`
  - `securityContext.capabilities` set per the Talos Cilium guide (no `SYS_MODULE`)
- **Datapath:**
  - `kubeProxyReplacement: true`
  - `routingMode: native`, `autoDirectNodeRoutes: true`, `ipv4NativeRoutingCIDR: 10.244.0.0/16` (all nodes share one L2 segment)
  - `ipam.mode: kubernetes`
  - `bpf.masquerade: true`
  - netkit datapath (auto-selected by 1.20 on supported kernels)
  - `bandwidthManager: {enabled: true, bbr: true}`
  - `loadBalancer.algorithm: maglev`
- **Load balancing:**
  - `l2announcements.enabled: true`, `externalIPs.enabled: true`
  - `k8sClientRateLimit` raised per the L2 announcements guide
  - A `CiliumLoadBalancerIPPool` covering `${LB_POOL_START}`–`${LB_POOL_END}`, plus a `CiliumL2AnnouncementPolicy` on the physical interfaces. Both live in a second Kustomization, `cilium-config`, which `dependsOn: cilium`.
- **Gateway API:** `gatewayAPI.enabled: true`. The CRDs come from component `gateway-api-crds`: the standard channel, at the same version Cilium supports (decision time: Gateway API v1.6.3).
- **Hubble:**
  - `hubble.relay.enabled: true`, `hubble.ui.enabled: true`
  - `hubble.metrics.enabled: [dns, drop, tcp, flow, port-distribution, icmp, "httpV2:exemplars=true;labelsContext=source_namespace,destination_namespace"]`
  - The Hubble UI is exposed on the tailnet (ADR-0012)
- **Operator:** `operator.replicas: 1` until there are 3 or more nodes. Envoy runs as the default DaemonSet.
- **Monitoring:** ServiceMonitors are enabled for agent, operator, envoy, and Hubble (ADR-0018).
- **Priority:** Cilium uses the built-in `system-node-critical`.

## Consequences

- One component replaces flannel, kube-proxy, MetalLB, and an ingress controller.
- Hubble gives live traffic flows: the "satisfying to watch" goal.
- Athena's egress lock-down can use FQDN rules (ADR-0024).
- A Cilium upgrade is a platform-critical change and is never auto-merged (ADR-0023).

## Alternatives considered

- **flannel + MetalLB + Traefik:** three components, no FQDN policy, no flow view. Rejected.
- **Envoy Gateway:** more Gateway features, but one more controller. Deferred until Cilium's gateway is actually limiting (ADR-0026).

## Compliance

- The `render` check covers values. The bootstrap reads the same `values.yaml` (ADR-0015).
- `cilium status` / `hubble observe` are part of the post-bootstrap verification in `runbooks/02-bootstrap.md`.
