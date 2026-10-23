# Runbook 05 · Upgrades

Renovate proposes, tuppr executes (ADR-0023). Everything is a PR; nothing is upgraded by hand.

## Charts, images, tools and actions (Renovate)

Renovate opens PRs on Saturday mornings, only for releases at least 3 days old. Security fixes skip the wait.

- **Merges itself** once `validate` passes: image digest and patch bumps outside the platform-critical set, GitHub Actions, and mise tool patches.
- **Waits for you:**
  - everything in the platform-critical set: Talos, Kubernetes, Cilium, Flux, Gateway API, tailscale, cloudflared, k8up, tuppr
  - every minor or major update. Majors carry the `breaking` label.
- **The Dependency Dashboard issue** lists every pending and rate-limited update. Tick a box there to have Renovate open that PR now.

For a waiting PR, ask Athena to review it. The `upgrade` skill reads the changelog and diffs the values. Then merge it, or close it to skip that version.

Two kinds of PR need one extra commit before they can pass (ADR-0038):
- **Claude Code or mise in Athena's image:** Renovate bumps the version but can't compute the download checksum beside it, so the `athena-image` build fails until the `--checksum` is updated. Ask Athena to do it. Its `upgrade` skill knows where each checksum is published.
- **A mise tool whose `mise-lock` check fails:** run `mise lock --platform linux-x64,macos-arm64,macos-x64` and push `.config/mise.lock` to the PR.

**How Renovate works here:**
- Config: `.github/renovate.json5`. Renovate runs as the Mend-hosted GitHub app (installed on `olympus` only).
- Auto-merge uses GitHub's own auto-merge. Renovate may skip the review (ruleset `main-approval`), but never the PR or `validate`.

## Talos and Kubernetes (tuppr)

A Talos or Kubernetes PR changes four places at once. Renovate's `talos` and `kubernetes` groups keep them together, and `versions-match` and `talos` fail otherwise:

| Upgrade | Files |
|---|---|
| Talos | `01-talos/cluster.yaml` `talosVersion`, `upgrades/talos.yaml` `spec.talos.version`, the `talosctl` image in both upgrade CRs, and the talosctl pin in `.config/mise.toml` |
| Kubernetes | `01-talos/cluster.yaml` `kubernetesVersion`, `upgrades/kubernetes.yaml` `spec.kubernetes.version` |

**Order:** Talos first, then Kubernetes, in separate PRs. Kubernetes moves one minor at a time (ADR-0008).

**After merge,** tuppr does this one node at a time:
1. checks that every node is Ready and every Flux Kustomization is Ready
2. drains the node
3. upgrades it, keeping the node's own Image Factory schematic
4. reboots it and waits for it to be Ready again

Watch it from any tailnet device:

```bash
kubectl get talosupgrade,kubernetesupgrade -n tuppr
```

```bash
kubectl get nodes -o wide
```

On a single node, zeus, expect the cluster to be unreachable for a few minutes while it reboots. Remote Control sessions with Athena reconnect by themselves afterwards.

## When an upgrade fails

`TalosUpgradeFailed` or `KubernetesUpgradeFailed` arrives on your phone (critical). tuppr stops and touches no further node.

1. `kubectl -n tuppr describe talosupgrade talos` (or `kubernetesupgrade kubernetes`) gives the phase and the reason.
2. `kubectl -n tuppr logs job/<name>` shows the upgrade Job's talosctl output.
3. **If a health gate blocks it** (a Kustomization not Ready, say), fix that first. tuppr retries by itself.
4. **If a node won't come back:** Talos keeps the previous version on its other partition. Roll back with the admin `talosconfig` (break-glass):

   ```bash
   talosctl -n zeus rollback
   ```

   Then open a PR that reverts the version bump, so git matches the cluster again.

Kubernetes can't be downgraded. That's why there's the 3-day release age and the `.2`-patch rule.
