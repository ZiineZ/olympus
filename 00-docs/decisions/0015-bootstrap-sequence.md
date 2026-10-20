# ADR-0015: Bootstrap sequence: Talos, then helmfile hands over to Flux

- **Status:** Accepted
- **Date:** 2026-10-20
- **Deciders:** Stan (owner), Claude (proposer)
- **Related:** ADR-0006, ADR-0007, ADR-0010, ADR-0013, ADR-0014

## Context

There is a chicken-and-egg problem: Flux pods can't start without a CNI, and the CNI is supposed to be managed by Flux. If the bootstrap installs a different version or different values than Flux later wants, the cluster drifts on its first day.

## Decision

The bootstrap runs from Stan's Mac only, as these mise tasks, in this order.

1. **`talos:genconfig`:** talhelper renders `01-talos/clusterconfig/` (git-ignored) from `talconfig.yaml` + patches + `talsecret.sops.yaml`.
2. **Boot zeus** from the `zeus` schematic ISO (Image Factory). It starts in maintenance mode.
3. **`talos:apply node=zeus insecure=true`:** installs Talos to disk. Zeus reboots.
4. **`talos:bootstrap`:** runs `talosctl bootstrap` once (etcd init), waits for the API on the VIP, and writes the admin kubeconfig to the location given in `runbooks/02-bootstrap.md`, which is never inside the repo.
5. **`bootstrap:apps`** does the following, each step idempotent:
   1. Applies `02-bootstrap/resources/` (namespace `flux-system`).
   2. Creates the Secret `sops-age` from the local age key (ADR-0014).
   3. Decrypts the deploy key with SOPS and applies it as Secret `flux-system`.
   4. Applies the Gateway API CRDs with `kubectl apply --server-side -k`, using the upstream ref at the **version read with `yq` from `04-platform/01-network/gateway-api-crds/ks.yaml`**.
   5. Runs `helmfile sync` on `02-bootstrap/helmfile.yaml.gotmpl`. The releases, in order: `cilium` (kube-system), `flux-operator` (flux-system), `flux-instance` (flux-system).
      - **Each release's chart version is read from its `ocirepository.yaml`, and its values from its `app/values.yaml`**, both via helmfile `readFile | fromYaml`.
      - Release names and namespaces equal the HelmRelease names, so helm-controller *adopts* the releases instead of reinstalling them.
6. **Flux takes over.** The FluxInstance syncs `03-cluster`. From then on every change is a PR. The helmfile is never run again on this cluster.
7. **Verification.** `runbooks/02-bootstrap.md` lists the checks:
   - `cilium status --wait`
   - `flux get all -A`: everything Ready
   - `kubectl get nodes`: Ready, with labels set
   - Hubble UI reachable on the tailnet

## Consequences

- There is no version or values drift between bootstrap and Flux, because the files are shared, not copied.
- Bootstrap state stays out of git: the age key and the admin kubeconfig never enter the repo.
- Re-running the bootstrap against a live cluster is harmless but pointless. It is only for new builds (ADR-0025).

## Alternatives considered

- **Talos inline manifests for Cilium:** these duplicate values in machine config, giving two sources. Rejected.
- **`flux bootstrap github`:** commits generated components and needs a write token. Rejected (ADR-0013).

## Compliance

- `render` validates `02-bootstrap/helmfile.yaml.gotmpl` (`helmfile template`).
- The no-copy rule is structural: the helmfile can't hold a version or values literal. A check greps for `version:` or `values:` literals in the helmfile.
