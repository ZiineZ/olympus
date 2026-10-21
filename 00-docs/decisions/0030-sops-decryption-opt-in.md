# ADR-0030: SOPS decryption is opted into per Kustomization

- **Status:** Accepted
- **Date:** 2026-10-21
- **Deciders:** Stan (owner), Claude (proposer)
- **Related:** ADR-0014, ADR-0029 (supersedes its rule 3)

## Context

ADR-0029 rule 3 said that starting kustomize-controller with `--sops-age-secret=sops-age` enables SOPS decryption for every Kustomization, so "no Kustomization needs a `decryption` block".

That is wrong. The rehearsal of the core network layer (2026-10-21) applied the Tailscale operator's `*.sops.yaml` Secret **still encrypted**: the cluster held `ENC[AES256_GCM,…]` as the "value", and the operator was rejected with `401 API token invalid`. The flag only tells the controller *where the age key is*. Decryption happens only for Kustomizations that set `spec.decryption.provider: sops`. The home-operations template does both. ADR-0029 copied only the flag.

## Decision

1. kustomize-controller keeps `--sops-age-secret=sops-age` (the FluxInstance patch). That's where the key comes from.
2. **Every component Kustomization gets `decryption: {provider: sops}`** through `03-cluster/flux-defaults.yaml`, so components never write it themselves.
3. The two components outside the layers (`flux-operator`, `flux-instance`) hold no secrets and need no decryption. If one ever does, its `ks.yaml` sets the block itself.

## Consequences

- Encrypted Secrets reach the cluster decrypted. The Cloudflare tunnel and DNS secrets would have failed the same way on zeus. The rehearsal caught it first.
- Showing ciphertext as a value leaked nothing (it is ciphertext), but it is a silent failure mode. Rule 2 makes it structurally impossible for components inside the layers.

## Alternatives considered

- **A `decryption` block in every `ks.yaml`:** many copies of the same block. Rejected.
- **Rely on the controller flag alone:** that's what failed. Rejected.

## Compliance

- `flux-defaults.yaml` is the single place where the setting lives.
- The rehearsal checks a decrypted value's *shape* (length and prefix only) for every new secret.
