# ADR-0027: Public repository with GitHub's free security features

- **Status:** Accepted
- **Date:** 2026-10-20
- **Deciders:** Stan (owner), Claude (proposer)
- **Related:** ADR-0005 (supersedes its rule 7), ADR-0014, ADR-0024

## Context

ADR-0005 rule 7 made the repo private under Stan's GitHub Pro, which comes from the Student Developer Pack and expires 2027-06-14. Applying the settings showed two costs of that choice:

- **Secret scanning and push protection are refused on private personal repos** (HTTP 422). They are a paid add-on.
- **Rulesets on a private repo stop being enforced if Pro ever lapses.**

The design already assumed the repo might be public: every secret is SOPS-encrypted (ADR-0014).

## Decision

1. **The repo `ZiineZ/olympus` is public.** This supersedes ADR-0005 rule 7. The rest of ADR-0005 stays in force, and rulesets on public repos need no paid plan.
2. **Free security features, all declared in `.github/settings/settings.json`:**
   - **Secret scanning and push protection on.** A push that contains a recognized credential is blocked.
   - **CodeQL default setup for the `actions` language.** It catches script injection and over-broad permissions in workflows.
   - **Private vulnerability reporting on,** so outsiders report problems privately instead of in a public issue.
   - **Fork pull requests from outside contributors need approval before any workflow runs** (`all_external_contributors`).
   - Unchanged: Dependabot alerts on; Dependabot security-update PRs off, because Renovate is the single version writer.
3. **Discovery:** topics `k8s-at-home` and `kubesearch` are added, so kubesearch.dev can index the repo. *Verify that kubesearch picks it up.*
4. **What is public, and is fine to be:** the design, the ADRs, the domain, the tailnet name, the private LAN plan, and Stan's name and GitHub login.
5. **What is never public:**
   - **Plaintext secrets of any kind.** `*.sops.yaml` files are encrypted; their key names remain readable.
   - **Credentials:** age keys, talosconfig, kubeconfigs (git-ignored), Tailscale auth keys, the restic password.
   - **Personal email addresses:** commits use the GitHub no-reply address, and GitHub-side merges use it too, once "Keep my email addresses private" is on.
   - **Unfixed security weaknesses** (see rule 6).
6. **Issues and PRs are public as well.** The `audit` skill reports security-relevant findings (RBAC too broad, a missing egress policy, exposed services) only to Stan, in chat or as a private draft security advisory. **They never go in a public issue.** Logs pasted into issues or PRs must be scrubbed of tokens, IPs outside the documented plan, and personal data.

## Consequences

- Push protection catches the most likely accident, a pasted token, before it reaches GitHub.
- Enforcement no longer depends on the Student Pack.
- **Anything committed is effectively permanent.** Forks and caches outlive deletion, so the scan before switching (rule 5) matters, and the `sops-encrypted` check must exist before the first secret lands.

## Alternatives considered

- **Stay private under Pro:** no secret scanning, and enforcement tied to the Pack's expiry. Rejected.
- **Private with paid GitHub Secret Protection:** costs money for a homelab. Rejected.

## Compliance

- `mise run github:diff` checks visibility and every feature above.
- `audit` follows rule 6 for security findings.
