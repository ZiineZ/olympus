# Conventions

These are the operative rules of Olympus. Each rule links to the ADR that decided it and explains why. This file is **living**: it always reflects every Accepted ADR. It never states versions (those live in manifests; see `inventory.md`). `.claude/CLAUDE.md` imports this file, so these rules bind Athena too.

## Principles ([ADR-0001](decisions/0001-guiding-principles.md))

- Git is the only source of truth, every fact lives once, and every change is a PR.
- Every UI is read-only.
- One writer per kind of change. Structural limits beat instructions.
- Boring by default; upstream conventions first.
- The cluster is cattle and the data is a pet.
- Make the smallest diff, one concern per PR, and always explain why.
- Minimal by default: deferred items go to the [register](decisions/0026-deferred-decisions-register.md).
- Prefer performance over silence, and deterministic failure over a slow crawl.

## Naming ([ADR-0002](decisions/0002-naming-greek-pantheon.md))

- **Identities are Greek gods:** cluster `olympus`, nodes in `01-talos/cluster.yaml`, agent `athena`. Never use `hermes` or `prometheus`.
- **Everything else is functional:** namespace = folder = upstream name, written in lowercase kebab-case.
- Secrets are named `<component>-<purpose>`, in files `<name>.sops.yaml`.
- **Custom keys always use the `olympus/` prefix.** These are the only allowed ones:

  | Key | Kind | On | Values |
  |---|---|---|---|
  | `olympus/tier` | label | nodes | `heavy`, `light` |
  | `olympus/gateway-access` | label | namespaces | `public` |
  | `olympus/policy` | label | namespaces | `exempt` (only `kube-system`, `flux-system`) |
  | `olympus/description`, `olympus/docs`, `olympus/adr` | annotation | `ks.yaml` Kustomizations | text, paths, ADR numbers |
  | `olympus/backup` | annotation | namespaces | `none` plus a reason |

## Layout ([ADR-0003](decisions/0003-repository-layout.md))

- **Root:** only `00-docs` through `05-apps`, plus `.claude/ .github/ .config/ .sops.yaml .gitignore`.
- **Layers and groups:** a layer depends only on lower numbers. Groups are a closed set; a new group is appended with the next number and nothing is ever renumbered.
- **Component shape:** `<component>/ks.yaml` plus `app/{kustomization, namespace, ocirepository, helmrelease, values, *.sops}.yaml`. The only extra folder allowed is `image/`, and only for components that build their own image.
- **Namespace = folder name.** The exceptions are `cilium` and `metrics-server` (in `kube-system`) and `flux-operator` and `flux-instance` (in `flux-system`).
- **Cohesion:** everything about X lives in X's folder.
- Every manifest starts with a `# yaml-language-server: $schema=…` line.

## Keeping things in sync ([ADR-0004](decisions/0004-single-source-of-truth-and-change-enforcement.md))

- **Single homes:**

  | Fact | Lives in |
  |---|---|
  | Versions | manifests |
  | Talos and Kubernetes versions | `01-talos/cluster.yaml` and the tuppr CRs (must match) |
  | Shared values | `03-cluster/cluster-settings.yaml` |
  | Nodes and IPs | `01-talos/cluster.yaml` |
  | Helm values | `app/values.yaml` |
  | Rules | this file |
  | CLI versions | `.config/mise.toml` |

- **`00-docs/inventory.md` is generated** by `mise run docs:gen`. Never edit it by hand.
- **`mise run check` must pass**, and CI runs the same thing.
- Co-change rules live in `.github/sync-rules.yaml` and in each component's `olympus/docs` annotation.
- **The only bypass** is a line in the PR body: `No doc change: <path> — <reason>`.
- **Living docs never contain version strings.** Living docs are this file, `architecture.md`, and `runbooks/`.
- Changing `.github/checks/**`, `.github/sync-rules.yaml`, or the `change` skill requires updating this file in the same PR.

## Git ([ADR-0005](decisions/0005-git-and-pull-request-workflow.md))

- **Branches:** `<stan|athena>/<type>/<slug>`.
- **Commits:** Conventional Commits, `type(scope): summary`. Scope is a component name or `talos|bootstrap|cluster|adr|checks`.
- **Merging:** squash only. The PR title is the commit message.
- **Reviews:** Athena's PRs need Stan's approval as CODEOWNER. Stan's own PRs and Renovate's allow-listed auto-merges bypass approval, but **never** bypass the PR requirement or the `validate` check.
- **Repo settings and rulesets are code** in `.github/settings/`. Apply them with `mise run github:apply` and check them with `mise run github:diff`. Never click-change them in the GitHub UI.
- **Actions** must be pinned to a full commit SHA, and only allow-listed actions may run.
- **The repo is public** ([ADR-0027](decisions/0027-public-repository.md)). Commits, PRs, and issues must never contain plaintext secrets, credentials, or unfixed security weaknesses. Push protection is on.
- **PR body:** Why, What changed, Impact checklist, `No doc change:` lines, How verified, Learn more.

