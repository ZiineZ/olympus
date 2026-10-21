<div align="center">

# 🏛️ Olympus

**A GitOps Kubernetes homelab on Talos Linux: declared in git, reconciled by Flux, watched over by Athena.**

[![validate](https://github.com/ZiineZ/olympus/actions/workflows/validate.yaml/badge.svg?branch=main)](https://github.com/ZiineZ/olympus/actions/workflows/validate.yaml)
![Talos](https://img.shields.io/badge/OS-Talos_Linux-FF7300?style=flat-square&logo=linux&logoColor=white)
![Kubernetes](https://img.shields.io/badge/Kubernetes-326CE5?style=flat-square&logo=kubernetes&logoColor=white)
![Flux](https://img.shields.io/badge/GitOps-Flux-5468FF?style=flat-square&logo=flux&logoColor=white)
![Cilium](https://img.shields.io/badge/CNI-Cilium-F8C517?style=flat-square&logo=cilium&logoColor=black)
![SOPS](https://img.shields.io/badge/secrets-SOPS_%2B_age-2E7D32?style=flat-square&logo=letsencrypt&logoColor=white)
![Renovate](https://img.shields.io/badge/updates-Renovate-1A1F6C?style=flat-square&logo=renovate&logoColor=white)
![Tailscale](https://img.shields.io/badge/access-Tailscale-242424?style=flat-square&logo=tailscale&logoColor=white)
![Cloudflare](https://img.shields.io/badge/edge-Cloudflare-F38020?style=flat-square&logo=cloudflare&logoColor=white)
![Claude](https://img.shields.io/badge/agent-Athena_(Claude)-D97757?style=flat-square&logo=claude&logoColor=white)

</div>

> [!IMPORTANT]
> **Git is the only way in.** Nothing on this cluster is changed by hand: no `kubectl apply`, no click-ops, no SSH (Talos has none). Every change is a pull request, and Flux reverts anything that drifts.

> [!TIP]
> New here? Read in this order: [conventions](../00-docs/conventions.md) → [architecture](../00-docs/architecture.md) → [decisions](../00-docs/decisions/).

---

## 🗺️ How it fits together

```mermaid
flowchart LR
  classDef git fill:#24292f,stroke:#57606a,color:#fff
  classDef actor fill:#5468ff,stroke:#3b4bd8,color:#fff
  classDef k8s fill:#326ce5,stroke:#1f4fb8,color:#fff
  classDef edge fill:#f38020,stroke:#c4650f,color:#fff
  classDef ext fill:#2e7d32,stroke:#1b5e20,color:#fff

  stan([🧑 Stan]):::actor -- PR + review --> repo[(📦 olympus<br/>main)]:::git
  athena([🦉 Athena]):::actor -- PR only --> repo
  renovate([🤖 Renovate]):::actor -- version PRs --> repo
  repo -- pull + webhook --> flux

  subgraph cluster [☸️ cluster olympus]
    flux[Flux]:::k8s --> platform[Platform<br/>network · storage · security<br/>observability · operations · agent]:::k8s
    flux --> apps[Apps]:::k8s
  end

  internet((🌍 Internet)) --> cf[Cloudflare<br/>Access + Tunnel]:::edge --> apps
  tailnet((🔒 Tailnet)) --> uis[Kite · Grafana<br/>Hubble · Flux UI]:::k8s
  cluster -. alerts .-> ntfy((📱 ntfy)):::ext
  cluster -. daily backups .-> r2((🪣 R2)):::ext
```

## 🧱 The layers

Every folder is a layer, numbered in the order it's built. A layer only depends on the ones before it.

| | Layer | What lives there | Applied by |
|:-:|---|---|---|
| 📚 | [`00-docs`](../00-docs/) | design, rules, decisions, runbooks | humans |
| 🪨 | `01-talos` | the node operating system, as config | Stan, `mise run talos:apply` |
| 🚀 | `02-bootstrap` | Cilium + Flux, used once per build | Stan, `mise run bootstrap:apps` |
| 🌀 | `03-cluster` | the Flux entrypoint and cluster-wide primitives | Flux |
| 🏗️ | `04-platform` | shared infrastructure, in six ordered groups | Flux |
| 📦 | `05-apps` | the actual services | Flux |

<details>
<summary><b>🧭 The stack at a glance</b></summary>

```mermaid
mindmap
  root((🏛️ Olympus))
    🪨 Nodes
      Talos Linux
      Image Factory
      tuppr upgrades
    🌐 Network
      Cilium + Hubble
      Gateway API
      Cloudflare Tunnel
      external-dns
      Tailscale operator
    💾 Data
      local-path
      k8up → R2
    🛡️ Security
      Pod Security
      ValidatingAdmissionPolicy
      SOPS + age
    📈 Observability
      VictoriaMetrics
      Grafana
      Kite
      ntfy alerts
    🔁 GitOps
      Flux Operator
      Renovate
      mise toolchain
    🦉 Agent
      Athena: Claude Code
      read-only RBAC
      PR-only writes
```

</details>

## 🔁 The life of a change

```mermaid
sequenceDiagram
  autonumber
  actor S as 🧑 Stan / 🦉 Athena
  participant G as 📦 GitHub
  participant CI as ✅ validate
  participant F as 🌀 Flux
  participant K as ☸️ cluster
  participant N as 📱 ntfy

  S->>G: branch + PR (impact checklist)
  G->>CI: run checks
  CI-->>G: render · policies · docs · co-change rules
  S->>G: review + squash-merge
  G-)F: webhook
  F->>K: reconcile, prune, revert drift
  K--)N: alert if anything fails
```

<details>
<summary><b>🌿 Branching model</b></summary>

```mermaid
gitGraph
  commit id: "main"
  branch athena/feat/kite
  checkout athena/feat/kite
  commit id: "feat(kite): …"
  checkout main
  merge athena/feat/kite id: "squash ✅"
  branch renovate/cilium
  checkout renovate/cilium
  commit id: "chore(deps): cilium"
  checkout main
  merge renovate/cilium id: "squash 🤖"
  branch stan/docs/runbook
  checkout stan/docs/runbook
  commit id: "docs: runbook"
  checkout main
  merge stan/docs/runbook id: "squash 🧑"
```

`main` is protected: every change is a PR, the `validate` check must be green, history is linear, and Athena's PRs need Stan's approval. The rulesets are code in [`.github/settings/`](settings/).

</details>

## 🛣️ Roadmap

```mermaid
timeline
  title From one mini PC to a small pantheon
  section Foundation
    0 · Prep         : Repo, rulesets, CI 🔨
                     : Backups target, BIOS, cabling
    1 · Rehearsal    : Full stack on the MacBook
  section Platform
    2 · Bootstrap    : Talos on zeus → Cilium → Flux
    3 · Core         : Storage, policies, Tailscale, Gateway, tunnel
    4 · Observability: VictoriaMetrics, Grafana, Hubble, Kite, ntfy
    5 · Agent        : Athena in-cluster
    6 · Upkeep       : Renovate, tuppr, k8up restore drill
  section Growth
    7 · Apps         : One app per PR
    8 · Nodes        : ares, artemis, apollo, hephaestus…
```

## 🏺 The pantheon

Machines and the agent are named after Greek gods; everything inside the cluster uses plain upstream names. **zeus** rules today, **athena** maintains, and new workers take the next name in line. See [ADR-0002](../00-docs/decisions/0002-naming-greek-pantheon.md).

## 🧠 Principles

> Git is the only source of truth · every fact lives once · every UI is read-only · structural limits beat instructions · boring by default · the cluster is cattle, the data is a pet.
>
> All of them: [ADR-0001](../00-docs/decisions/0001-guiding-principles.md)

<details>
<summary><b>📂 Repo map</b></summary>

```
olympus/
├── 00-docs/            architecture · conventions · inventory (generated) · decisions/ · runbooks/
├── 01-talos/           cluster.yaml · patches/ · schematics/
├── 02-bootstrap/       helmfile (cilium → flux)
├── 03-cluster/         flux entrypoint · cluster-settings · priority classes · components/
├── 04-platform/        01-network · 02-storage · 03-security · 04-observability · 05-operations · 06-agent
├── 05-apps/            one folder = one app = one namespace
├── .claude/            Athena's instructions + skills
├── .github/            this README · CI · checks · co-change rules · repo settings as code
└── .config/            mise toolchain + tasks
```

</details>

<div align="center">
<sub>Built and maintained with 🦉 Athena (Claude Code). Every change arrives through a pull request.</sub>
</div>
