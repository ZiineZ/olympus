## Why

<!-- The problem or goal in plain words, for a Kubernetes beginner. Link the issue, alert, or ADR. -->

## What changed

<!-- Bullets. One concern per PR. -->

## Impact checklist

<!-- From `mise run impact` + the manual sweep in the `change` skill. Every line: changed, or not affected + why. -->
- [ ] a. component itself
- [ ] b. dependents
- [ ] c. shared cluster primitives
- [ ] d. node level (Talos)
- [ ] e. bootstrap
- [ ] f. upgrades (Renovate, tuppr)
- [ ] g. CI and checks
- [ ] h. living docs (README, architecture, conventions, runbooks)
- [ ] i. decisions (ADR)
- [ ] j. agent config (.claude)
- [ ] k. outside git (GitHub settings, tailnet policy, Cloudflare)

<!-- Skipping a required co-change? One line per path, with a reason:
No doc change: <path> — <reason>
-->

## How verified

- [ ] `mise run check` passes

## Learn more

<!-- Upstream docs that explain the concepts in this PR. -->