## Tooling ([ADR-0006](decisions/0006-tooling-mise.md))

- `mise install` provides the whole toolchain.
- **mise tasks are the only imperative entrypoints.** `mise tasks` lists the ones that exist today. They are defined only in `.config/mise.toml`, and each task is added in the phase that first needs it (target set: ADR-0006).
- **A tool joins `.config/mise.toml` in the phase that first needs it.** `.config/mise.lock` pins checksums for linux-x64, macos-arm64, and macos-x64. Regenerate it with `mise lock --platform linux-x64,macos-arm64,macos-x64` whenever a version changes.
- **CI installs only `python` and `yq`.**
- Check scripts use the Python standard library only.

## Nodes ([ADR-0007](decisions/0007-operating-system-talos-linux.md), [ADR-0008](decisions/0008-cluster-topology-and-versions.md), [ADR-0009](decisions/0009-network-addressing-and-hardware.md))

- **Talos only.** Configuration is applied only through mise tasks. There is no SSH and no hand-made patches.
- **Talos config is rendered by `talosctl` alone** ([ADR-0028](decisions/0028-talos-config-with-talosctl.md)). `01-talos/cluster.yaml` holds versions and nodes. Patches apply by folder: `patches/global` to every node, `patches/<role>` to that role. Each image is defined in `schematics/<name>.yaml`.
- **Patches use only Talos 1.14 config documents**, never the deprecated `v1alpha1` fields. Cluster-scoped documents belong in `patches/controlplane/`.
- **Talos patches append to lists; they don't replace them.** Never restate a list entry Talos already sets by default: a duplicate can stop a component from starting. Remove an entry with `$patch: delete`.
- **Image schematics:** `zeus`, `amd`, `intel`. Every node has wired Ethernet.
- **No swap.** Kubelet reservations and eviction thresholds are set in `patches/`.
- **The API endpoint is always the VIP** (`${CLUSTER_API_VIP}`), never a node IP.
- **LAN:** `192.168.50.0/24`. Node IPs are static and set in `01-talos/cluster.yaml`. Router DHCP serves `.100`–`.199`, and the LoadBalancer pool is `.200`–`.229`.
- A new node must pass the live-boot hardware check (`runbooks/08-add-node.md`) before it joins.
- **Kubernetes version:** the newest minor that Talos supports and that has reached `.2`. Never skip a minor.

## Traffic ([ADR-0010](decisions/0010-cni-cilium.md), [ADR-0011](decisions/0011-traffic-exposure.md), [ADR-0012](decisions/0012-remote-access-tailscale.md))

- **Public traffic** flows: Cloudflare, then the `cloudflared` tunnel, then Gateway `public`, then an `HTTPRoute`. The namespace must be labelled `olympus/gateway-access: public`.
- **Admin UIs** are reachable only on the tailnet, through an `Ingress` with `ingressClassName: tailscale`. That is the only allowed use of `Ingress`.
- **Never used:** NodePort, `hostNetwork` for apps, port forwarding, or LAN-only hostnames.
- **Humans are read-only by default.** The `olympus:viewers` group sees everything except Secrets. Write access goes through `runbooks/break-glass.md`.
- **The tailnet policy is code:** `04-platform/01-network/tailscale/tailnet-policy.hujson`.
- **The one out-of-git exception:** Cloudflare Access apps and policies, which are documented in `runbooks/03-core.md`.

## GitOps and secrets ([ADR-0013](decisions/0013-gitops-flux.md), [ADR-0014](decisions/0014-secrets-sops-age.md), [ADR-0015](decisions/0015-bootstrap-sequence.md))

- **Flux defaults** are set once, in the FluxInstance patches:
  - Kustomizations reconcile every 10m, with `prune` and `wait`.
  - HelmReleases reconcile every 30m, with `driftDetection: enabled`.
