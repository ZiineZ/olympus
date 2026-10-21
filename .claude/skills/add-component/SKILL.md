---
name: add-component
description: Add or remove a platform component (04-platform) or an application (05-apps) in the Olympus repo with the standard folder shape, namespace, Pod Security, resources, priority, network policy, exposure, monitoring, backups and docs. Use when Stan asks to deploy, install, add, migrate, remove or decommission any service, operator or chart. It is always used together with the change skill.
---

# Add or remove a component

Run it inside the `change` workflow: this skill decides *what* the PR contains, and `change` decides *how* it is made.

## 1. Decide where it goes

- **A platform component** (shared infrastructure) goes in `04-platform/<NN-group>/<name>/`.
  - **It requires Stan's explicit request and a new ADR** in the same PR (ADR-0000).
  - First check whether ADR-0026 lists it as deferred, and whether its trigger has fired.
  - Pick the existing group it belongs to. Groups are a closed set; never renumber them.
- **An app** (Stan's service) goes in `05-apps/<name>/`, one namespace each. No ADR is needed unless it brings a new kind of dependency, such as the first Postgres (which means CloudNativePG, per ADR-0026).

## 2. Pick a template

Copy the **most similar existing component** and adapt it, so the repo itself is the template. Never write manifests from memory.

- **Own apps:** use bjw-s `app-template`. Copy an existing `app-template` app once one exists.
- **Third-party software:**
  - Use the upstream chart if it is maintained (a release within 6 months) and exposes resources and securityContext.
  - Otherwise use `app-template` with the upstream image.
- See how others configure the chart at kubesearch.dev, then map that onto our conventions.

## 3. Required pieces (every box ticked, or justified in the PR)

**`<name>/ks.yaml`**
- [ ] A Flux Kustomization `<name>`: `path: ./<layer>/<group>/<name>/app`, `targetNamespace` or the namespace in the manifests.
- [ ] `dependsOn` on whatever it needs: CRDs, storage, secrets operator, and so on.
- [ ] Annotations:
  - `olympus/description`: one sentence
  - `olympus/docs`: comma-separated living-doc paths that must co-change
  - `olympus/adr`: the governing ADRs

**`app/kustomization.yaml`**
- [ ] Lists every file in `app/`.
- [ ] `components:` includes `../../../03-cluster/components/default-deny` (adjust the relative path).
- [ ] If the component has PVCs, it also includes `…/components/backup`. Otherwise the namespace has `olympus/backup: none` + a reason.

**`app/namespace.yaml`**
- [ ] `name` = the folder name.
- [ ] Pod Security: no label means the cluster default `restricted`. If it needs less, use `pod-security.kubernetes.io/enforce: baseline|privileged` with a `# why:` comment, **and add it to the exceptions list in `conventions.md`**.
- [ ] If it is public: `olympus/gateway-access: public`.

**`app/ocirepository.yaml` + `app/helmrelease.yaml`**
- [ ] The chart is pinned to an exact tag, plus `verify` (cosign) where the publisher signs.
- [ ] The HelmRelease sets `interval` and `chartRef`. Everything in `03-cluster/flux-defaults.yaml` (drift detection, CRD handling, remediation) comes from the layer, so **never** repeat it (ADR-0029).
- [ ] Secret values come through `valuesFrom` a `*.sops.yaml` Secret, never inline.

**Values (inline in `helmrelease.yaml` under `spec.values`)**
- [ ] Every container: `requests.cpu`, `requests.memory`, `limits.memory` (= request), **no `limits.cpu`**. Add a sizing comment saying where the numbers came from.
- [ ] `priorityClassName`: `platform-critical` | `platform` for platform components. Leave it unset for apps (`apps` is the global default).
- [ ] securityContext: runAsNonRoot, no privilege escalation, drop ALL, seccomp RuntimeDefault, read-only root filesystem where possible, `hostUsers: false` where supported.
- [ ] Images: `tag@sha256:digest`.
- [ ] Pod label `app.kubernetes.io/name`.
- [ ] Stateful: `nodeSelector: {olympus/tier: heavy}`, and PVC `storageClassName: local-path`.
- [ ] Replicas: 1. No PDB.
- [ ] Own apps: readiness and liveness probes.

**Exposure (pick at most one, ADR-0011)**
- [ ] Public: an `HTTPRoute` to `parentRefs: [{name: public, namespace: gateway}]`, host `<name>.${PUBLIC_DOMAIN}`. Tell Stan about the Cloudflare Access app step, which happens outside git (runbook).
- [ ] Admin UI: an `Ingress` with `ingressClassName: tailscale`, host `<name>${TS_HOST_SUFFIX}`.
- [ ] Ingress allows in the namespace's network policies, for whichever path above applies.

**Observability**
- [ ] A ServiceMonitor or PodMonitor, if it exposes metrics (enable it in the chart values).
- [ ] Alert rules (a VMRule) in `app/` for its failure modes.
- [ ] A dashboard ConfigMap with `grafana_dashboard: "1"`, or a grafana.com `gnetId` + `revision`.

**Secrets**
- [ ] One Secret per `*.sops.yaml`, encrypted. You can't encrypt with Stan's key from the pod unless the public age recipient is in `.sops.yaml` (encrypting needs only the public key). Never commit plaintext. If you need a secret value, ask Stan to supply it.

**Registration and docs**
- [ ] Add `./<name>/ks.yaml` to the group's `kustomization.yaml`.
- [ ] `architecture.md`: the right section. Apps go in §9. Platform components go in their layer and flow sections.
- [ ] A new ADR (platform components).
- [ ] A runbook, if it has operational steps (Stan actions, restore specifics).
- [ ] `.github/renovate.json5`: group or auto-merge rules, if it belongs to a group or to the platform-critical set.
- [ ] `mise run docs:gen` to regenerate the inventory.

## 4. Removing a component

Work through the same list in reverse:

- **Delete the folder** and its entry in the group's `kustomization.yaml`. Flux prunes everything it owned.
- **PVs remain (`Retain`).** Say so in the PR, and ask Stan whether to keep the data or delete it. If deleting, it's a follow-up PR with a runbook step, after the backups have been checked.
- **Public DNS records** are removed by external-dns, which only touches records it owns. Cloudflare Access apps must be removed by Stan.
- **Clean up everything that pointed at it:** dashboards, alerts, network policy allows, Athena egress, docs, skills, and Renovate rules.
- **Write a superseding or decommissioning ADR** if an ADR introduced the component.
