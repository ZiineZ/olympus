# Runbook 01 · Rehearsal

Builds a throwaway Olympus on Stan's MacBook (OrbStack) to prove the repo works before zeus is wiped (ADR-0025). **It starts only on Stan's explicit "go".**

## Where it runs

- A separate checkout, `~/olympus-rehearsal` on the Mac. It is **not** Stan's working clone, and it is deleted afterwards.
- All state, `talosconfig` and `kubeconfig` live in `.rehearsal/` inside that checkout, which is git-ignored. Stan's `~/.talos` and `~/.kube` are never touched.
- Ports are bound to `127.0.0.1`, so nothing is reachable from the Wi-Fi network.

## Layer by layer

Each layer is a PR. The rehearsal proves it on the running cluster *before* Stan merges it.

| Layer | Proves | Expected state after it |
|---|---|---|
| Talos | the 1.14 patches boot: kubelet settings, sysctls, Pod Security default, control-plane scheduling | Talos healthy, API answering, node **NotReady** (there is no CNI yet, by design) |
| Bootstrap | Cilium, then Flux taking over from helmfile | node Ready, Flux syncing |
| Core, observability, agent | one PR each | each component Ready under the admission policies |

## Commands (run in `~/olympus-rehearsal`)

```bash
mise run rehearsal:up      # create the cluster (blocks until Talos reports the node; see the note below)
export TALOSCONFIG=$PWD/.rehearsal/talosconfig KUBECONFIG=$PWD/.rehearsal/kubeconfig
talosctl -n 10.5.0.2 health --server=false   # Talos-side health
kubectl get nodes -o wide
mise run rehearsal:down    # destroy everything, including .rehearsal/
```

`talosctl cluster create` waits for the node to become Ready, and that only happens once Cilium is installed. Until the bootstrap layer exists, run it in the background and judge the Talos layer by `talosctl health` and the node's status instead.

## What the rehearsal can't prove

The Docker provisioner has no real hardware, so these are verified on zeus in phase 2 (ADR-0025 rule 8):

- the VIP, and L2 announcements on the real router
- extensions and kernel args (the schematic)
- disks and user volumes
- the tailscale extension
- NIC drivers

Sysctls that a container can't set show up as warnings here. They are expected to work on bare metal.

## Results

Each run appends one line: date, layer, outcome, findings.

| Date | Layer | Outcome | Findings |
|---|---|---|---|
| 2026-10-21 | Talos | ✅ after one fix | The PodSecurity exemption duplicated Talos's default `kube-system` entry (patches append to lists), and kube-apiserver exited. Fixed by dropping our exemption. Then verified: flannel and kube-proxy absent; Pod Security `restricted` rejects a privileged pod; sysctls applied; allocatable = capacity − 2 GiB − 500 Mi and 7/8 CPU; `olympus/tier=heavy`; no control-plane taint; node NotReady as expected without a CNI. |
| 2026-10-21 | Bootstrap | ✅ after one fix | `bootstrap:apps` installed Cilium → flux-operator → flux-instance, and Flux adopted all three (release v2, not reinstalled). Cosign verification of both Flux charts passed. Node Ready; 7/7 Kustomizations Ready. Cilium OK with kube-proxy replacement, **netkit** (via `auto`), native routing, BPF masquerade; the LB pool has no conflicts. **Fix:** Hubble fell back to the `apps` priority because `platform` didn't exist at bootstrap time; the bootstrap now applies `priority-classes.yaml` first. **GitOps loop:** a pushed change rolled out through Flux (Cilium v3). **Drift:** a hand-scaled cilium-operator and a hand-edited `cluster-settings` were both reverted (`DriftCorrected` event). **Full rebuild from nothing: 8 min 14 s** (Talos 126 s, bootstrap 118 s, Flux converged 250 s). Can't be proven here: BandwidthManager is disabled inside a container (no access to `net/core/default_qdisc`), so check it on zeus. |
| 2026-10-21 | Core network (Tailscale, Gateway; cloudflared and external-dns excluded by design) | ✅ after three fixes | **1. Flux web UI config:** the chart wraps `web.config` in `apiVersion`/`kind` itself; our extra wrapper crash-looped flux-operator. **2. SOPS (ADR-0030):** `--sops-age-secret` only supplies the key, so without `decryption: {provider: sops}` the Tailscale Secret was applied still encrypted (`401 API token invalid`); now set for every component in `flux-defaults.yaml`. **3. Network:** the Mac's university network resets connections to `controlplane.tailscale.com`; a different network worked (zeus sits on the dorm network, which reaches it). Then: 10/10 Kustomizations Ready; operator and both proxies Ready at the intended priorities. `hubble-rehearsal` and `flux-rehearsal` served over the tailnet with Let's Encrypt certificates. Through `olympus-k8s-rehearsal` the user is `ZiineZ@github` in `olympus:viewers`: reads work; listing Secrets, deleting a pod, patching a Kustomization and creating a namespace are all **Forbidden**. |
