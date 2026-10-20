# Runbook 00 · Prep

Everything that must exist before the rehearsal (phase 1) and the real install (phase 2). Stan does every step here himself, because each one needs his machine, his accounts, or his hands. Each step says what success looks like.

## 1. GitHub repository ✅

Done on 2026-10-20 (ADR-0005, ADR-0027). The repo is public and `main` is protected by the rulesets in `.github/settings/rulesets/`.

- To re-check at any time: `mise run github:diff` should print `in sync`.
- To restore the settings after a click-change in the UI: `mise run github:apply` (needs Stan's admin token).

## 2. Toolchain on the MacBook

```bash
brew install mise
echo 'eval "$(mise activate zsh)"' >> ~/.zshrc && exec zsh
git clone https://github.com/ZiineZ/olympus.git ~/olympus && cd ~/olympus
mise trust .config/mise.toml
mise install
gh auth login
```

- `mise install` reads `.config/mise.toml` and verifies every download against the checksums in `.config/mise.lock`. A checksum mismatch aborts the install, and that is the point.
- **Success:** `mise doctor` reports no problems, and `talosctl version --client` and `kubectl version --client` print the versions pinned in `.config/mise.toml`.

## 3. The age key (the key to every secret) ✅

Created 2026-10-21. Its public key is the only recipient in `.sops.yaml`. If you haven't yet, **do the two storage steps below**: this key cannot be regenerated, and without it every secret has to be recreated by hand.

This creates the one identity that encrypts every secret in the repo (ADR-0014). **Do it on the Mac, and only once.**

```bash
mkdir -p ~/.config/sops/age
age-keygen -o ~/.config/sops/age/keys.txt
chmod 600 ~/.config/sops/age/keys.txt
```

The command prints `Public key: age1…`.

- The **public key** (`age1…`) is safe to share. Give it to Claude, who adds it to `.sops.yaml` in a PR.
- The **private key** is the line in `keys.txt` that starts with `AGE-SECRET-KEY-1`. It **never** goes into git, chat, CI, a node, or Athena.

Store the private key in **two** places:

1. In your password manager, as a secure note named `olympus age key`, holding the full contents of `keys.txt`.
2. On paper: print it, and keep the paper somewhere other than your dorm room.

`mise` sets `SOPS_AGE_KEY_FILE` to this path on every machine, so `sops` finds the key without further setup.

- **Success:** `age-keygen -y ~/.config/sops/age/keys.txt` prints the same `age1…` public key, and both copies exist.

## 4. Before phase 2 (the real install on zeus): not yet

These steps come later. They are listed here so nothing gets forgotten.

- [ ] **Back up `/srv` off the box** (about 143 GB), then test a restore of a few files. The install wipes the disk.
- [ ] **Decide** which current services on `lab` come back as apps and which are dropped.
- [ ] **Router:**
  - router mode behind the repeater, LAN `192.168.50.0/24`, DHCP pool `.100`–`.199` only (ADR-0009)
  - no port forwarding
- [ ] **Cabling:** zeus's 2.5 GbE port goes to the switch or router. Talos doesn't do Wi-Fi.
- [ ] **zeus BIOS** (ADR-0009):
  - set the UMA frame buffer to the minimum
  - power on after AC loss
  - performance mode
  - SecureBoot off
- [ ] **Accounts and tokens, each created in the phase that first needs it:**
  - a Cloudflare R2 bucket `olympus-backups` and its token (ADR-0017)
  - a Tailscale OAuth client (ADR-0012)
  - a healthchecks.io check (ADR-0019)
  - Anthropic API keys for Athena and Kite (ADR-0024, ADR-0020)