- **Charts** come from `OCIRepository`, pinned and verified with cosign wherever the publisher signs them. There is no image automation.
- **Secrets:** every `Secret` lives in a `*.sops.yaml` file next to the component that uses it. Secret Helm values are passed through `valuesFrom`.
- **The age key** is kept in Stan's password manager and on paper. It never goes in the cluster, CI, or Athena. Its public key is the single recipient in `.sops.yaml`. Anyone can **encrypt** with it, Athena included; only Stan can **decrypt**.
- **Bootstrap** reads versions and values from the same files Flux uses. It runs once per cluster build.

## Data ([ADR-0016](decisions/0016-storage-local-path.md), [ADR-0017](decisions/0017-backups-k8up.md))

- **Storage:** StorageClass `local-path` only, set explicitly on every PVC. It is backed by zeus only, with `Retain`.
- **Placement:** stateful workloads use `nodeSelector: {olympus/tier: heavy}`.
- **Backups:** every namespace with PVCs includes `03-cluster/components/backup` (k8up, daily), or is annotated `olympus/backup: none` with a reason.
- **Restores** are a PR that adds a `Restore` CR. A follow-up PR removes it.

## Observability ([ADR-0018](decisions/0018-observability-victoriametrics.md), [ADR-0019](decisions/0019-alerting-ntfy.md), [ADR-0020](decisions/0020-dashboard-kite.md))

- **Metrics:** the VictoriaMetrics stack. Alert rules and dashboards live in the folder of the component they watch.
- **Grafana dashboards** come from git only, with `editable: false`.
- **Alerts** go to ntfy and are outbound only. `Watchdog` pings healthchecks.io, which acts as the dead man's switch.
- **Kite** runs in config-file mode with a read-only ServiceAccount.

## Admission and workloads ([ADR-0021](decisions/0021-admission-policy.md), [ADR-0022](decisions/0022-workload-standards.md))

- **Resources:** every container sets a CPU request, a memory request, and a memory limit, with **memory limit = request** and **no CPU limit**.
- **PriorityClasses:**
  - `platform-critical`: Flux, cloudflared, tailscale
  - `platform`: other platform components
  - `apps`: the default
  - `agent`: Athena
- **Security:** Pod Security `restricted` by default, plus `hostUsers: false` for our own apps.
- **Pod Security exceptions:**

  | Namespace | Level | Why |
  |---|---|---|
  | `kube-system` | privileged | Cilium |
  | `victoria-metrics` | privileged | node-exporter |
  | `tailscale` | privileged | proxies need NET_ADMIN |
  | `local-path-provisioner` | privileged | hostPath helpers |
  | `k8up` | baseline | backup pods read files as root |

- **Images** are written `repo:tag@sha256:…`. Never `latest`.
- **Labels:** `app.kubernetes.io/name` is required on every pod.
- **Replicas and PDBs:** one replica by default, and no PodDisruptionBudgets while any workload runs a single replica.
- **Network:** every namespace includes `03-cluster/components/default-deny` (ingress). Egress is open, except for `athena`.
- **Our own apps** use the bjw-s `app-template` chart. Third-party software uses its upstream chart when maintained, otherwise `app-template`.
- **New Deny policies** run in Warn/Audit mode for one week before switching to Deny.

## Upgrades ([ADR-0023](decisions/0023-upgrades-renovate-tuppr.md))

- **Renovate** runs Saturdays before 06:00 (Europe/Amsterdam), with a minimum release age of 3 days. Related versions are grouped into one PR.
- **Never auto-merged:** Talos, Kubernetes, Cilium, Flux, Gateway API, tailscale, cloudflared, k8up, tuppr.
- **tuppr** performs Talos and Kubernetes upgrades from its CRs, one node at a time, with health gates. Talos is upgraded before Kubernetes.
- **Rollback:** `git revert` (Talos A/B rollback is break-glass only).

## Athena ([ADR-0024](decisions/0024-agent-athena.md))

- **Read access:** `view` plus `olympus-cluster-read`. No Secrets, no exec, no write access, no Talos access, no age key.
- **Write access:** git PRs only, through the GitHub App, with no `workflows` permission. Athena cannot merge.
- **Egress:** only the Anthropic API, GitHub, the kube-apiserver, VMSingle, and Hubble Relay.
- **Memory:** a 2Gi limit, with PriorityClass `agent`.
- Every change goes through the `change` skill. The `olympus` skill is the entrypoint.

## Recovery ([ADR-0025](decisions/0025-disaster-recovery-and-rehearsal.md))

- **Must survive outside the cluster:** the repo, the age key, the restic password, and the external accounts.
- **Restore drill:** quarterly. **Full rehearsal rebuild:** yearly.
- **Rehearsal** happens on Stan's MacBook only, after his explicit "go", on a throwaway branch `rehearsal/<date>` that changes exactly three files.
