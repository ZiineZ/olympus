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

## Mac resources

The full stack requests about 6.6 GiB of memory. OrbStack needs **12 GB** (`orb config set memory_mib 12288`, then `orb stop && orb start`). The rehearsal node gets 10 GiB and 6 CPUs.

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
| 2026-10-21 | Core network (Tailscale, Gateway; cloudflared and external-dns excluded by design) | ✅ after four fixes | **1. Flux web UI config:** the chart wraps `web.config` in `apiVersion`/`kind` itself; our extra wrapper crash-looped flux-operator. **2. SOPS (ADR-0030):** `--sops-age-secret` only supplies the key, so without `decryption: {provider: sops}` the Tailscale Secret was applied still encrypted (`401 API token invalid`); now set for every component in `flux-defaults.yaml`. **3. Network:** the Mac's university network resets connections to `controlplane.tailscale.com`; a different network worked (zeus sits on the dorm network, which reaches it). Then: 10/10 Kustomizations Ready; operator and both proxies Ready at the intended priorities. `hubble-rehearsal` and `flux-rehearsal` served over the tailnet with Let's Encrypt certificates. **4. Flux UI "Limited Access"** (spotted by Stan): Kubernetes can't impersonate a group without a user, so the anonymous identity got username `flux-web-viewer`. The UI then loads fully, and that identity may not patch, suspend or read Secrets. Through `olympus-k8s-rehearsal` the user is `ZiineZ@github` in `olympus:viewers`: reads work; listing Secrets, deleting a pod, patching a Kustomization and creating a namespace are all **Forbidden**. |
| 2026-10-21 | Storage + security | ✅ after four fixes | **1. Volume path:** `/var/mnt` is read-only on Talos until a user volume is mounted, and Docker-Talos has no disk, so `patches/rehearsal/` now adds a `directory` user volume (zeus gets a partition in phase 2). Then: a test app wrote to a `local-path` volume. Deleting the claim left the PV `Released`, with the data **still on the node** (`Retain` works). **2. Policies:** 8 of 9 warned exactly as designed on a deliberately bad bundle, and the compliant app got no warnings. `pvc-explicit-storage-class` could never fire, because the default StorageClass is filled in before validation; it moved to the CI `render` check. **3. Platform scan:** only Tailscale violated (no digests, no `app.kubernetes.io/name`); fixed in values and the ProxyClass. external-dns digest pinned preemptively. **4. ProxyClass changes** reach existing proxies only after an operator restart (noted in the file). Final scan: no platform workload violates a policy. Flux pruned the removed policy by itself. |
| 2026-10-21 | Backups (k8up → R2) | ✅ first try | k8up and `backup-canary` Ready; the SOPS secret decrypted into the canary's namespace (the Flux `targetNamespace` override and the SOPS MAC work together). **One** manual backup: 1,065 bytes to `olympus-backups/rehearsal/backup-canary` (per-namespace path via the component's replacement). The backup pod ran under Pod Security `restricted` as UID 1000, so the `k8up` exception is gone. **One** restore into an empty `restore-drill` claim: the restored `heartbeat.log` equals the original byte for byte (`2026-10-21T12:27:19Z`). R2 use was kept minimal (about 1 KB, a few hundred requests; no check or prune), and the cluster was destroyed right after so its daily schedule never ran. Known noise: k8up's job pods try to push metrics to a non-existent Pushgateway; handled in the observability layer. |
| 2026-10-21 | Observability | ✅ after six fixes | **Found:** (1) Grafana 13 `OOMKilled` at 256 Mi, now 512 Mi. (2) Duplicate `app.kubernetes.io/name` labels on Kite and metrics-server, which Flux's post-render rejected; CI now post-renders every chart through kustomize. (3) Talos scheduler and controller-manager certs are valid only for localhost, so their scrapes skip TLS verification but keep token auth. (4) The operator's Alertmanager Service is headless, so a ClusterIP Service was added for the tailnet UI. (5) Operator-injected config-reloader containers had no resources; set via `configReloaderResources`. (6) The chart's sync job pulled about 40 rule/dashboard files from floating `main`/`master`; all are pinned now, and CI rejects floating refs. **Then:** 20/20 Kustomizations Ready, all pods Running, about 3.4 GiB real memory for the whole platform. Every scrape target up, including etcd over plain HTTP from Talos. 38 rule groups and 44 dashboards loaded from pinned sources. Only `Watchdog` and `InfoInhibitor` firing. Grafana, Kite, Alertmanager and vmui served over the tailnet. Grafana is anonymous read-only (44 dashboards visible, create → 403). Kite's ServiceAccount lists pods but can't read Secrets, delete, patch or exec, and has no Prometheus errors. `Watchdog` → healthchecks.io about every minute; a test alert routed to `ntfy-warning`; 0 failed deliveries. Rehearsal-only noise: `GroupIterationReset` warnings after the Mac slept (clock jump). Remaining gap, accepted for now: chart-internal images are tag-pinned, not digest-pinned (ADR-0033 rule 9). |
| 2026-10-22 | Per-component monitoring | ✅ after one fix | **Found:** k8up's backup pods push restic stats as Prometheus **protobuf**, which VictoriaMetrics's import endpoint rejects. A hand-made text push had passed, so only a real backup showed it. The push is now off (`BACKUP_PROMURL: ""`), and the backup alerts use the operator's job counters (ADR-0034). **Then:** all five `*-monitoring` Kustomizations Ready. Every scrape target up: Cilium agent, Hubble, Cilium operator, flux-operator and k8up. All 8 new rules healthy in VMAlert. 6 Cilium/Hubble dashboards loaded by Grafana's sidecar. A canary backup raised `k8up_jobs_successful_counter` for `backup-canary` from 0 to 1, with no push reaching VictoriaMetrics. `BackupStale` stays quiet for namespaces younger than 26 h. `FluxResourceNotReady` went pending while `tailscale-config` waited on Cilium's restart, then cleared. **Not testable here:** the PSI rules (OrbStack's kernel has no PSI; Talos enables it) and `CloudflaredTunnelDown` (cloudflared runs only on zeus). |
| 2026-10-22 | Athena | ✅ after two fixes | **Found:** (1) `app-template` doesn't mount the ServiceAccount token by default, so kubectl in the pod had no credentials; mounted explicitly. (2) The pre-push check needs the chart registries, and the egress policy blocked them, so every push would have been blocked; the chart sources are now allowed read-only, and the new `athena-egress` check keeps that list complete (ADR-0035). **Then:** UID 1000 in its own user namespace (`hostUsers: false`), all tools present, `mise run check` green in the pod in about a minute. RBAC: reads pods, nodes and Flux objects; refused Secrets (even its own), delete, patch, exec and create. Egress: Anthropic, GitHub, chart sources, VMSingle and Hubble Relay reachable; example.com, google.com and 1.1.1.1 blocked. GitHub: opened a draft PR as `athena-ziinez[bot]` (closed right away); a push touching a workflow was refused (no `workflows` permission); a push to `main` was refused by the ruleset. `claude -p` answered on the subscription token. As `ZiineZ@github` (viewer) over the tailnet proxy, exec into Athena works; exec elsewhere and pod deletion are forbidden. Daily backup Schedule to `rehearsal/athena`. **Rehearsal-only:** the node's 9.25 GiB allocatable can't hold the platform's requests plus Athena's 2 GiB, so Kite and Grafana were paused for the test. When they came back, Athena (lowest priority, never preempts) went Pending as designed. zeus has room for all of it. |
| 2026-10-23 | Athena via Remote Control | ✅ after one fix | **Found:** `athena-setup` signed in fine (claude.ai, Pro) and its trust and consent answers were saved. But the "setup done" marker it wrote at the end was lost when the Mac rebooted mid-setup, so the pod never started serving. The pod now starts once `claude auth status` reports a login, with no marker. **Then:** Stan talked to Athena from the Claude desktop app. After a pod restart on the new image, with no marker present, Remote Control started by itself at capacity 4 and reattached the same `athena` session, so conversations survive restarts. |
