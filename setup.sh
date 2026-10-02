#!/usr/bin/env bash
# setup.sh — DEVELOPMENT VPS for remote Claude Code sessions.
# Ubuntu 24.04 or 26.04. Idempotent: you can rerun it without breaking anything.
#
#   Phase 1 (root):  ssh root@NEW_IP 'bash -s' < setup.sh
#   Phase 2 (dev):   ssh dev@NEW_IP  'bash -s' < setup.sh
#
# Settings go in config.env (see config.env.example), put in front of the
# script: cat config.env setup.sh | ssh dev@NEW_IP 'bash -s'. A plain
# 'REPOS=... ssh ...' does NOT work: ssh doesn't carry local variables over.
#
# The phase is detected on its own from the user running it.
set -euo pipefail

DEV_USER=dev
SWAP_GB=4
# Fixed major, not "lts". Patches within 24 keep coming, but the jump to the
# next LTS is your call: with "lts" a future rerun would switch majors
# without warning, and that breaks the promise that rerunning the script breaks
# nothing. To follow the current LTS: NODE_V=lts ./setup.sh
NODE_V=${NODE_V:-24}
GO_V=${GO_V:-1.23}
PY_V=${PY_V:-3.12}

# OpenAI's Codex, the other agent. OFF by default and on purpose: it installs
# from its own channel (releases.openai.com) that self-updates, and enrolment
# does not finish without two settings in a ChatGPT account that this script
# cannot touch. Whoever doesn't use it shouldn't end up with an extra daemon.
#   CODEX=1 sudo -E bash setup.sh
CODEX=${CODEX:-0}

# Repos to turn into sessions. EMPTY on purpose: someone else's repos have no
# business here, and whoever clones this repo shouldn't end up cloning
# mine. They are chosen later, with 'claude-repos pick', which shows yours from
# GitHub and GitLab. For automation:
#
#   REPOS="owner/repo gitlab:group/other" ./setup.sh
#
# No prefix = GitHub, as always.
if [ -n "${REPOS:-}" ]; then
  read -r -a REPOS <<< "$REPOS"
else
  REPOS=()
fi

log() { printf '\n\033[1;36m▶ %s\033[0m\n' "$*"; }
ok()  { printf '  \033[32m✓\033[0m %s\n' "$*"; }
warn() { printf '  \033[33m!\033[0m %s\n' "$*"; }

