# ADR-0002: Naming: the Greek pantheon for identities, functional names for everything else

- **Status:** Accepted (the `olympus/policy` label superseded by ADR-0031)
- **Date:** 2026-10-20
- **Deciders:** Stan (owner), Claude (proposer)
- **Related:** ADR-0003, ADR-0008, ADR-0009, ADR-0024

## Context

Stan wants the project to feel personal, so he wants Greek god names. However, names inside Kubernetes (namespaces, releases, services) must stay searchable and must match upstream documentation. Otherwise every tutorial, chart value, and error message needs translating.

## Decision

### Identities get pantheon names

| Thing | Name | Notes |
|---|---|---|
| Cluster | `olympus` | Talos `clusterName`, kube context `admin@olympus`, metrics label `cluster=olympus` |
| Git repository | `olympus` | GitHub, under Stan's account |
| Node: current mini PC (AZW SER, Ryzen 7 6800U, 24 GB) | `zeus` | control plane, `olympus/tier=heavy`, 192.168.50.11 |
| Reserved control-plane names #2, #3 | `hera`, `poseidon` | used only if the HA trigger in ADR-0008 fires (.12, .13) |
| Workers, assigned in join order | `ares`, `artemis`, `apollo`, `hephaestus`, `demeter`, `dionysus` | `olympus/tier=light`, .21 to .26 |
| Cluster agent | `athena` | namespace and ServiceAccount `athena`, GitHub App `athena-<github-user>`, git author `athena[bot]` |

Further rules:

- **Hostnames never encode role or tier.** Labels carry those (`node-role.kubernetes.io/control-plane`, `olympus/tier`). This way a node can change role without being renamed.
- **The pool is Olympians only**, plus Hades, Hestia, and Dionysus.
- **Excluded names:**
  - `hermes`: Stan's existing agent "one" runs on Hermes.
  - `prometheus` and the other Titans: they collide with software, and they aren't Olympians anyway.
  - Any name that collides with software used in this stack.
- **A new node takes the next free name in the list above.** The list is extended only by an ADR.

### Everything inside the platform gets functional names

- Namespaces, folders, HelmRelease names, Services, Gateways, StorageClasses, PriorityClasses, buckets, and UI hostnames all use the upstream or functional name. Examples: `cilium`, `kite`, `victoria-metrics`, `kite.<tailnet>.ts.net`, bucket `olympus-backups`.
- All Kubernetes object names are lowercase kebab-case, at most 63 characters.
- Secrets are named `<component>-<purpose>`, for example `kite-config` or `cloudflared-tunnel`. SOPS files are named `<name>.sops.yaml`.
- **Every custom label and annotation uses the `olympus/` prefix.** Every other label is a Kubernetes recommended `app.kubernetes.io/*` label or an upstream label. Each custom key is defined by exactly one ADR and listed in `conventions.md`. A new key requires an ADR. The complete initial set:

  | Key | Kind | On | Values | Defined by |
  |---|---|---|---|---|
  | `olympus/tier` | label | nodes | `heavy` \| `light` | ADR-0008 |
  | `olympus/gateway-access` | label | namespaces | `public` | ADR-0011 |
  | `olympus/policy` | label | namespaces | `exempt` | ADR-0021 |
  | `olympus/description`, `olympus/docs`, `olympus/adr` | annotation | Flux Kustomizations (`ks.yaml`) | free text, paths, ADR numbers | ADR-0004 |
  | `olympus/backup` | annotation | namespaces | `none` (with reason) | ADR-0017 |

## Consequences

- The fun lives where Stan interacts with identities: `talosctl -n zeus`, `kubectl get nodes`, "Athena opened a PR".
- Documentation and charts stay copy-pasteable, because platform names match upstream.

## Alternatives considered

- **`cp-01`, `wk-01`:** clear but impersonal, and they encode role in the name. Rejected.
- **God names for namespaces too:** breaks upstream docs and is confusing (`apollo` for monitoring?). Rejected.

## Compliance

- The `component-shape` check verifies that namespace equals folder name (ADR-0003).
- `talconfig.yaml` is the only place where node names and IPs are assigned (ADR-0004).
