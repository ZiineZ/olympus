# Runbook 02 · Bootstrap

Builds the cluster from bare hardware to Flux running everything from git, **once per cluster build**, from Stan's Mac. Part 1 installs Talos on zeus (ADR-0039); part 2 starts the apps (ADR-0015, ADR-0029). After this, every change is a PR.

## Part 1 · Talos on zeus

Before you start, runbook 00 §4 is done: `/srv` backed up, router and cabling set, BIOS set.

### 1. Live boot and record the NIC

1. Download the ISO for zeus's schematic. Open [factory.talos.dev](https://factory.talos.dev), paste `01-talos/schematics/zeus.yaml`, and pick the Talos version in `01-talos/cluster.yaml`. Write it to a USB stick.
2. Boot zeus from the stick. Talos starts in **maintenance mode** and shows its DHCP address on the screen. Nothing is installed yet.
3. From the Mac, inside the repo:

   ```bash
   talosctl get links --insecure --nodes <address-on-screen>
   ```

   ```bash
   talosctl get disks --insecure --nodes <address-on-screen>
   ```

   Note the wired NIC's `HW ADDR`, and check that the NVMe disk is listed with transport `nvme`.
4. Open a PR that sets `mac:` for zeus in `01-talos/cluster.yaml` (lowercase). If the disk isn't NVMe, change `installDisk:` too.

### 2. Install

After that PR is merged, in a fresh pull of `main`:

```bash
mise run talos:secrets
```

Once per cluster: it generates the cluster's Talos secrets straight into `01-talos/secrets.sops.yaml`. Commit that file in its own PR. Losing it means rebuilding the cluster from scratch.

```bash
mise run talos:render zeus
```

It writes `01-talos/clusterconfig/zeus.yaml` and `talosconfig` (git-ignored, mode 600), and validates the config for bare metal.

```bash
mise run talos:apply zeus --insecure <address-on-screen>
```

zeus installs to its NVMe disk, reboots, and comes back at `192.168.50.11`. Remove the USB stick once the reboot starts.

```bash
mise run talos:bootstrap
```

It starts etcd and writes `01-talos/clusterconfig/kubeconfig`. Then:

```bash
export TALOSCONFIG=$PWD/01-talos/clusterconfig/talosconfig KUBECONFIG=$PWD/01-talos/clusterconfig/kubeconfig
```

**Check:**
- `talosctl health` passes, apart from the CNI (that's part 2).
- `kubectl get nodes` shows `zeus NotReady`.
- `ping 192.168.50.10` answers: that's the VIP.

**Later changes** to Talos config are PRs, followed by `mise run talos:render zeus` and `mise run talos:apply zeus` (add `--dry-run` first to see the diff).

## Part 2 · Apps

### Before you start

- `KUBECONFIG` points at the new cluster's admin kubeconfig. Never commit it.
- The age key is at `$SOPS_AGE_KEY_FILE`, which mise sets.
- `kubectl get nodes` shows the node(s) `NotReady`. That is expected.

### Run

```bash
mise run bootstrap:apps
```

It does five things, each safe to re-run:

1. Creates namespace `flux-system`, and the Secret `sops-age` from your age key. Flux uses that Secret to decrypt `*.sops.yaml`.
2. Applies `03-cluster/priority-classes.yaml`, because Cilium's Hubble pods use the `platform` class. Flux adopts the classes later.
3. Applies the Gateway API CRDs from `04-platform/01-network/gateway-api-crds/app`, the same file Flux uses.
4. Runs `helmfile sync`, in order: **Cilium** (the node turns Ready), **flux-operator**, **flux-instance**. Chart versions come from each `ocirepository.yaml`, and values from each `helmrelease.yaml`.
5. Flux starts and syncs `03-cluster` from git.

### Verify

| Check | Command | Expected |
|---|---|---|
| Node | `kubectl get nodes` | `Ready` |
| Flux has taken over | `flux get all -A --status-selector ready=false` | empty |
| Releases adopted, not reinstalled | `flux get helmreleases -A` | `cilium`, `flux-operator`, `flux-instance` Ready at release **v2 or later** |
| Cilium | `cilium status --wait` | everything `OK`, Hubble Relay `OK` |
| Datapath | `kubectl -n kube-system exec ds/cilium -c cilium-agent -- cilium-dbg status --verbose \| grep -E 'KubeProxyReplacement\|Device Mode\|BandwidthManager'` | kube-proxy replacement `True`, device mode `netkit` (or `veth` on old kernels), BandwidthManager `EDT with BPF` on bare metal |
| LB pool | `kubectl get ciliumloadbalancerippools` | `lan`, no conflict |

### If something fails

- **helmfile times out on Cilium:** check `kubectl -n kube-system get pods`. A Pending pod usually means a missing PriorityClass or CRD, so check that steps 2–3 ran.
- **A HelmRelease shows `install` instead of `upgrade`:** its name or namespace differs between the helmfile and the HelmRelease. They must match exactly, or Flux installs a second copy.
- **Flux objects stuck `not ready`:** run `flux events -A`, then follow the `debug` skill (layer 1).