# ─────────────────────────────────────────────────────────────
# PHASE 1 — as root: system base
# ─────────────────────────────────────────────────────────────
phase_root() {
  log "Phase 1 (root): system base"

  log "User $DEV_USER"
  if ! id "$DEV_USER" &>/dev/null; then
    adduser --disabled-password --gecos "" "$DEV_USER"
    ok "created"
  else ok "already exists"; fi
  usermod -aG sudo "$DEV_USER"
  install -d -m700 -o "$DEV_USER" -g "$DEV_USER" "/home/$DEV_USER/.ssh"
  if [ -f /root/.ssh/authorized_keys ]; then
    # MERGE, don't overwrite. With install, every pass clobbered dev's file and
    # wiped out the keys that had only been added there — a phone, a new
    # laptop. Rerunning the script must not lock you out: the header promises
    # it breaks nothing, and this broke it completely.
    AK="/home/$DEV_USER/.ssh/authorized_keys"
    touch "$AK"
    sort -u "$AK" /root/.ssh/authorized_keys -o "$AK"
    chown "$DEV_USER:$DEV_USER" "$AK" && chmod 600 "$AK"
    ok "SSH keys merged with root's ($(grep -c . "$AK") in total)"
  fi
  echo "$DEV_USER ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/90-$DEV_USER
  chmod 440 /etc/sudoers.d/90-$DEV_USER

  log "Harden SSH"
  sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/; s/^#\?PermitRootLogin.*/PermitRootLogin no/' /etc/ssh/sshd_config
  rm -f /etc/ssh/sshd_config.d/*cloud-init*  # cloud-init re-enables password auth
  # Our own file: sshd_config's Include comes first and in sshd the FIRST
  # occurrence of each directive wins, so this overrides everything else.
  #
  # Deliberately WITHOUT MaxAuthTries and WITHOUT AllowGroups. Every public key
  # the agent offers and gets rejected counts against MaxAuthTries: with several
  # keys loaded, the right one may come fourth and lock you out — and fail2ban
  # may ban your own IP for the failures. And it mitigates nothing, because
  # without passwords there is no brute force that works against an ed25519.
  # AllowGroups adds another way to lock yourself out if the group doesn't
  # exist, in exchange for nothing when only dev has authorized_keys.
  cat > /etc/ssh/sshd_config.d/60-hardening.conf <<'SSHD'
PermitEmptyPasswords no
HostbasedAuthentication no
X11Forwarding no
LoginGraceTime 30
LogLevel VERBOSE
SSHD
  # sshd -t BEFORE restarting: a typo here leaves sshd unable to start, and
  # without an out-of-band console that means being locked out of the machine.
  if sshd -t; then
    systemctl restart ssh && ok "public key only, no root, no X11"
  else
    rm -f /etc/ssh/sshd_config.d/60-hardening.conf
    echo "  ✗ invalid sshd config, reverted; not restarting ssh"
  fi

  log "Base packages"
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -qq
  apt-get install -y -qq --no-install-recommends \
    git curl wget make build-essential pkg-config libssl-dev unzip jq ripgrep \
    tmux ufw fail2ban ca-certificates gnupg python3-venv gh glab \
    bubblewrap >/dev/null
  ok "installed"

  log "Firewall + fail2ban"
  ufw --force default deny incoming >/dev/null
  ufw --force default allow outgoing >/dev/null
  # limit instead of allow: 6 connections per IP every 30 s. The limit is added
  # first and THEN the allow is removed — never the other way round, or there is
  # a moment with no accept rule at all for port 22.
  ufw limit in 22/tcp >/dev/null
  ufw --force delete allow OpenSSH >/dev/null 2>&1 || true
  ufw --force enable >/dev/null
  systemctl enable --now fail2ban >/dev/null
  ok "ufw active (22 only), fail2ban active"

  log "Containers out of reach from the Internet (DOCKER-USER)"
  # UFW is NOT enough. Docker writes its own rules and evaluates them BEFORE
  # ufw's, so a careless "-p 8080:80" opens the port to the Internet even though
  # ufw is denying it. The only place to cut that traffic is the DOCKER-USER
  # chain, which Docker creates if it doesn't exist and never flushes.
  #
  # The policy can be absolute —nothing incoming from the public interface
  # reaches a container— because the intended public path is the Cloudflare
  # tunnel, which goes OUT and comes in through localhost. No container
  # needs to publish on 0.0.0.0.
  #
  # It lives in after.rules and not in a loose "iptables -I": that way it
  # survives reboots, "ufw reload" and Docker upgrades.
  PUB_IF=$(ip route get 1.1.1.1 | awk '{for(i=1;i<NF;i++) if($i=="dev") print $(i+1); exit}')
  if [ -n "$PUB_IF" ] && ! grep -q 'BEGIN DOCKER-USER' /etc/ufw/after.rules; then
    cat >> /etc/ufw/after.rules <<EOF

# BEGIN DOCKER-USER (pocket-agents)
*filter
:DOCKER-USER - [0:0]
# Replies to connections the container itself opens must get through:
# without this line, an apt or a curl inside a container hangs.
-A DOCKER-USER -i ${PUB_IF} -m conntrack --ctstate RELATED,ESTABLISHED -j RETURN
-A DOCKER-USER -i ${PUB_IF} -j DROP
# The provider's metadata service can serve instance identity.
# A container has no reason to reach it, let alone a curious testcontainer.
-A DOCKER-USER -d 169.254.169.254 -j DROP
-A DOCKER-USER -j RETURN
COMMIT
# END DOCKER-USER
EOF
    ufw reload >/dev/null
    ok "nothing incoming on $PUB_IF reaches a container"
  else
    ok "DOCKER-USER rule already present"
  fi

  log "Automatic security updates"
  # Having the package installed is not enough: the policy is written so it
  # doesn't depend on the image's default, which changes between providers.
  cat > /etc/apt/apt.conf.d/20auto-upgrades <<'APT'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
APT
  # Automatic-Reboot set to false on purpose: rebooting on its own would wipe
  # out the tmux sessions without warning. The price is that a kernel patch is
  # installed but NOT applied until you reboot — which is why the watchdog
  # alerts over Telegram when a reboot is pending.
  cat > /etc/apt/apt.conf.d/51-reboot-policy <<'APT'
Unattended-Upgrade::Automatic-Reboot "false";
Unattended-Upgrade::Remove-Unused-Kernel-Packages "true";
APT
  ok "automatic patches; the reboot is your call (the bot tells you)"

  log "Swap ${SWAP_GB}G"
  if ! swapon --show | grep -q .; then
    fallocate -l "${SWAP_GB}G" /swapfile
    chmod 600 /swapfile && mkswap -q /swapfile && swapon /swapfile
    grep -q '^/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
    sysctl -qw vm.swappiness=10
    ok "active"
  else ok "swap already present"; fi
  # Our own file in sysctl.d, not a line in /etc/sysctl.conf: Ubuntu 26.04 no
  # longer ships that file nor the 99-sysctl.conf link that made systemd read
  # it, so a line there was silently lost on every reboot.
  echo 'vm.swappiness=10' > /etc/sysctl.d/60-pocket-agents.conf

  log "Journald capped at 500M"
  # A drop-in rather than editing journald.conf: it works whether or not the
  # distro ships that file in /etc, which newer systemd versions don't.
  install -d /etc/systemd/journald.conf.d
  printf '[Journal]\nSystemMaxUse=500M\n' > /etc/systemd/journald.conf.d/60-pocket-agents.conf
  systemctl restart systemd-journald && ok "applied"

  log "Docker Engine (compose / testcontainers)"
  if ! command -v docker &>/dev/null; then
    install -m0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
    chmod a+r /etc/apt/keyrings/docker.asc
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" \
      > /etc/apt/sources.list.d/docker.list
    apt-get update -qq
    apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin >/dev/null
    ok "installed"
  else ok "already there"; fi
  usermod -aG docker "$DEV_USER"
  # So the build cache doesn't eat 17 GB again.
  #
  # All three names of the same setting are here on purpose. 'defaultKeepStorage'
  # is the old one; in Docker 28 it splits into 'defaultReservedSpace' (what is
  # kept no matter what) and 'defaultMaxUsedSpace' (the real cap), and today's
  # documentation contradicts itself about which one is still alive: the dockerd
  # reference shows the new ones and the garbage collection page the old one. A
  # daemon silently ignores keys it doesn't know, so with all three it's
  # right on any version.
  #
  # Measured on 2026-09-10: with only the old key, this machine had 8.3 GB of
  # cache and three-week-old entries against a nominal 5 GB cap. That's why
  # there is also a daily sweep in userland (claude-docker-gc): it doesn't depend
  # on the daemon doing its job, nor on what the key is called next year.
  cat > /etc/docker/daemon.json <<'JSON'
{
  "ip": "127.0.0.1",
  "log-driver": "json-file",
  "log-opts": { "max-size": "10m", "max-file": "3" },
  "builder": {
    "gc": {
      "enabled": true,
      "defaultKeepStorage": "5GB",
      "defaultReservedSpace": "2GB",
      "defaultMaxUsedSpace": "5GB"
    }
  }
}
JSON
  # CAREFUL: this file is rewritten WHOLE on every pass. If you edit daemon.json
  # by hand on the machine, the next setup.sh wipes it out: changes go
  # here. "ip": 127.0.0.1 makes a -p without an address bind to loopback; the
  # real safety net is the DOCKER-USER rule above, because an explicit
  # "-p 0.0.0.0:X:Y" bypasses this setting.
  systemctl restart docker && ok "publish on loopback by default, GC at 5GB, logs rotated"

  log "Linger for $DEV_USER"
  loginctl enable-linger "$DEV_USER" && ok "user services survive logout"

  printf '\n\033[1;32m═══ PHASE 1 COMPLETE ═══\033[0m\n'
  printf 'Now:  ssh %s@<IP> \x27bash -s\x27 < setup.sh\n\n' "$DEV_USER"
}

# ─────────────────────────────────────────────────────────────
# PHASE 2 — as dev: toolchains, Claude, projects
# ─────────────────────────────────────────────────────────────
phase_dev() {
  log "Phase 2 ($USER): toolchains and Claude Code"

  log "mise (runtime manager)"
  if [ ! -x "$HOME/.local/bin/mise" ]; then
    curl -fsSL https://mise.run | sh >/dev/null
    ok "installed"
  else ok "already there"; fi
  export PATH="$HOME/.local/bin:$PATH"
  grep -q 'mise activate' ~/.bashrc || {
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
    echo 'eval "$(mise activate bash)"' >> ~/.bashrc
  }
  # ~/.profile: shims also in login and non-interactive shells (ssh host 'cmd')
  grep -q 'mise/shims' ~/.profile 2>/dev/null || \
    echo 'export PATH="$HOME/.local/share/mise/shims:$HOME/.local/share/npm-global/bin:$HOME/.local/bin:$PATH"' >> ~/.profile
  # In THIS script: shims, not 'mise activate' (its hook only runs in interactive shells)
  export PATH="$HOME/.local/share/mise/shims:$PATH"

  log "Runtimes: node $NODE_V, go $GO_V, python $PY_V, rust, uv"
  mise use -g -y "node@$NODE_V" "go@$GO_V" "python@$PY_V" rust@stable uv >/dev/null 2>&1
  mise reshim >/dev/null 2>&1 || true
  ok "$(mise ls --current 2>/dev/null | awk '{printf "%s@%s ", $1, $2}')"

  log "Claude Code"
  export NPM_CONFIG_PREFIX="$HOME/.local/share/npm-global"
  mkdir -p "$NPM_CONFIG_PREFIX"
  grep -q 'NPM_CONFIG_PREFIX' ~/.bashrc || {
    echo 'export NPM_CONFIG_PREFIX="$HOME/.local/share/npm-global"' >> ~/.bashrc
    echo 'export PATH="$NPM_CONFIG_PREFIX/bin:$PATH"' >> ~/.bashrc
  }
  export PATH="$NPM_CONFIG_PREFIX/bin:$PATH"
  command -v npm >/dev/null || { echo "  ✗ npm is not on PATH — mise did not install node"; exit 1; }
  npm install -g @anthropic-ai/claude-code 2>&1 | tail -2
  ok "$(claude --version 2>/dev/null || echo installed)"

  if [ "$CODEX" = "1" ]; then
    log "Codex (standalone)"
    # The standalone build and NOT the npm package: 'codex app-server daemon'
    # requires the install managed by the official installer and aborts with
    # "managed standalone Codex install not found" if only the npm one is there.
    # Having both is worse than neither — whichever the PATH order says wins,
    # and that order is not the same in your shell as in the units.
    if [ -d "$HOME/.local/share/npm-global/lib/node_modules/@openai/codex" ]; then
      warn "removing the npm codex: living alongside the standalone, PATH decides"
      npm rm -g @openai/codex >/dev/null 2>&1 || true
    fi
    CODEX_NON_INTERACTIVE=true sh -c \
      "$(curl -fsSL https://chatgpt.com/codex/install.sh)" 2>&1 | tail -3
    ok "$("$HOME/.local/bin/codex" --version 2>/dev/null || echo installed)"
  fi

  log "Claude permissions (~/.claude/settings.json)"
  # What is NOT here matters as much as what is. Left out of allow:
  # python3, make, npm run, uv run, mise and docker compose. They all run
  # whatever they're told, so with them in allow the "sudo" deny was
  # decorative: python3 -c 'os.system("sudo ...")' doesn't start with sudo, and
  # with NOPASSWD:ALL that's root without a single prompt. And with
  # --permission-mode acceptEdits the agent can first WRITE the Makefile or the
  # docker-compose.override.yml that it then runs.
  #
  # The realistic trigger isn't the agent misbehaving, it's a prompt
  # injection: these sessions read websites, issues and dependency READMEs.
  # Now those commands ask, and that's what the remote control on the phone is for.
  mkdir -p ~/.claude
  if [ ! -f ~/.claude/settings.json ]; then
    cat > ~/.claude/settings.json <<'JSON'
{
  "permissions": {
    "allow": [
      "Bash(git status:*)", "Bash(git diff:*)", "Bash(git log:*)", "Bash(git add:*)",
      "Bash(git commit:*)", "Bash(git pull:*)", "Bash(git checkout:*)", "Bash(git branch:*)",
      "Bash(go test:*)", "Bash(go build:*)", "Bash(go vet:*)",
      "Bash(cargo test:*)", "Bash(cargo build:*)", "Bash(cargo clippy:*)",
      "Bash(npm test:*)", "Bash(rg *)"
    ],
    "deny": [
      "Bash(git push:*)",
      "Bash(sudo *)",
      "Bash(systemctl *)",
      "Bash(ufw *)",
      "Read(**/.env)", "Read(**/.env.*)", "Read(**/.secrets.json)",
      "Read(**/id_rsa)", "Read(**/id_ed25519)", "Read(**/*.pem)", "Read(**/*.key)"
    ]
  }
}
JSON
    ok "created (arbitrary execution left out of allow; push and sudo denied)"
  else ok "already existed, leaving it alone"; fi

  log "Session tools (bin/, units, translations)"
  # The script arrives alone, via 'bash -s': there is no repo on the machine, so
  # it clones itself. Without this, the bot, the watchdog and the bridge stayed
  # as manual steps in the README, and whoever cloned the repo had half an
  # install. Over HTTPS on purpose: it works before 'gh auth login'.
  SELF_REPO=${SELF_REPO:-https://github.com/Pepebits/pocket-agents.git}
  SELF_DIR=~/dev/pocket-agents
  mkdir -p ~/dev
  if [ -d "$SELF_DIR/.git" ]; then
    git -C "$SELF_DIR" pull -q --ff-only 2>/dev/null || true
    ok "pocket-agents already there"
  else
    git clone -q "$SELF_REPO" "$SELF_DIR" && ok "pocket-agents cloned"
  fi
  if [ -d "$SELF_DIR/bin" ]; then
    mkdir -p ~/.local/bin ~/.config/systemd/user ~/.local/share/claude-rc
    # claude-* and not *: anything else in bin/ —a __pycache__ left by the
    # tests— made install fail and, with set -e, cut phase 2 short right here.
    install -m755 "$SELF_DIR"/bin/claude-* ~/.local/bin/
    install -m644 "$SELF_DIR"/systemd/*.service "$SELF_DIR"/systemd/*.timer \
            ~/.config/systemd/user/ 2>/dev/null || true
    install -m644 "$SELF_DIR/share/i18n.json" ~/.local/share/claude-rc/i18n.json
    systemctl --user daemon-reload 2>/dev/null || true
    ok "$(ls "$SELF_DIR"/bin | wc -l) tools installed"
    # The Docker sweep IS armed on its own: a timer installed and never
    # enabled is exactly the fault it came to fix. It deletes nothing that can't
    # be rebuilt —cache, dangling layers, containers stopped for a
    # week— and never touches volumes.
    systemctl --user enable --now claude-docker-gc.timer 2>/dev/null \
      && ok "Docker sweep armed (daily)" \
      || ok "Docker sweep installed — enable it with: systemctl --user enable --now claude-docker-gc.timer"
    # The Codex one is NOT armed on its own, unlike the sweep: without a login it
    # can't enrol, and arming it earlier leaves a service retrying against a 403
    # every ten seconds. Step 4 of the list below turns it on.
    [ "$CODEX" = "1" ] && ok "codex-app-server installed — armed after login"
  fi

  log "Projects in ~/dev"
  # Repos are NOT hardcoded. They are chosen with 'claude-repos pick', which needs a
  # real terminal and so can't live here: this script arrives over
  # stdin and has no way to ask. REPOS= still works for CI.
  if [ "${#REPOS[@]}" -gt 0 ]; then
    for r in "${REPOS[@]}"; do claude-repos add "$r" || true; done
  elif [ -s ~/.config/claude-sessions/repos.conf ]; then
    claude-repos sync
  else
    ok "none yet — pick them with: claude-repos pick"
  fi

  log "systemd template for Claude sessions"
  mkdir -p ~/.config/systemd/user
  cat > ~/.config/systemd/user/claude@.service <<'UNIT'
[Unit]
Description=Claude Code — %i
After=network-online.target

[Service]
Type=forking
WorkingDirectory=%h/dev/%i
Environment=TERM=xterm-256color
Environment=NPM_CONFIG_PREFIX=%h/.local/share/npm-global
# Per-session config. Without this, they all share ~/.claude.json: each process
# loads it into memory and rewrites it whole, so the last one to write clobbers
# the others' flags (workspace trust included). Credentials and the
# permission policy are shared by symlink inside each directory.
Environment=CLAUDE_CONFIG_DIR=%h/.claude-%i
# systemd does NOT read .bashrc or .profile: without this explicit PATH, the session
# starts (ExecStart uses an absolute path) but Claude can't find node, npm, go, cargo or uv.
# mise's shims go first; they are real binaries and don't depend on any hook.
Environment=PATH=%h/.local/share/mise/shims:%h/.local/share/npm-global/bin:%h/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
# -L: one tmux server PER service. With the default socket, the second service
# would talk to the first one's server, exit instantly and systemd would declare it dead.
ExecStart=/usr/bin/tmux -L claude-%i new-session -d -s claude-%i "exec %h/.local/share/npm-global/bin/claude --remote-control %i --permission-mode acceptEdits"
ExecStop=/usr/bin/tmux -L claude-%i kill-server
Restart=on-failure
RestartSec=15

[Install]
WantedBy=default.target
UNIT
  systemctl --user daemon-reload
  ok "claude@<project>.service available"

  # The first two steps are NOT stated by any error message: the login just
  # sits waiting without a word, and enrolment returns a 403 that you only
  # see if you look at the output of 'pair'. They are printed here because it's
  # the only place anyone will read them in time.
  CODEX_STEPS=""
  [ "$CODEX" = "1" ] && CODEX_STEPS="
  4. Codex, and in this order:
       a) In ChatGPT settings: enable device code authorization
          for Codex.                    <- without this the login just waits
       b) In ChatGPT settings: MFA enabled on the account.
          <- without this enrolment gives 403 'Multi-factor authentication required'
       c) codex login --device-auth      # gives you URL + code
       d) systemctl --user enable --now codex-app-server
          <- AFTER the login: the app-server doesn't reread auth.json, and started
             earlier it stays at 'the connection is errored', which sounds like network
       e) codex remote-control pair      # ~10 min code, ask for it as many
                                         # times as needed
     Or all of it from the Telegram bot: /codex"

  cat <<EOF

$(printf '\033[1;32m═══ PHASE 2 COMPLETE ═══\033[0m')

Manual steps left (they need you to paste something):

  1. Authenticate GitHub:   gh auth login
  2. Authenticate Claude:   claude auth login      # gives you URL + code
  3. Secrets outside git, from your machine (if a project needs them):
       scp <path>/.secrets.json $USER@<IP>:~/dev/<project>/.secrets.json
${CODEX_STEPS}
Choose which repos become persistent sessions (one per project):

     claude-repos pick

  They'll show up in the Claude app by name. To get in raw:
     ssh $USER@<IP> -t tmux -L claude-<project> attach -t claude-<project>

  Status / stop:
     systemctl --user status claude@<project>
     systemctl --user stop   claude@<project>

EOF
}

if [ "$(id -u)" -eq 0 ]; then phase_root; else phase_dev; fi
