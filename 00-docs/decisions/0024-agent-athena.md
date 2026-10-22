# ADR-0024: Cluster agent Athena: Claude Code in-cluster, read-only, changes only through PRs

- **Status:** Accepted (rule 19 and the second key superseded by ADR-0033: Kite's AI is off; rules 1, 9, 10 and 14 amended by ADR-0035; access (rule 5) and the Claude credential amended by ADR-0036)
- **Date:** 2026-10-20
- **Deciders:** Stan (owner), Claude (proposer)
- **Related:** ADR-0001, ADR-0004, ADR-0005, ADR-0010, ADR-0012, ADR-0014, ADR-0020, ADR-0022

## Context

Stan wants a Claude assistant that helps run the cluster but structurally cannot make it messy. In July 2026 an unbounded Claude Code session on `lab` reached 15.5 GB RSS and starved the host. Any agent runtime must contain that failure by construction.

## Decision

### Runtime

1. **Claude Code CLI in a pod.** Deployment `athena`, namespace `athena`, `replicas: 1`, `strategy: Recreate`.
   - **Image:** built from `04-platform/06-agent/athena/image/Dockerfile` by `.github/workflows/athena-image.yaml`, pushed to `ghcr.io/<stan>/athena:<git-sha>`, bumped by Renovate. It contains Claude Code (pinned), and the mise toolchain from `.config/mise.toml` (kubectl, flux, helm, kustomize, sops *without a key*, cilium, hubble, gh, git, yq, python).
   - **Model:** `claude-opus-5-5`, set via `ANTHROPIC_MODEL`.
   - **Env:**
     - `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1`
     - `DISABLE_AUTOUPDATER=1`, because the version is pinned by the image
2. **Resources:** `requests: {cpu: 500m, memory: 2Gi}`, `limits: {memory: 2Gi}`, no CPU limit, PriorityClass `agent` (ADR-0022). A runaway session is now a clean `OOMKilled` inside its own cgroup, and the info alert reports it (ADR-0019).
3. **Storage:**
   - PVC `athena-home`: 5 Gi, `local-path`, `olympus/tier=heavy`, mounted at `/home/athena`. It holds `~/.claude` (sessions are resumable with `claude --continue`/`--resume`) and the repo clone `~/olympus`. It is backed up by k8up (ADR-0017).
   - `/tmp` is an `emptyDir`. The root filesystem is read-only.
4. **Security context:** `restricted`, `runAsUser: 1000`, `hostUsers: false`.
5. **Access:** `kubectl exec -it -n athena deploy/athena -- claude`, over the tailnet API proxy (ADR-0012). This is the one write-ish permission humans get by default: Role `athena-exec` in namespace `athena` (`pods/exec` create, `pods` get) bound to `olympus:viewers`. No ttyd or code-server. A phone-friendly web terminal is deferred (ADR-0026).

### Read access (structural)

6. **ServiceAccount `athena`** is bound to:
   - the built-in ClusterRole `view`, which excludes Secrets and `pods/exec`, and includes `pods/log` and events
   - ClusterRole `olympus-cluster-read`: get/list/watch on `nodes`, `namespaces`, `persistentvolumes`, `storageclasses`, `priorityclasses`, `customresourcedefinitions`, `apiservices`, `validatingadmissionpolicies`, `validatingadmissionpolicybindings`, `mutatingadmissionpolicies`, `clusterroles`, `clusterrolebindings`, plus **named API groups** (never `*`):
     - `source.toolkit.fluxcd.io`, `kustomize.toolkit.fluxcd.io`, `helm.toolkit.fluxcd.io`, `notification.toolkit.fluxcd.io`, `fluxcd.controlplane.io`
     - `cilium.io`
     - `gateway.networking.k8s.io`
     - `k8up.io`
     - `tuppr.home-operations.com` (*verify group*)
     - `tailscale.com`
     - `operator.victoriametrics.com`
     - `monitoring.coreos.com`
7. **No** Secrets, no exec or attach or port-forward, no write verbs, no `nodes/proxy`, no Talos API access, no age key.
8. **Read-only network reach:**
   - VMSingle `:8428` for PromQL
   - Hubble Relay `:4245` for `hubble observe`
   - the Flux Web UI API is reachable but not needed

### Write access (structural)

9. **Git only, through the GitHub App `athena-<stan>`**, installed on the `olympus` repo only. Permissions:
   - Contents RW, Pull requests RW, Issues RW (audit reports), Checks R, Actions R, Metadata R
   - **No `workflows` permission**: Athena can't change `.github/workflows/`, so it can't weaken CI
   - **No Administration**
10. **Tokens** are minted per use by `image/git-credential-athena`, a git credential helper using the app's private key from `athena-github-app.sops.yaml`. Tokens are valid for 1 hour.
11. **Merging is impossible for Athena:** it isn't a CODEOWNER, it can't approve its own PR, and it isn't a ruleset bypass actor (ADR-0005).
12. **No break-glass role for Athena, ever.** Emergency changes are made by Stan with the admin kubeconfig (`runbooks/break-glass.md`) and back-ported to git by PR immediately. A temporary RoleBinding would be drift and easy to forget.

### Network (CiliumNetworkPolicy `athena-egress`)

13. **Ingress:** deny all. Exec travels through the API server, not the pod network.
14. **Egress allow:**
    - DNS to kube-dns, with the DNS proxy (`rules.dns: [{matchPattern: "*"}]`)
    - `toEntities: [kube-apiserver]`
    - `toFQDNs`: `api.anthropic.com`, `github.com`, `api.github.com`, `codeload.github.com`, `objects.githubusercontent.com`, `raw.githubusercontent.com`
    - VMSingle and Hubble Relay (above)

    Everything else is denied.

### Behavior (defense in depth; the structure above is the real limit)

15. **`.claude/CLAUDE.md`** imports `00-docs/conventions.md`, names the `olympus` skill as the entrypoint, and requires the `change` skill for every modification.
16. **`.claude/settings.json`:**
    - `permissions.deny`: `Bash(kubectl apply:*)`, `Bash(kubectl create:*)`, `Bash(kubectl delete:*)`, `Bash(kubectl edit:*)`, `Bash(kubectl patch:*)`, `Bash(kubectl replace:*)`, `Bash(kubectl scale:*)`, `Bash(kubectl rollout:*)`, `Bash(kubectl exec:*)`, `Bash(kubectl port-forward:*)`, `Bash(helm install:*)`, `Bash(helm upgrade:*)`, `Bash(helm uninstall:*)`, `Bash(flux suspend:*)`, `Bash(flux resume:*)`, `Bash(talosctl:*)`, `Bash(git push origin main:*)`, `Bash(git push --force:*)`, `Bash(sops -d:*)`, `Bash(sops --decrypt:*)`
    - A `PreToolUse` hook runs `mise run check` before `git push` and `gh pr create`, and blocks on failure.
17. **Skills:** `.claude/skills/{olympus,change,add-component,upgrade,debug,audit}`.
18. **Long-term memory** is the repo (ADRs, living docs, inventory). Session memory is the PVC. Athena never keeps facts only in its session. Anything worth remembering becomes a docs PR.

### Second surface

19. Kite's built-in AI (ADR-0020) handles quick read-only questions in the UI, with a separate API key. Claude Code on the web can't see the cluster (it is tailnet-only), so it is suitable for repo-only work at most.

## Consequences

- The worst Athena can do is open a bad PR. CI and Stan's review stand between that and `main`.
- Athena can't fix an outage by itself. That is by design: it diagnoses, then proposes.
- Two keys cost money (Athena, Kite AI). Usage is visible per key.

## Alternatives considered

- **Claude Code on Stan's Mac with a read-only kubeconfig:** the admin credentials on the same machine make the limits non-structural. Rejected.
- **The Claude Agent SDK with a custom service:** more code to maintain, and Claude Code already provides sessions, skills, and hooks. Rejected.
- **A temporary emergency role:** drift, easily forgotten. Rejected (point 12).
- **A Kubernetes MCP server in read-only mode:** redundant with kubectl plus RBAC. The Flux MCP server is deferred (ADR-0026).

## Compliance

- `audit` verifies:
  - Athena's bindings: exactly `view` + `olympus-cluster-read` + nothing else
  - its ClusterRole contains no `*` and no Secrets
  - the egress policy exists
  - the GitHub App permissions (via API)
- A sync rule: `06-agent/**` or `.claude/**` → `architecture.md` (ADR-0004).
