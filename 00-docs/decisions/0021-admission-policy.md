# ADR-0021: Admission policy: built-in Pod Security and ValidatingAdmissionPolicy, no Kyverno

- **Status:** Accepted
- **Date:** 2026-10-20
- **Deciders:** Stan (owner), Claude (proposer)
- **Related:** ADR-0011, ADR-0016, ADR-0022

## Context

Olympus needs to enforce its standards at the API server too, not just in CI: resources, pinned images, labels, storage class, and exposure rules. Kyverno would add about 4 controllers and a webhook that can block the API server if it is down. Kubernetes 1.36 ships ValidatingAdmissionPolicy (GA since 1.30) and MutatingAdmissionPolicy (GA in 1.36), and both run in-process.

## Decision

1. **Pod Security Admission:**
   - The cluster default is `enforce: restricted`, `audit: restricted`, `warn: restricted`, set in the Talos apiServer `admissionControl` (ADR-0007).
   - A namespace that needs less sets `pod-security.kubernetes.io/enforce: baseline|privileged` in its `namespace.yaml`, with a one-line comment saying why. Every exception is listed in `conventions.md`.
   - **Initial exceptions:**
     - `kube-system`: privileged (Cilium)
     - `victoria-metrics`: privileged (node-exporter hostPID/hostNetwork)
     - `tailscale`: privileged (proxy NET_ADMIN)
     - `local-path-provisioner`: privileged (hostPath helpers)
     - `k8up`: baseline (backup pods may run as root to read files; *verify*)
2. **ValidatingAdmissionPolicies** live in `04-platform/03-security/admission-policies/`. Each policy has a matching binding:

   | Policy | Matches | Action |
   |---|---|---|
   | `require-requests-and-memory-limit` | Deployments, StatefulSets, DaemonSets, Jobs, CronJobs (all containers incl. init) | **Deny** if `requests.cpu`, `requests.memory` or `limits.memory` is missing |
   | `memory-limit-equals-request` | same | **Warn + Audit** if `limits.memory != requests.memory` |
   | `no-cpu-limits` | same | **Warn + Audit** if `limits.cpu` is set (ADR-0022) |
   | `pinned-images` | same | **Deny** if an image has no tag, or tag `latest`. **Warn** if no `@sha256:` digest |
   | `require-app-name-label` | same, pod template | **Deny** if `app.kubernetes.io/name` is missing |
   | `pvc-explicit-storage-class` | PersistentVolumeClaims | **Deny** if `storageClassName` is unset |
   | `no-nodeport` | Services | **Deny** `type: NodePort` |
   | `ingress-tailscale-only` | Ingresses | **Deny** unless `ingressClassName: tailscale` |

3. **Scope.** Bindings exclude namespaces labelled `olympus/policy: exempt`. That label is allowed only on `kube-system` and `flux-system` (operator-generated objects), and each use is listed in `conventions.md`. Upstream charts are made compliant through their values, not through exemptions.
4. **Rollout.** A new Deny policy first ships for one week with `validationActions: [Warn, Audit]`, then switches to `[Deny]` in a follow-up PR.
5. **CI evaluates the same policy files offline** against the rendered manifests (`policies-offline`, ADR-0004), so a PR fails before the cluster ever sees it.
6. **No MutatingAdmissionPolicies** at first. Explicit values in git beat invisible mutation: what you read is what runs.

## Consequences

- Zero extra pods, and no webhook that can wedge the API server.
- CEL policies are less expressive than Kyverno. There is no generate and no image-signature verification. Those needs would be a new ADR.

## Alternatives considered

- **Kyverno:** about 4 controllers for 8 rules. Its generate and verifyImages features aren't needed. Deferred (ADR-0026).
- **Gatekeeper:** heavier, and it uses Rego. Rejected.

## Compliance

- `policies-offline` in CI.
- `audit` reads the VAP audit annotations and Warn events and reports violations.
