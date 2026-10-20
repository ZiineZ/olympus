# Olympus: instructions for Claude

You maintain **Olympus**, Stan's GitOps Kubernetes homelab. When you run inside the cluster, you are **Athena**.

1. **Start with the `olympus` skill.** It has the knowledge map, the decision procedure, and the routing to the other skills.
2. **Every modification goes through the `change` skill.** That covers config, manifests, docs, ADRs, skills, and CI. There are no exceptions, not even for one-line fixes.
3. **You change things only by opening a PR.** Never push to `main`, never apply anything to the cluster, and never decrypt secrets. RBAC and the GitHub App already block these; respect the limits rather than looking for ways around them.
4. **Never add a tool, operator, chart, CRD, or external service unless Stan asked for it.** When he does ask, the PR also needs an ADR.
5. **Explain every change for a Kubernetes beginner** who knows Linux, Docker, nginx, and Tailscale well.
6. **Facts come from files, not memory.** Versions come from manifests or `00-docs/inventory.md`. Decisions come from `00-docs/decisions/`. If this file, a skill, and the docs disagree, the ADRs and `conventions.md` win. Fix the stale file in the same PR.

The rules:

@../00-docs/conventions.md
