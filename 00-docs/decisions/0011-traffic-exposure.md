# ADR-0011: Traffic exposure: public via Cloudflare, admin via the tailnet, no LAN hostnames

- **Status:** Accepted
- **Date:** 2026-10-20
- **Deciders:** Stan (owner), Claude (proposer)
- **Related:** ADR-0009, ADR-0010, ADR-0012, ADR-0026

## Context

The cluster sits behind double NAT in a dorm, with no port forwarding allowed. Stan already publishes sites through Cloudflare Tunnels protected by Cloudflare Access. Today `lab` runs about 13 separate `cloudflared` containers. Admin UIs must never be public.

## Decision

There are exactly two exposure tiers. Each Service uses one of them, or neither.

### Tier 1: public (`*.stantheunissen.nl`)

**Path:** Cloudflare edge (TLS, Access) → one `cloudflared` Deployment in namespace `cloudflared` → the Gateway `public` → `HTTPRoute` → Service.

- **Tunnel `olympus`** is a *locally-managed* tunnel. Its credentials JSON lives in `cloudflared-tunnel.sops.yaml`, and its ingress config lives in git:
  - `*.${PUBLIC_DOMAIN}` → `http://cilium-gateway-public.gateway.svc.cluster.local:80`
  - a catch-all `http_status:404`

  A remotely-managed (dashboard-configured) tunnel is forbidden.
- `cloudflared` runs with `replicas: 2` once there are 2 or more nodes (1 until then). It uses `--protocol quic` and the `metrics` port, and its PriorityClass is `platform-critical`.
- **Gateway `public`** (namespace `gateway`, `gatewayClassName: cilium`):
  - one HTTP listener on port 80. TLS terminates at Cloudflare, and the in-cluster hop is plain HTTP inside the cluster network.
  - `allowedRoutes.namespaces.from: Selector`, matching namespaces labelled `olympus/gateway-access: public`. An app must opt in explicitly.
  - It gets an IP from the Cilium pool. Nothing on the LAN depends on that IP.
- **external-dns** (namespace `external-dns`) creates DNS records from routes:
  - `provider: cloudflare`, `sources: [gateway-httproute]`, `domainFilters: [${PUBLIC_DOMAIN}]`
  - `registry: txt` with `txtOwnerId: olympus`, `policy: sync`. It only ever deletes records it owns, so existing records for services still on the old `lab` setup are safe.
  - Records are proxied CNAMEs to `<tunnel-id>.cfargotunnel.com`, set by the target annotation on the Gateway.
  - The API token is limited to Zone:DNS:Edit for this one zone, stored in SOPS.
- **Cloudflare Access applications and policies** are configured in the Cloudflare dashboard for now. This is a known out-of-git exception, documented in `runbooks/03-core.md`. Managing them as code (OpenTofu) is deferred (ADR-0026).

### Tier 2: tailnet (`<component>.<tailnet>.ts.net`)

- Admin UIs are exposed through the Tailscale operator with `Ingress` (`ingressClassName: tailscale`). Each gets an automatic HTTPS certificate.
- The initial set: `kite`, `grafana`, `hubble`, `flux`, `alertmanager`, `vmui`.
- **This is the only allowed use of the `Ingress` API.** Everything else uses Gateway API.
- `kubectl` reaches the API server through the operator's API server proxy (ADR-0012).

### Not offered

- **No LAN-only hostnames, no internal DNS, no cert-manager.** This is deferred until the first LAN-only service exists (ADR-0026).
- **No NodePorts.**
- **No `hostNetwork`** for apps.

## Consequences

- Admin surfaces are reachable only by tailnet identity. Public surfaces are reachable only through Cloudflare (Access, WAF).
- About 13 `cloudflared` containers collapse into one Deployment with its config in git.
- Cloudflare Access config is the one remaining out-of-git piece. It is tracked in the register.

## Alternatives considered

- **Port forwarding + cert-manager + a LAN reverse proxy:** impossible in the dorm, and it exposes the home IP. Rejected.
- **Tailscale Funnel for public sites:** loses Cloudflare Access/WAF and the existing domain setup. Rejected.
- **One tunnel per app:** that is today's sprawl. Rejected.

## Compliance

- An admission policy and a CI check reject a `Service` of `type: NodePort`, and reject an `Ingress` whose class isn't `tailscale` (ADR-0021).
- The `render` check validates the HTTPRoutes.
