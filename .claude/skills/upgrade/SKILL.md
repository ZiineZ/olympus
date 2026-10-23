---
name: upgrade
description: Review Renovate PRs and plan or perform version upgrades in the Olympus repo (Helm charts, images, Talos, Kubernetes, Cilium, Flux, Gateway API, mise tools, GitHub Actions). Use when a Renovate PR appears, when Stan asks to upgrade something, or when planning Talos or Kubernetes version moves. It covers changelog review, values diffs, CRD and breaking changes, version policy, grouping and rollback. It is always used together with the change skill when files must change.
---

# Upgrades

Policy sources: **ADR-0023** (Renovate and tuppr) and **ADR-0008** (the Kubernetes version policy). Re-read both if anything below seems to conflict with them.

## 1. Classify the bump

| Kind | Examples | Who merges |
|---|---|---|
| Auto-merge eligible | image digest/patch outside the platform-critical set, GitHub Actions minor/patch/digest, mise patch | Renovate, after CI passes. You only review it if CI fails. |
| Reviewed | everything else | Stan, after your review comment |
| **Platform-critical** | Talos, Kubernetes, Cilium, Flux (operator + distribution), Gateway API, tailscale, cloudflared, k8up, tuppr | Stan, **never** auto-merged; the PR needs a full review from you |

## 2. Review procedure (for every reviewed or platform-critical PR)

1. **Read every release note between the current and target versions, including the intermediate ones.** Note:
   - breaking changes and removed or renamed values
   - changed defaults
   - CRD changes, and whether the CRD API version changes
   - deprecated or removed Kubernetes APIs
   - minimum Kubernetes version
   - security fixes
2. **Diff the chart values** between the two versions:
   ```bash
   helm show values oci://<registry>/<chart> --version <old> > /tmp/old.yaml
   helm show values oci://<registry>/<chart> --version <new> > /tmp/new.yaml
   diff -u /tmp/old.yaml /tmp/new.yaml
   ```
   Then check every key that our `spec.values` (in `helmrelease.yaml`) sets against the diff.
3. **Check the rendered diff** (flate output on the PR). Any changed object besides the version labels needs an explanation.
4. **Check compatibility:**
   - The Talos support matrix covers the target Kubernetes version.
   - Cilium supports the Kubernetes version and the Gateway API CRD version.
   - The chart's `kubeVersion` constraint is satisfied.
5. **Check grouping.** Related versions must be in the same PR:
   - `01-talos/cluster.yaml` + the tuppr CR
   - Cilium + Gateway API CRDs
   - flux-operator + `FluxInstance.distribution.version`

   If Renovate split them, comment and ask for a regroup by fixing `.github/renovate.json5` (via `change`).
6. **Make any required value changes in the same PR** (via `change`). A version bump that needs a config change is one concern. Two bumps always need a follow-up commit (ADR-0038):
   - **Athena's Dockerfile** (`CLAUDE_CODE_VERSION`, `MISE_VERSION`): put the new release's sha256 in the matching `--checksum`. Claude Code's checksum is in `https://downloads.claude.ai/claude-code-releases/<version>/manifest.json` (`platforms.linux-x64.checksum`); mise's is in the release's `SHASUMS256.txt`. Then pin the HelmRelease to the image the PR builds.
   - **A mise tool** whose `mise-lock` check fails: run `mise lock --platform linux-x64,macos-arm64,macos-x64` and commit `.config/mise.lock`.
7. **Post a review comment:**
   - **Risk:** low, medium, or high, and why
   - **What changes for Stan**, in plain words
   - **Required actions outside git**, if any
   - **Rollback plan**
   - **Recommendation:** merge, wait, or needs changes

## 3. Version policy

- **Kubernetes:** run the newest minor that the pinned Talos supports *and* that has a `.2` or later patch. Never skip a minor. One minor per PR. Talos goes first if both are pending.
- **Minimum release age:** 3 days (Renovate enforces it). Don't shortcut it, except for security advisories.
- **Majors** get the `breaking` label. Upgrade them alone, never in a batch.
- **Order** across platform upgrades in the same week: Talos → Kubernetes → Cilium → Flux → everything else. Wait for the cluster to be green between each.

## 4. Talos and Kubernetes upgrades (tuppr)

- **Minors and majors** sit in the Dependency Dashboard's *Pending Approval* until Stan ticks them (`.github/renovate.json5`). When asked, check the ADR-0008 bar: the minor has a `.2` or later patch, and the Talos support matrix for the pinned Talos lists it. Then tell Stan whether to tick it.

- The PR changes **both** `01-talos/cluster.yaml` (`talosVersion`/`kubernetesVersion`) and the tuppr CR in `04-platform/05-operations/tuppr/app/upgrades/`. `versions-match` fails otherwise. A Talos bump also moves the `talosctl` image in both CRs and the talosctl pin in `.config/mise.toml` (`talos` check). See `runbooks/05-upgrades.md`.
- **After merge:** tuppr upgrades one node at a time, gated on all nodes Ready + Flux Ready. Watch, read-only:
  ```bash
  kubectl get talosupgrade,kubernetesupgrade -A
  kubectl get nodes -o wide
  ```
- If a node is stuck, give Stan the break-glass steps (`talosctl -n <node> dmesg`, `services`, and `rollback` if needed) from `runbooks/break-glass.md`. You can't run talosctl yourself.

## 5. Rollback

- **Charts and images:** a PR that runs `git revert <merge-sha>`. HelmRelease remediation already rolls back failed upgrades automatically. Check `flux get hr -A` before proposing a revert.
- **Talos:** A/B rollback is a break-glass step for Stan.
- **Kubernetes:** no downgrades. If a Kubernetes upgrade is in doubt, the answer is "don't merge yet".
