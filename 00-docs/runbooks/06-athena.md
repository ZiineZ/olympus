# Runbook 06 · Athena

Athena is Claude Code in a pod (ADR-0024). It reads the cluster, opens PRs as `athena-ziinez[bot]`, and can't change anything else.

## Talk to it

From any tailnet device with the read-only kubeconfig (`olympus-k8s`):

```bash
kubectl exec -it -n athena deploy/athena -- claude
```

- Pick up where you left off: `claude --continue`, or `claude --resume` to choose a session. Sessions live on the `athena-home` volume, which is backed up daily.
- It works in `~/olympus`, its own clone. Ask it to `git pull` first if `main` moved.
- Its PRs need your approval. It cannot merge, push to `main`, or change workflows.

## Credentials (all in `04-platform/06-agent/athena/app/`)

| Secret | What | Rotate |
|---|---|---|
| `athena-claude` | your Claude subscription token, from `claude setup-token` (valid one year) | before it expires: run `claude setup-token`, then `mise run secret:new 04-platform/06-agent/athena/app/athena-claude.sops.yaml athena athena-claude CLAUDE_CODE_OAUTH_TOKEN` |
| `athena-github-app` | the GitHub App's private key | if it may have leaked: generate a new key on the app's page, delete the old one there, then re-run `secret:new … athena-github-app private-key=@<file>` |

Both are read only when the pod starts. In the same PR, bump `kubectl.kubernetes.io/restartedAt` under `controllers.athena.pod.annotations` in the HelmRelease.

GitHub App installation tokens are minted per use by `athena-token` (valid 1 hour). Nothing long-lived ever reaches GitHub.

## When something's wrong

| Symptom | Likely cause |
|---|---|
| `OOMKilled` in `kubectl -n athena get pods` | a session grew past 2 Gi. That's the limit working; start a fresh session. |
| Claude says it's not logged in, or returns 401 | the subscription token expired or was revoked: rotate `athena-claude` |
| `git push` or `gh` fails with 401/403 | the app's key was removed, or the app is no longer installed on `olympus` |
| it can't reach a site | by design: egress is limited to Anthropic, GitHub, the API server, VMSingle and Hubble Relay (`athena-egress`). Hubble shows the drop. |

## Its image

`ghcr.io/ziinez/athena`, built by `.github/workflows/athena-image.yaml` from `athena/image/`: pinned Claude Code plus the repo's mise toolchain. Every change to the Dockerfile or `.config/mise.*` builds a new image tagged with the commit SHA. A PR bumps the HelmRelease to that tag and digest.
