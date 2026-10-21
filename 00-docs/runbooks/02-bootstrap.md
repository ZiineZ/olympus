# Runbook 02 · Bootstrap

Takes a cluster whose node is `NotReady` (Talos is up, but there's no CNI yet) to a cluster where Flux runs everything from git (ADR-0015, ADR-0029). It runs **once per cluster build**, from Stan's Mac. After this, every change is a PR.

## Before you start

- `KUBECONFIG` points at the new cluster's admin kubeconfig. Never commit it.
- The age key is at `$SOPS_AGE_KEY_FILE`, which mise sets.
- `kubectl get nodes` shows the node(s) `NotReady`. That is expected.

## Run

```bash
mise run bootstrap:apps
```

It does five things, each safe to re-run:

1. Creates namespace `flux-system`, and the Secret `sops-age` from your age key. Flux uses that Secret to decrypt `*.sops.yaml`.
2. Applies `03-cluster/priority-classes.yaml`, because Cilium's Hubble pods use the `platform` class. Flux adopts the classes later.
3. Applies the Gateway API CRDs from `04-platform/01-network/gateway-api-crds/app`, the same file Flux uses.
4. Runs `helmfile sync`, in order: **Cilium** (the node turns Ready), **flux-operator**, **flux-instance**. Chart versions come from each `ocirepository.yaml`, and values from each `helmrelease.yaml`.
5. Flux starts and syncs `03-cluster` from git.

## Verify

| Check | Command | Expected |
|---|---|---|
| Node | `kubectl get nodes` | `Ready` |
| Flux has taken over | `flux get all -A --status-selector ready=false` | empty |
| Releases adopted, not reinstalled | `flux get helmreleases -A` | `cilium`, `flux-operator`, `flux-instance` Ready at release **v2 or later** |
| Cilium | `cilium status --wait` | everything `OK`, Hubble Relay `OK` |
| Datapath | `kubectl -n kube-system exec ds/cilium -c cilium-agent -- cilium-dbg status --verbose \| grep -E 'KubeProxyReplacement\|Device Mode\|BandwidthManager'` | kube-proxy replacement `True`, device mode `netkit` (or `veth` on old kernels), BandwidthManager `EDT with BPF` on bare metal |
| LB pool | `kubectl get ciliumloadbalancerippools` | `lan`, no conflict |

## If something fails

- **helmfile times out on Cilium:** check `kubectl -n kube-system get pods`. A Pending pod usually means a missing PriorityClass or CRD, so check that steps 2–3 ran.
- **A HelmRelease shows `install` instead of `upgrade`:** its name or namespace differs between the helmfile and the HelmRelease. They must match exactly, or Flux installs a second copy.
- **Flux objects stuck `not ready`:** run `flux events -A`, then follow the `debug` skill (layer 1).
