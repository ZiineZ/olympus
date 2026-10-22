# Runbook 06 · Athena

Athena is Claude Code in a pod (ADR-0024). It reads the cluster, opens PRs as `athena-ziinez[bot]`, and can't change anything else.

## Talk to it: the Claude app (Remote Control, ADR-0036)

Open the **Claude desktop app → Code**, the Claude mobile app (**Code**), or [claude.ai/code](https://claude.ai/code), and pick the session **athena**. It shows a computer icon with a green dot while the pod is up.

- **New session:** start a new session on `athena` from the session list. The pod serves up to 4 at once, all working in `~/olympus`.
- **Tool approvals** appear in the app. Approving one can't give Athena more power than its RBAC, GitHub App and network policy allow.
- **Before starting work,** ask it to `git pull` if `main` moved.
- **Its PRs need your approval.** It cannot merge, push to `main`, or change workflows.

### One-time sign-in (and again after a sign-out)

From a tailnet device with the read-only kubeconfig. The first command is needed once per device:

```bash
tailscale configure kubeconfig olympus-k8s
```

```bash
kubectl exec -it -n athena deploy/athena -- athena-setup
```

1. **Sign in.** It runs `claude auth login`: choose the claude.ai account, open the URL it prints on your own device, sign in, and paste the code back.
2. **Accept the prompts.** It then starts Remote Control once: answer `y` to trust `~/olympus` and to enable Remote Control.
3. **Finish.** When the session URL appears, press **Ctrl+C**.

Within about 10 seconds, the pod starts serving Remote Control by itself, and keeps doing so across restarts.

### Fallback: a terminal

```bash
kubectl exec -it -n athena deploy/athena -- claude
```

`claude --continue` picks up your last terminal session, and `claude --resume` lets you choose one.

## Credentials

| What | Where | Renew |
|---|---|---|
| your claude.ai login | `~/.claude/` on the `athena-home` volume (never in git), refreshed by Claude Code itself | if it was revoked or signed out: run `athena-setup` again |
| the GitHub App's private key | `athena-github-app` (SOPS, `04-platform/06-agent/athena/app/`) | if it may have leaked: generate a new key on the app's page, delete the old one there, then re-run `mise run secret:new 04-platform/06-agent/athena/app/athena-github-app.sops.yaml athena athena-github-app private-key=@<file>` |

The GitHub key is read only when the pod starts. In the same PR, bump `kubectl.kubernetes.io/restartedAt` under `controllers.athena.pod.annotations` in the HelmRelease.

**Revoking Athena's claude.ai access:** sign its device out in claude.ai's account settings. GitHub App installation tokens are minted per use by `athena-token` (valid 1 hour); nothing long-lived ever reaches GitHub.

## When something's wrong

| Symptom | Likely cause |
|---|---|
| no **athena** session in the app | the pod isn't Running (`kubectl -n athena get pods`), or the sign-in hasn't been done (`athena-setup`) |
| `kubectl -n athena logs deploy/athena` says it must be logged in, or needs a full-scope login | the login was revoked or expired: run `athena-setup` |
| `OOMKilled` in `kubectl -n athena get pods` | sessions grew past 2 Gi. That's the limit working; the pod restarts and Remote Control comes back by itself. |
| `git push` or `gh` fails with 401/403 | the app's key was removed, or the app is no longer installed on `olympus` |
| it can't reach a site | by design: egress is limited to Anthropic, GitHub, the chart sources, the API server, VMSingle and Hubble Relay (`athena-egress`). Hubble shows the drop. |

## Its image

`ghcr.io/ziinez/athena`, built by `.github/workflows/athena-image.yaml` from `athena/image/`: pinned Claude Code plus the repo's mise toolchain. Every change to the Dockerfile or `.config/mise.*` builds a new image tagged with the commit SHA. A PR bumps the HelmRelease to that tag and digest.
