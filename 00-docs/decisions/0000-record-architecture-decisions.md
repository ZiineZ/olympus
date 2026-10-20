# ADR-0000: Record architecture decisions

- **Status:** Accepted
- **Date:** 2026-10-20
- **Deciders:** Stan (owner), Claude (proposer)
- **Related:** ADR-0004, ADR-0005

## Context

Olympus has to stay drift-free over years, and it is maintained by a beginner (Stan) together with an AI agent (Athena). Neither of them can rely on memory alone. Decisions and the reasons for them must live in the repository, so that a later "let's do it differently" becomes a deliberate, recorded change instead of a quiet divergence.

## Decision

1. Every significant decision gets an ADR in `00-docs/decisions/`, named `NNNN-kebab-case-title.md`. `NNNN` is a 4-digit number, assigned sequentially and never reused.
2. **A decision is significant** when it:
   - adds or removes a tool, operator, Helm chart, CRD, or external service;
   - changes a convention, a cluster-wide default, addressing, a security boundary, or the change workflow; or
   - contradicts or extends an existing ADR.
3. **Every ADR uses this structure:** the header block (Status, Date, Deciders, Related), then the sections Context, Decision, Consequences, Alternatives considered, and Compliance. Compliance says how the decision is enforced or checked.
4. **Statuses:**
   - `Accepted`: in force.
   - `Proposed`: merged on purpose as an open question, with the pending input named.
   - `Deferred`: deliberately not now; lives in the register, ADR-0026.
   - `Superseded by ADR-XXXX`: replaced by a later ADR.
   - `Rejected`: considered and turned down.
5. **Approval:** an ADR is written with its intended status in a PR. Merging the PR (Stan's approval) is the act of acceptance. An unmerged ADR does not exist.
6. **Immutability:** an Accepted ADR is never edited. The only allowed changes are the status line (set to `Superseded by …`) and typo fixes. To change a decision, write a new ADR that supersedes the old one.
7. **Versions:** any version number in an ADR is historical ("at decision time"). Current versions live only in manifests (ADR-0004).
8. **Living docs:** `architecture.md`, `conventions.md`, and `runbooks/` always describe the current state, meaning all Accepted ADRs applied. A new or superseding ADR must update them in the same PR.

## Consequences

- The ADR set is the project's long-term memory for both Stan and Athena.
- History stays readable: superseded ADRs remain, with a pointer forward to their replacement.
- There is a little overhead per decision, which is intentional friction against tool sprawl.

## Alternatives considered

- **Editing a single design doc in place:** loses the "why" and the history. Rejected.
- **A wiki or issues:** lives outside git, which is drift by definition. Rejected.

## Compliance

- The `adr-format` check validates the file name, header fields, and allowed status values.
- A sync rule requires that a PR adding a file in `decisions/` also changes `conventions.md` or `architecture.md`, or carries a `No doc change:` justification (ADR-0004).
