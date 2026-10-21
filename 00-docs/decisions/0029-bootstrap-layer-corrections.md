# ADR-0029: Corrections from building the bootstrap layer

- **Status:** Accepted (rule 3 superseded by ADR-0030)
- **Date:** 2026-10-21
- **Deciders:** Stan (owner), Claude (proposer)
- **Related:** ADR-0003 (supersedes the `values.yaml` file in its component shape), ADR-0013 (supersedes rules 3–4's mechanism), ADR-0022 (supersedes Flux's PriorityClass), ADR-0025 (rule 6: `values.yaml` → `helmrelease.yaml`)

## Context

Writing the first real components (Flux, Cilium) against the actual charts and tools showed that three details in earlier ADRs don't work as written. The intent of each ADR stands. Only the mechanism changes.

1. **ADR-0003 and ADR-0015 put Helm values in a separate `values.yaml`, fed to the HelmRelease through a kustomize `configMapGenerator`.**
   - That needs either a name-reference plumbing file per component, or a ConfigMap whose changes Flux only notices on the next interval.
   - The home-operations pattern keeps values **inline** in `helmrelease.yaml`, and the bootstrap reads `.spec.values` from that file.
2. **ADR-0013 said the Kustomization and HelmRelease defaults are applied "by kustomize patches in the FluxInstance".**
   - FluxInstance patches modify the *Flux controllers' own manifests*, not our Kustomizations.
   - Defaults for child objects have to come from a parent Kustomization's `spec.patches`.
3. **ADR-0022 gave Flux the `platform-critical` PriorityClass.**
   - That class is created *by* Flux, so the bootstrap install of Flux (before Flux exists) can't reference it.

## Decision

1. **Helm values live inline in `helmrelease.yaml` (`spec.values`).** The component shape is now:

   ```
   <component>/ks.yaml + app/{kustomization, namespace, ocirepository, helmrelease, *.sops}.yaml
   ```

   - The bootstrap helmfile reads `.spec.values` from that file and `.spec.ref.tag` from `ocirepository.yaml`.
   - So values of bootstrapped releases (Cilium, flux-operator, flux-instance) must not contain `${VAR}`s: helmfile doesn't substitute them.
   - Secret values still come through `valuesFrom` (ADR-0014).
2. **The uniform settings live in `03-cluster/flux-defaults.yaml`.** `03-cluster/kustomization.yaml` applies them to every `layer-*` Kustomization. Each layer then patches every component Kustomization it creates:
   - `retryInterval`, `timeout`, `wait`, `deletionPolicy`
   - `postBuild.substituteFrom: cluster-settings`

   Those component Kustomizations in turn patch every HelmRelease they create:
   - drift detection
   - CRD handling (`CreateReplace`)
   - install and upgrade remediation
   - rollback cleanup

   These are **enforced** settings, not overridable defaults: components never set them. The two components outside the layers (`flux-operator`, `flux-instance`) state the HelmRelease settings themselves.
3. **SOPS decryption is enabled once, at the controller,** with `--sops-age-secret=sops-age` on kustomize-controller (a FluxInstance patch). No Kustomization needs a `decryption` block.
4. **Flux (operator and controllers) uses the built-in `system-cluster-critical` PriorityClass,** which exists before Flux does. `platform-critical` remains for cloudflared and the tailscale operator.
5. **A component's second Flux Kustomization** (needed when CRD ordering requires it, e.g. `cilium` → `cilium-config`) points to a subfolder of `app/` (`app/config/`). The component folder still holds only `ks.yaml`, `app/` and, when needed, `image/`.
6. **Floating defaults in upstream charts are overridden.** Example: flux-instance's `distribution.artifact` defaults to `:latest`. We pin it to the tag that matches the operator version.

## Consequences

- One file fewer per component, and value changes reconcile immediately.
- The uniform settings are written exactly once. The flip side: a component that genuinely needs a different value for an enforced field needs an ADR.
- ADR-0025 rule 6's rehearsal diff now touches `03-cluster/flux-instance/app/helmrelease.yaml` instead of `values.yaml`.

## Alternatives considered

- **Keep `values.yaml` + `configMapGenerator` + a name-reference config per component:** more files and plumbing for no benefit. Rejected.
- **Copy the defaults into every `ks.yaml` and HelmRelease:** many copies of the same block that drift apart. Rejected.

## Compliance

- `component-shape` enforces the folder shape, the annotations, the paths into `app/`, and namespace = folder.
- `bootstrap-literals` rejects any version or chart literal in `02-bootstrap/`.
- `render` builds every Flux path, substitutes `cluster-settings`, validates every object against Kubernetes and CRD schemas, and runs `helm template` on every HelmRelease's inline values.
