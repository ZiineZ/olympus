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
