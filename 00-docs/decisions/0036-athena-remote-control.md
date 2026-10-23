# ADR-0036: Talk to Athena through Claude Remote Control

- **Status:** Accepted
- **Date:** 2026-10-22
- **Deciders:** Stan (owner), Claude (proposer)
- **Related:** ADR-0024 (amends rules 1 and 5), ADR-0026 (adopts "Web terminal for Athena (phone)"), ADR-0035

## Context

ADR-0024 made `kubectl exec … -- claude` the only way to talk to Athena. That needs a terminal, kubectl and the tailnet kubeconfig. Stan wants to talk to Athena from the Claude desktop app, as he does with Claude Code on his own machines, and from his phone. The deferred register's trigger for this ("Stan wants to talk to Athena from his phone") has fired.

Claude Code's Remote Control does exactly that, with nothing new to host:
- The `claude` process stays in Athena's pod and makes outbound HTTPS requests to the Anthropic API only.
- The Claude apps and claude.ai/code show its sessions.

It has three requirements (Remote Control docs):
- **A full-scope claude.ai login.** The `claude setup-token` token can only make model requests.
- **`CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC` must not be set.**
- **The workspace must be trusted** before the server can start without a terminal.

## Decision

1. **The pod's main process serves Remote Control:** `claude remote-control --name athena --capacity 4`, from `~/olympus` (`image/bin/athena-init`). It restarts the server if it ever exits. Sessions show up as **athena** in the Claude desktop and mobile apps and at claude.ai/code.
2. **The one-time sign-in is `athena-setup`**, run with `kubectl exec -it -n athena deploy/athena -- athena-setup`.
   - It runs `claude auth login`: Stan opens the printed URL on his own device and pastes the code back.
   - It then runs Remote Control once interactively, so Stan answers its trust and consent prompts.
   - Until that has happened, the pod only waits.
3. **The login lives on the `athena-home` volume** (`~/.claude/`), not in git. Claude Code refreshes it through `platform.claude.com`, which joins `athena-egress`.
   - The `athena-claude` Secret (the setup-token token) is removed. An environment token would take precedence over the login, and Remote Control refuses it.
4. **Telemetry and error reporting stay off** through `DISABLE_TELEMETRY` and `DISABLE_ERROR_REPORTING`. Only `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC` goes, because it also turns Remote Control off.
5. **Nothing else changes.** Athena's limits are structural (RBAC, the GitHub App, the ruleset, `athena-egress`), so a session driven from the app has exactly the same powers as one in a terminal. Tool approvals appear in the app. `kubectl exec … -- claude` keeps working as a fallback.

## Consequences

- Stan talks to Athena from the desktop app, his phone or a browser, with no kubectl and no tailnet needed on that device.
- **The credential is stronger than before.** It's a full sign-in to Stan's claude.ai account, not a model-only token.
  - It's readable by Athena itself, and by anyone who can exec into its pod. That's only `olympus:viewers`, which is Stan.
  - It's also in the volume's daily restic backups on R2, encrypted.
  - Revoke it by signing that device out in claude.ai's account settings.
- The setup-token Secret is gone from git, so there's nothing to rotate yearly. If the login is ever revoked, run `athena-setup` again.
- Remote Control depends on Anthropic's service. The `kubectl exec` path doesn't, so it remains the fallback.

## Alternatives considered

- **ttyd behind a Tailscale Ingress:** a browser terminal, fully self-hosted. But it's another container and another UI that can make changes, it isn't the app Stan already uses, and it's tailnet-only. Rejected.
- **Keep the setup-token token beside the login:** Remote Control refuses to start while an environment token is set. Rejected.
- **Store the login in a SOPS Secret:** Claude Code refreshes and rewrites it, which a read-only Secret can't hold, and git would need a new value after every refresh. Rejected.

## Compliance

- `athena-egress` lists `platform.claude.com`. The `athena-egress` check keeps the chart sources complete (ADR-0035).
- `audit`: claude.ai's account settings list the device Athena signed in as, and nothing unexpected.
