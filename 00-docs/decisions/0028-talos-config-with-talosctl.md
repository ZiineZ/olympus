# ADR-0028: Render Talos config with plain talosctl (talhelper is archived)

- **Status:** Accepted
- **Date:** 2026-10-21
- **Deciders:** Stan (owner), Claude (proposer)
- **Related:** ADR-0003 (supersedes `talconfig.yaml` in its tree), ADR-0006 (supersedes `talhelper` in its tool list), ADR-0007 (supersedes rule 2's renderer), ADR-0023

## Context

ADR-0007 chose talhelper to render Talos machine config from a `talconfig.yaml`. When the files were written on 2026-10-21, two problems surfaced:

- **talhelper was archived on 2026-08-26.** Its README says "This project is now archived and abandoned". It is pinned to a Talos 1.14 *alpha* machinery library and warns that it may not support Talos v1.14.4. An abandoned tool on the upgrade path would block every future Talos upgrade (ADR-0001 principle 6, ADR-0022's "maintained" bar).
- **talhelper runs environment-variable substitution over patch files.** It turns Talos's own `$patch: delete` directive into an unset `${patch}` variable.

The home-operations community already renders Talos config with plain `talosctl machineconfig patch` and the Image Factory API.

Separately, **Talos 1.14 moved most settings into dedicated config documents**: `KubeletConfig`, `SysctlConfig`, `KubeProxyConfig`, `KubeFlannelCNIConfig`, `KubeAdmissionControlConfig`, `KubeNodeConfig`, `KubePrismConfig`, `ResolverConfig`, and others. The `v1alpha1` field names in ADR-0007 still work, but are deprecated.

## Decision

1. **No config generator beyond `talosctl`** (pinned in `.config/mise.toml`). talhelper is removed.
2. **Layout of `01-talos/`:**

   | Path | Holds |
   |---|---|
   | `cluster.yaml` | The single source of `talosVersion`, `kubernetesVersion`, `endpoint`, and the node list (name, IP, role, schematic, install disk). Read with `yq`. |
   | `patches/global/` | Patches applied to **every** node |
   | `patches/controlplane/`, `patches/worker/` | Patches applied to every node of that role |
   | `schematics/<name>.yaml` | Image Factory schematics: extensions and kernel args. A node names one in `cluster.yaml`. |
   | `secrets.sops.yaml` | Output of `talosctl gen secrets`, fully encrypted (`.sops.yaml` rule 1). Created on Stan's Mac in phase 2. |
   | `clusterconfig/` | Rendered configs, git-ignored |

3. **The folder is the list.** Every `*.yaml` in a patch folder applies, in file-name order. No list of patches exists that could fall out of sync with the files.
4. **Patches use only Talos 1.14 config documents**, never the deprecated `v1alpha1` fields. Cluster-scoped documents (`KubeProxyConfig`, `KubeFlannelCNIConfig`, `KubeAdmissionControlConfig`) live in `patches/controlplane/`: Talos rejects them on workers.
5. **Rendering a node** (the mise task `talos:render`, added in phase 2):
   1. `talosctl gen config` with the decrypted secrets, the Kubernetes version, the Image Factory installer image for the node's schematic, and the global and role patches.
   2. `talosctl machineconfig patch` with a node patch built from that node's `cluster.yaml` entry.
6. **The rehearsal** (`mise run rehearsal:up`) reads the same `cluster.yaml` versions and patch folders.

## Consequences

- One tool fewer, and no dependency on an abandoned project.
- Every Talos field we set is visible in plain Talos documents, so the Talos docs apply one-to-one.
- The node patch built in step 5.2 is a small piece of `yq`. It is covered by the `talos` check and the rendered-config validation in phase 2.

## Alternatives considered

- **Keep talhelper:** archived, and it already lags Talos. Rejected.
- **A fork of talhelper:** we would become its maintainers. Rejected.
- **A templating engine (makejinja, minijinja) like home-ops:** one more tool for what `yq` and patch folders already cover. Rejected for now.
- **Omni:** SaaS dependency (ADR-0007). Rejected.

## Compliance

The `talos` check in `.github/checks/check.py` fails when any of these doesn't hold:

- `talosVersion` equals the `talosctl` pin
- `kubectl` is within one minor of `kubernetesVersion`
- every node's schematic file exists
- roles are `controlplane` or `worker`
- node names are unique
- every patch file is a valid YAML document stream
