# ADR-0014: Secrets: SOPS with age, decrypted by Flux

- **Status:** Accepted
- **Date:** 2026-10-20
- **Deciders:** Stan (owner), Claude (proposer)
- **Related:** ADR-0005, ADR-0013, ADR-0024, ADR-0025

## Context

Secrets must live in git, so that the repo plus one key is enough to rebuild everything. The repo may be public. Athena must never be able to read a plaintext secret.

## Decision

1. **SOPS + age.** There is one age identity, Stan's. Its private key is stored in **two** places: Stan's password manager, and a printed paper copy kept off-site. It is never stored on a node, in CI, or in Athena's pod.
2. **`.sops.yaml` creation rules**, in order:
   - `01-talos/.*\.sops\.yaml$`: encrypt all values (Talos secrets aren't Kubernetes objects).
   - `.*\.sops\.yaml$`: `encrypted_regex: ^(data|stringData)$`, so metadata stays readable for review and for checks.
3. **Every Kubernetes `Secret` lives in a file named `*.sops.yaml`**, one Secret per file, placed next to what uses it (ADR-0003 rule 6).
4. **The cluster's decryption key** is the Secret `sops-age` in `flux-system`. It is created once by `mise run bootstrap:apps` from the local key file, and never committed (ADR-0015).
5. **Helm values that must be secret** (for example Kite's `encryptKey`) are injected with HelmRelease `valuesFrom` a SOPS-encrypted Secret. They never appear in `values.yaml`.
6. **Rotation:** to rotate the age key, add the new recipient, run `sops updatekeys` on every file, replace `sops-age`, then remove the old recipient. The procedure is `runbooks/rotate-age-key.md`.

## Consequences

- The repo can be public.
- Losing the age key means re-creating every secret by hand, which is why it is kept in two places.
- Athena can read the encrypted files in git, but can neither decrypt them nor read `Secret` objects through the API (ADR-0024).

## Alternatives considered

- **Sealed Secrets:** needs a controller, and its key is bound to the cluster, so a rebuild needs a key backup anyway. Rejected.
- **External Secrets + 1Password:** a paid external dependency on the critical path. Rejected for now.

## Compliance

- The `sops-encrypted` check (ADR-0004).
- **Quarterly hand-made-Secret check, run by Stan.** It needs the admin kubeconfig, because Athena has no Secret access by design. The command is in `runbooks/break-glass.md` and lists every Secret that has none of these:
  - Flux ownership labels
  - a Helm owner (`owner=helm`)
  - a controller `ownerReference`

  Any Secret it lists was created by hand, which is drift.
