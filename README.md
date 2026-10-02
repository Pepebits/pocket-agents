<p align="center"><img src="docs/banner.png" alt="pocket-agents" width="720"></p>

<p align="center"><em>English · <a href="README.es.md">Español</a></em></p>

**pocket-agents** turns a VPS into a home for your coding agents: one persistent
Claude Code session per project, always on, that you check and steer from your phone —
with your computer switched off.

- 🧠 **One session per project**, supervised by systemd, that resumes where it left off
- 📱 **A Telegram bot** to see status, log in, add, pause or close sessions
- 🔑 **Login over Telegram**: the bot sends you the link, you send back the code
- 🩺 **A watchdog** that reconnects dropped sessions and warns before a login expires
- 🧹 **Disk and port housekeeping**: Docker sweeps, exposed-port alerts, unpushed-work checks
- 🌐 **Optional HTTPS previews** of your dev servers through a Cloudflare tunnel
- 🤖 **Optional Codex**, OpenAI's agent, with its own unit

👉 **[See how it fits together](https://pepebits.github.io/pocket-agents/overview.html)** — a one-page visual tour with diagrams.

## 🚀 Getting started

You need a fresh **Ubuntu 24.04** VPS you can reach as `root` with your SSH key. 8 GB of
RAM fits about four sessions comfortably.

**1. 📥 Clone this repo** on your own machine.

```bash
git clone https://github.com/Pepebits/pocket-agents.git
cd pocket-agents
```

**2. ⚙️ Create your settings.** Every line is optional; the template explains each one.

```bash
cp config.env.example config.env
```

**3. 🔒 Phase 1, as root** — creates the `dev` user, firewall, swap and Docker.

```bash
cat config.env setup.sh | ssh root@<IP> 'bash -s'
```

**4. 🧰 Phase 2, as dev** — toolchains, Claude Code and the pocket-agents tools.

```bash
cat config.env setup.sh | ssh dev@<IP> 'bash -s'
```

Both phases are safe to run again: they skip what's already done.

**5. 🔑 Sign in on the server.** These two ask you to paste a code.

```bash
ssh dev@<IP>
gh auth login
claude auth login
```

**6. 📂 Choose your projects.** Each one you pick becomes a session in the Claude app.

```bash
claude-repos pick
```

`claude-repos list` shows what's set up, `claude-repos add gitlab:group/repo` adds one
by name, and `tmux -L claude-<project> attach -t claude-<project>` drops you into a
session's terminal.

**7. 🤖 Connect Telegram.** Create a bot with [@BotFather](https://t.me/BotFather), get
your numeric user id (for example from [@userinfobot](https://t.me/userinfobot)), then
on the server:

```bash
install -d -m700 ~/.config/claude-rc-telegram
cat > ~/.config/claude-rc-telegram/config <<'EOF'
TG_TOKEN=<the token @BotFather gives you>
TG_CHAT=<your numeric user id>
EOF
chmod 600 ~/.config/claude-rc-telegram/config

systemctl --user enable --now claude-rc-bot              # the bot
claude-rc-bot --setup                                    # once: its menu and description
systemctl --user enable --now claude-rc-watchdog.timer   # the watchdog
```

✅ **Done.** Open your bot in Telegram and send `/status`.

**Optional extras:**

- 🌐 **Previews** — reach a dev server on port 3000 at `https://p3000-dev.<your-zone>`:
  run `cloudflared tunnel login`, then `cloudflare/tunnel-setup.sh`, which asks for your
  Cloudflare zone if `config.env` doesn't have it. Put Cloudflare Access in front: these
  URLs are public while the server runs.
- 🤖 **Codex** — set `CODEX=1` in `config.env` before phase 2. Its login needs two
  ChatGPT settings first; see [design notes → Codex](docs/design.md#the-other-agent-codex).

## 📱 From your phone

| Command | What it does |
|---|---|
| `/status` | 🟢 Every session at a glance, with buttons to log in, pause or resume |
| `/login <session>` | 🔑 Sends you the login link; reply with the code |
| `/new` | ➕ Clone a repo, create a private one, or start an empty session |
| `/close <session>` | ➖ Stop a session, keeping or deleting its folder |
| `/ports` | 🔌 What's listening, and what's exposed to the internet |
| `/backup` | 💾 Work that only exists on this disk, with a button to push it |
| `/disk` | 🧹 What fills the disk, and buttons to free it |
| `/reboot` | 🔄 What a reboot would interrupt right now |
| `/update` | ⬆️ New Claude Code or Codex versions, and which sessions run old ones |
| `/codex` | 🤖 Codex service, app-server and login |

The bot speaks English or Spanish: the units ship with `CLAUDE_RC_LANG=es`; set it to
`en` for English.

## 🛠️ What's on the server

| Tool | Job |
|---|---|
| `claude@<project>` | 🧠 One systemd service per session, resuming with `--continue` |
| `claude-rc-bot` | 📱 The Telegram bot |
| `claude-login-bridge` | 🔑 Carries the interactive `/login` over Telegram |
| `claude-rc-watchdog` | 🩺 Dropped links, expiring logins, pending reboots, exposed ports |
| `claude-rc-status` | 📋 The real state of each session |
| `claude-session` | ▶️ Starts a session with workspace trust already seeded |
| `claude-repos` | 📂 Picks GitHub and GitLab repos and turns them into sessions |
| `claude-docker-gc` | 🧹 Daily Docker sweep, enabled by phase 2 |

## ⚙️ Configuration

`config.env` goes in front of `setup.sh` because the script arrives through `bash -s`:
it can't ask you anything, and ssh doesn't carry your local variables to the server.

| Variable | Default | For |
|---|---|---|
| `REPOS` | empty | Projects to set up in phase 2, e.g. `"myorg/api gitlab:team/web"` |
| `NODE_V` / `GO_V` / `PY_V` | `24` / `1.23` / `3.12` | Runtime versions; `NODE_V=lts` follows the current LTS |
| `CODEX` | `0` | `1` installs Codex and its unit |
| `SELF_REPO` | this repo | Where phase 2 clones the tools from, if you use a fork |
| `ZONE` | asked | Cloudflare zone for previews |
| `LABEL` / `TUNNEL` / `PORTS` | `dev` / `dev-vps` / common dev ports | Preview host names and ports |

🔄 **Updating** the tools after a `git pull` on the server:

```bash
install -m755 bin/claude-* ~/.local/bin/
install -m644 systemd/*.service systemd/*.timer ~/.config/systemd/user/
install -Dm644 share/i18n.json ~/.local/share/claude-rc/i18n.json
systemctl --user daemon-reload     # the bot reloads itself; units need this
```

## 📚 Learn more

- 🗺️ **[Visual overview](https://pepebits.github.io/pocket-agents/overview.html)** — topology, supervision, the login flow
- 🧭 **[Design notes](docs/design.md)** — why each piece works the way it does, and the failures behind it
- 📒 **[Runbook](docs/runbook.md)** — day-to-day operation
- 🔧 **[Troubleshooting](docs/troubleshooting.md)** — failures already diagnosed

## 🧪 Tests

```bash
./tests/run          # hermetic: a fake Telegram and a fake HOME
./tests/run --live   # plus diagnostics that read this machine's state
```

No dependencies beyond python3 and `git`. See [tests/README.md](tests/README.md).

## 🧷 Principles

- 🐳 **No containers for the agents** — mounting the Docker socket would hand them root anyway
- 🏝️ **Separate from production** — this server serves nothing public
- 👤 **Everything in user space** — no `sudo npm -g`
- 🔀 **Git is the meeting point** between the server and your laptop
- 🛑 **Nothing on the allowlist that runs arbitrary code** — those commands ask, and you answer from your phone

The reasoning behind each one is in the [design notes](docs/design.md#principles).
