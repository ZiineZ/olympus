---
name: debug
description: Read-only troubleshooting for the Olympus cluster, for pods crashing or pending, Flux reconcile failures, HelmRelease errors, admission denials, network or Gateway or tunnel problems, DNS, OOMKills, node pressure, alerts firing, or "something is slow or weird". It walks the layers from git and Flux down to the workload, network and node, gathers evidence with read-only commands, finds the root cause and proposes a fix as a PR (via the change skill) or as exact steps for Stan. It never changes the live cluster.
---

# Debug (read-only)

**Rule:** gather evidence, find the root cause, propose a fix. Never "try things" live; you can't anyway. The fix arrives as a PR through `change`, or as numbered steps for Stan if only he can act.

## Layer 0: what changed?

Most breakage is a recent merge.

```bash
git -C ~/olympus log --oneline --since='3 days ago' origin/main
flux get all -A --status-selector ready=false
```

If a merge lines up with the start of the symptom, read that PR's diff first.

## Layer 1: Flux (did git make it to the cluster?)

```bash
flux get kustomizations -A ; flux get helmreleases -A ; flux get sources all -A
flux events --for Kustomization/<name> -n flux-system
kubectl describe helmrelease <name> -n <ns>            # status conditions, last error
flux tree kustomization <name> -n flux-system           # what it owns
flux logs --kind=HelmRelease --name=<name> -n <ns>      # controller logs
```

**Typical causes:**
- render error: the PR should have failed CI, so check `mise run check` locally
- `dependsOn` not ready
- SOPS decryption error: the file isn't encrypted for the cluster key; Stan has to fix it
- admission denied: the VAP message names the rule (ADR-0021)
- chart values schema error
- drift corrected: someone made a change by hand, so find out who and why

## Layer 2: workload

```bash
kubectl get pods -n <ns> -o wide
kubectl describe pod <pod> -n <ns>                      # events at the bottom
kubectl logs <pod> -n <ns> [-c <container>] [--previous]
kubectl get events -n <ns> --sort-by=.lastTimestamp | tail -30
```

| Symptom | Usual cause in Olympus | Fix path |
|---|---|---|
| `Pending`, "didn't match node selector" / PVC unbound | stateful pod not on `olympus/tier: heavy`, or its PVC landed on a worker (local-path is zeus-only by design) | PR: add the nodeSelector |
| `Pending`, "insufficient memory" | the sum of requests exceeds node allocatable | PR: rightsize from metrics, or add a node |
| `OOMKilled` | memory limit (= request) too low | PR: raise it to p99 × 1.2 from VictoriaMetrics data |
| `ImagePullBackOff` | wrong tag or digest, registry rate limit | PR: fix the ref, after checking the registry |
| `CrashLoopBackOff` | app config or missing secret; check `--previous` logs | PR, or ask Stan for the secret |
| `CreateContainerConfigError` | a referenced ConfigMap/Secret key is missing. You can see the reference, not the Secret | ask Stan to verify the Secret contents |
| Evicted | node memory pressure; priority ordering worked as designed | find the hog (layer 4) |

## Layer 3: network

`cilium status` needs exec, which you don't have. Use CRs and Hubble instead:

```bash
hubble observe --server <hubble-relay svc> --namespace <ns> --verdict DROPPED --last 200
hubble observe --server <hubble-relay svc> --to-pod <ns>/<pod> --last 100
kubectl get ciliumendpoints -n <ns> ; kubectl get ciliumnodes
kubectl get networkpolicy,ciliumnetworkpolicy -n <ns> -o yaml
```

- **Drops to a pod:** it is missing an allow in its namespace's network policies. Default-deny ingress is on everywhere (ADR-0022).
- **Public site down:** walk the path in order:
  1. `kubectl logs -n cloudflared deploy/cloudflared`: tunnel connected?
  2. `kubectl get gateway public -n gateway -o yaml`: `Programmed`?
  3. `kubectl get httproute -A`: `Accepted` + `ResolvedRefs`?
  4. Namespace label `olympus/gateway-access: public`?
  5. external-dns logs: was the record created?
  6. Cloudflare Access app: outside git, so ask Stan.
- **Tailnet UI down:** check the tailscale operator logs, the proxy StatefulSet in `tailscale`, and the Ingress status.
- **DNS:** CoreDNS pods in kube-system, and `hubble observe --protocol dns --namespace <ns>`.

## Layer 4: nodes and resources

```bash
kubectl describe node <node>      # Conditions: MemoryPressure/DiskPressure/PIDPressure, allocatable, top requests
kubectl top nodes ; kubectl top pods -A --sort-by=memory | head -20
```

PromQL via VMSingle (`curl -s "$VMSINGLE/api/v1/query" --data-urlencode 'query=…'`):

```promql
rate(node_pressure_memory_stalled_seconds_total[5m])      # PSI; sustained "full" > 0.2 = the July-2026 signature
topk(10, container_memory_working_set_bytes{container!=""})
sum by (namespace) (kube_pod_container_resource_requests{resource="memory"})
increase(kube_pod_container_status_restarts_total[1h]) > 0
```

**Talos-level problems** (kubelet, containerd, kernel, disk): you have no Talos access. Give Stan exact commands:

```bash
talosctl -n zeus dmesg | tail -100
talosctl -n zeus logs kubelet
talosctl -n zeus services
talosctl -n zeus get volumestatus
```

## Report format

1. **Symptom:** what is observed, since when.
2. **Evidence:** commands with the relevant output excerpts.
3. **Root cause:** one sentence, plus why. Explain the Kubernetes mechanism for Stan.
4. **Fix:**
   - a PR (link it, via `change`), or
   - Stan's numbered steps (break-glass only if the service is down and git can't fix it fast, followed by a back-port PR)
5. **Prevention:** an alert, a check, or a policy that would have caught it. Offer it as a separate PR.
