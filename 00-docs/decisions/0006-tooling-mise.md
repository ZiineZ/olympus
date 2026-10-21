# ADR-0006: Tooling: mise pins every CLI and owns all tasks

- **Status:** Accepted (`talhelper` superseded by ADR-0028)
- **Date:** 2026-10-20
- **Deciders:** Stan (owner), Claude (proposer)
- **Related:** ADR-0003, ADR-0004, ADR-0015

## Context

"Which version of talosctl was on my laptop?" is drift too. Imperative commands scattered across READMEs are hidden config. Stan's MacBook, CI, and Athena's container must all run identical tool versions and identical entrypoints.

## Decision

1. **`.config/mise.toml` pins every CLI**, with `.config/mise.lock` committed:
   - `talosctl`, `talhelper`
   - `kubectl`, `flux2`, `helm`, `helmfile`, `kustomize`
   - `sops`, `age`
   - `kubeconform`, `flate`
   - `cilium-cli`, `hubble`, `k9s`
   - `yq`, `gh`, `python`
   - `kyverno` (CI policy evaluation only, ADR-0021)

   Renovate updates them (ADR-0023).
2. **mise tasks are the only imperative entrypoints.** There is no justfile, Makefile, or ad-hoc script outside them.

   | Task | Does |
   |---|---|
   | `talos:genconfig` | talhelper → `01-talos/clusterconfig/` (git-ignored) |
   | `talos:apply node=<name> [insecure=true]` | apply one node's generated config |
   | `talos:diff node=<name>` | `talosctl apply-config --dry-run`: shows how a node differs from git |
   | `talos:bootstrap` | etcd bootstrap and kubeconfig fetch (first control plane only) |
   | `bootstrap:apps` | Gateway API CRDs + age secret + deploy key + `helmfile sync` (ADR-0015) |
   | `check` | every check in ADR-0004 |
   | `impact paths=<…>` | prints the co-change checklist for the given paths |
   | `docs:gen` | regenerates `00-docs/inventory.md` |

3. **Check scripts are Python 3 standard library only** (`.github/checks/`). A broken venv must never break the checks. The same lesson as Sentinel.
4. **Every manifest has a schema modeline** (ADR-0003 rule 8), so editors validate as you type.
5. **A formatter** (yamlfmt or prettier) is deferred until the first formatting-inconsistency PR (ADR-0026).

## Consequences

- `mise install` gives a fresh laptop the exact toolchain.
- CI and Athena's image install tools from the same file.

## Alternatives considered

- **just + Homebrew:** two tools, and Homebrew is unpinned. Rejected.
- **devcontainer:** heavier, and awkward on macOS for `talosctl cluster create`. Rejected.

## Compliance

- CI runs `mise install` + `mise run check`.
- `root-clean` rejects a justfile or Makefile at the root.
