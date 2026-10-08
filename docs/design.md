# Design notes

*English · [Español](design.es.md) · [← README](../README.md)*

The why behind pocket-agents: what each piece does, the failures that shaped it, and the trade-offs taken on purpose. The [README](../README.md) is the how-to.

## What it sets up

**Phase 1 (root)** — a `dev` user with root's SSH keys, root and password logins
disabled (it also removes the cloud-init override that re-enables them), ufw with only
port 22 open, fail2ban, 4 GB of swap with `swappiness=10`, journald capped at 500 MB,
Docker Engine with build-cache GC at 5 GB and log rotation, and `enable-linger` so user
services survive logout.

**Phase 2 (dev)** — [mise](https://mise.jdx.dev) with node LTS / go 1.23 / python 3.12 /
rust / uv, Claude Code in user space (no `sudo`), the tools in `bin/` installed into
`~/.local/bin`, the `claude@.service` template and a restrictive
`~/.claude/settings.json`. With `CODEX=1`, also OpenAI's Codex and its unit — off by
default, because it installs from its own self-updating channel and its setup can't
finish without two settings in a ChatGPT account that the script can't touch.

The script **doesn't clone any repo on its own**: the list starts empty and you choose.

## Re-authentication and monitoring

Unattended sessions have a failure you don't see coming: **the OAuth refresh token is
single-use**. When the access token expires, every session tries to refresh with its
own copy of the same grant; one wins and the rest get a rejection, on which Claude Code
deletes the stored credentials. The process does NOT die, so `Restart=on-failure` never
fires: the session stays alive and without Remote Control until someone notices.

`bin/` solves both halves of the problem — finding out, and fixing it without being
there. **Phase 2 installs everything**; this is only for updating by hand after a
`git pull`:

```bash
install -m755 bin/claude-* ~/.local/bin/
install -m644 systemd/*.service systemd/*.timer ~/.config/systemd/user/
install -Dm644 share/i18n.json ~/.local/share/claude-rc/i18n.json
```

**The bot reloads itself**, and not for convenience: installing left the new file in
place while the process kept the old one in memory, so a newly added button *didn't
exist* for it and the only clue was a spinner that did nothing. Now, at the end of each
loop, it compares the `mtime` and size of its own file and of `i18n.json` with the ones
it loaded; if they changed, it says so on Telegram and exits, and `Restart=always`
brings it back in ten seconds. It doesn't exit if what's on disk doesn't compile:
`install` writes *in place*, there's an instant with a half-written file, and a broken
version would mean a restart every ten seconds forever. **Units** still need
`systemctl --user daemon-reload`.

Messages are in **English by default**; `CLAUDE_RC_LANG=es` switches them to Spanish,
and the unit files already set it. Translations live in `share/i18n.json`, shared by
the four scripts: adding a language or fixing a string touches no code. If the file is
missing, the scripts keep working and messages come out as keys.

| | |
|---|---|
| `claude-rc-status` | Real state of each session: credentials on disk and `bridgeSessionId`, not the pane |
| `claude-login-bridge` | Runs the interactive `/login` over Telegram: sends the link, receives the code, types it |
| `claude-rc-bot` | Sole consumer of `getUpdates`; hands the code to the bridge through a file |
| `claude-rc-watchdog` | Link down, login about to expire, pending reboot and exposed ports |
| `claude-session` | Replaces the `ExecStart`: seeds workspace trust and resumes with `--continue` |
| `claude-repos` | Picks repos from GitHub and GitLab and turns them into sessions |
| `claude-docker-gc` | Daily disk sweep: build-cache ceiling, dangling layers, old containers |

**How to tell whether a session is connected.** Not from the pane: the `/rc` pill in
the status bar gets truncated in a narrow pane even when the bridge is alive, and it
shows up through auto-activation even when `--remote-control` isn't requested. The
reliable signal is `bridgeSessionId` in `~/.claude-<session>/sessions/<pid>.json`,
which Claude writes when it brings up the bridge. A blocking dialog is detected by the
**presence** of its text, never by the absence of something else.

The bridge and the bot need a Telegram bot of your own:

```bash
install -d -m700 ~/.config/claude-rc-telegram
cat > ~/.config/claude-rc-telegram/config <<'EOF'
TG_TOKEN=<the token @BotFather gives you>
TG_CHAT=<your numeric user id>
EOF
chmod 600 ~/.config/claude-rc-telegram/config
systemctl --user enable --now claude-rc-bot
```

```bash
claude-rc-bot --setup    # once: publishes the bot's menu and descriptions
```

From your phone: `/status`, `/login <session>`, `/new`, `/close <session>`, `/ports`,
`/backup`, `/disk`, `/reboot`, `/codex`, `/update`, and the same as buttons. Command
names are always English — they're identifiers, like `/status` and `/login` — and the
descriptions get translated; `/nueva` and `/cerrar` still work as aliases.

`/new` has three modes and disambiguates with buttons instead of syntax:

- `/new owner/repo` (with a slash) clones directly.
- `/new name` asks: **clone your repo**, **create a private repo** or **empty session**.
  If `~/dev/<name>` already exists without a session, the only button is *bring it up
  as is*.

The repos it creates are **always private**, with no flag to publish them: a repo made
public by accident can't be undone. And a remote is never deleted when undoing a
half-finished setup; it says the remote exists and that retrying picks it up.

After bringing a session up, the bot watches the pane and reports whether it reached
the prompt, got stuck on a dialog, or died. **Only the login is left to you**: workspace
trust is seeded by `claude-session`, but authenticating is still yours.

**⏸ Pause / ▶️ Resume**, one button per session. Each session takes 0.5–1 GB, and 8 GB
fits four comfortably: pausing is `stop` and not `disable --now`, so it closes and
deletes nothing — repo, config dir and conversation stay where they were — and the unit
starts with `--continue`, so resuming picks up at the same point. The message says how
much memory was freed, which is the reason to press it. A paused session shows ⏸ and
not ⛔ because what sets them apart is `systemctl is-active` saying `inactive`, and with
`Restart=always` that only happens if someone stopped it.

**`/backup` — work that exists only on this disk.** A session that commits on its own
produces the failure nobody sees coming. Measured here on 2026-09-13: `job-queue` with
21 unpushed commits from eight days earlier, and `budget-app` — a **live** session —
with a repo that had no remote at all. Nothing said so; the runbook said to check before
an `rm -rf`, which is exactly when it's already too late to remember. The bot checks once
a day and only speaks up if there's something, at two levels because they're two
problems: ⛔ has nowhere to go and a button won't fix that, ⚠️ has somewhere to go and
hasn't gone, and there the ⬆️ does the `push`.

It fires on what **waiting won't fix** — no remote, a branch that tracks nothing,
unpushed commits, stashes — with a 6 h grace period on the oldest, because a commit from
five minutes ago isn't abandoned work. Uncommitted files do **not** trigger it on their
own: that's a session working, and an alarm that goes off daily for normal things ends
up ignored. `git push` is still denied to Claude; you press the button, which is the
same deliberate decision made from your phone.

**`/reboot` — what rebooting would cost right now.** `unattended-upgrades` installs
kernel and libc patches but doesn't reboot, on purpose. The measured result: 24 days of
uptime with `libc6` and two kernels waiting. What holds a reboot back isn't risk, it's
not knowing what you'd lose — and you lose less than it seems, because files stay and
every session comes back with `--continue`. The only thing interrupted is whatever an
agent has **half done**, and that can be read from the pane's status bar. Rebooting
isn't a user operation: if polkit doesn't grant it to the bot, it says so and gives you
the command.

With a trap that cost a round of debugging: **a tmux socket existing doesn't mean
anyone is there**. tmux leaves the file behind when the server dies, so an `exists()`
painted paused sessions as alive and the Resume button never appeared. What's asked now
is whether anyone *answers*, with a `connect()` to the unix socket: with no server it
gives `ECONNREFUSED` instantly, and costs microseconds.

The command menu is published in `chat` scope with your id, so a stranger who opens the
bot doesn't even see the list. The list is **static on purpose**: commands are verbs
and sessions go in the inline buttons. Putting them in the menu would mean calling the
API again on every add and remove, and clients cache it anyway. Besides, a command name
only allows lowercase letters, digits and `_`, so `my-repo` and `my.repo` would collide.

The API **doesn't support argument autocompletion**: choosing `/login` from the menu
sends it bare. That's why that path answers with the session buttons.

**Why a command took 47 seconds.** The `getUpdates` `timeout` and the socket timeout
are two different things, and confusing them cost that much: Telegram holds the
response for as many seconds as you ask, but if the connection dies silently — about
**80 times a day**, measured in the journal — the client doesn't notice until *its*
deadline expires, and meanwhile the button you pressed sits on the server with nobody
picking it up. Now the socket timeout sits just above the long poll, with TCP keepalive
probes so a dead peer is detected in ~11 s instead of 25.

And the bot is single-threaded on purpose, so the second tap in a batch waited for the
first one's work to finish — Pause and Resume take seconds — and by then Telegram had
already expired the tap: a button spinning forever. The **whole batch** is answered as
soon as it's picked up, and the same button repeated counts as one intention, not three.
Answering a tap gets its own 6 s socket timeout and one retry, because it's only worth
anything within the ~15 s a tap lives: one answer that took 36.5 s to get out, under the
general 45 s timeout, arrived to an already-expired tap. And the long poll's network
blips — about a hundred a day, each one recovered on the next loop — are counted rather
than logged one by one: a line when three fail in a row, another when it comes back, and
a daily summary.

```bash
systemctl --user enable --now claude-rc-watchdog.timer
```

The watchdog does two things, and the preventive one is what matters: **it warns on
Telegram when the login has `WARN_DAYS` or fewer left** (3 by default), once a day per
session. That's the only thing that attacks the cause — the incident that started all
this would have been avoided by renewing in time. The rest is reaction: it detects a
dropped link, warns at most once an hour, and restarts after three failed checks.

The `.service` already sets `MAX_RESTARTS=3` and `WARN_DAYS=3`. That cap isn't paranoia:
detection used to search for the text across the whole pane, and since these sessions
talk about this very system, two **healthy** sessions were flagged as down. Without a
limit it would have been a restart loop killing a conversation every three minutes.
Detection now only looks at the status bar, but the cap stays.

`--dry-run` says what it would do without restarting or sending anything.

Environment variables for all scripts are in English: `SESSIONS`, `MAX_RESTARTS`,
`WARN_DAYS`, `FAILURES_BEFORE_RESTART`, `ATTEMPTS`, `URL_TIMEOUT`, `CODE_TIMEOUT`.
`SESSIONS` is only a **fallback** for when there are no instances enabled in systemd;
it can't be used to narrow things down, because systemd is the source of truth.

## The other agent: Codex

Codex ships **its own remote control**, so it isn't wrapped like Claude. And its model
is the opposite one: **one daemon with N threads**, not N processes with a shared
config. All of `claude@<project>` — one service per repo, one tmux server per service,
one `CLAUDE_CONFIG_DIR` per session — was born from the `.claude.json` race, and Codex
doesn't have it. Here there's **one** unit, not seven.

```bash
CODEX=1 sudo -E bash setup.sh     # installs the standalone build and the unit
```

**The two steps no error message tells you about**, which cost an afternoon:

1. In ChatGPT settings, **enable device-code authorization for Codex**. Without it,
   `codex login --device-auth` just sits there waiting.
2. **MFA enabled on the account.** Enrollment fails with
   `HTTP 403 · {"detail":"Multi-factor authentication required"}`, and you only see that
   if you look at the output of `pair`.

Then, **in this order**:

```bash
codex login --device-auth                        # URL + code
systemctl --user enable --now codex-app-server   # AFTER logging in
codex remote-control pair                        # code valid ~10 min
```

The service goes after the login because **the app-server doesn't re-read
`auth.json`**: started without credentials it says `the connection is errored`, which
sounds like a network problem and means "you logged in afterwards". The bot restarts it
by itself when it detects the login has just completed.

Pairing is **repeatable**: each call gives a new code valid for about ten minutes, while
the machine's `environmentId` doesn't change. The code is a handshake, not state you
keep — ask for it as many times as needed.

It has to be the **standalone** build, not the npm package: `codex app-server daemon`
aborts with `managed standalone Codex install not found`. Having both is worse than
having neither, because whichever comes first in `PATH` wins — and that isn't the same
in your shell as in the units. The script removes the npm one if it finds it.

**The unit runs the real app-server in the foreground**, not `codex app-server daemon
start`: that one launches the process and exits, so systemd would find the cgroup empty
and consider the service finished — the same failure as the tmux socket, which cost two
days here. The price is the auto-updater the wrapper brings; in exchange, the version is
changed by hand, same as Claude's.

And `/codex` in the bot checks **three things separately** — service, app-server and
login — because they're fixed in different ways, with Stop, Start, Restart, Login and
Pair buttons; only what can be done right now shows up. Login over Telegram comes almost
for free: `--device-auth` is one-way, so the bot only reads two lines, with none of the
file-based bridge Claude needs.

**Updating is manual for both**, also on purpose: `/update` compares what's installed
with what's available and asks. The bot restarts Codex itself — it's a service with no
conversation to lose — but each Claude session keeps the version it started with and
only picks up the new one when restarted, which interrupts whatever it has half done.
That decision is still yours.

## Previews from your phone (optional)

`cloudflare/tunnel-setup.sh` exposes the development servers over HTTPS **without
opening any inbound port**: `cloudflared` connects outward, just like the Claude
sessions.

```bash
cloudflared tunnel login     # once, pick the zone in the browser
./tunnel-setup.sh            # creates the tunnel, the DNS routes and the service
```

The zone comes from `ZONE` in `config.env` at the repo root; if it isn't there, the
script asks for it, since this one runs by hand on a terminal.

Each development port ends up at `p<port>-dev.<zone>`: start an `npm run dev` on 3000
and open it at `https://p3000-dev.<zone>` from wherever you are. The mapping is per port,
not per project, so anything you start already has a URL without touching the tunnel
config.

> **These URLs are public** while the server is up. Put Cloudflare Access in front of
> them (Zero Trust → Access → Applications, domain `p*-dev.<zone>`, an `Emails` policy
> with your address). Without it, the only barrier is nobody guessing the subdomain.

## Customizing the repos

The usual path is `claude-repos pick` after phase 2. For automation, `REPOS` in
`config.env` takes identifiers with a forge:

```bash
REPOS="myorg/one gitlab:mygroup/two"
```

No prefix means GitHub. The list is stored in `~/.config/claude-sessions/repos.conf`,
which is the source of truth: a rerun clones and brings up whatever is missing, without
asking again.

## Network and containers

**ufw isn't enough with Docker.** Docker writes its own rules and they're evaluated
*before* ufw's, so a careless `-p 8080:80` opens the port to the Internet even though
ufw denies it. Phase 1 adds three rules to `DOCKER-USER` (through
`/etc/ufw/after.rules`, so they survive reboots and Docker upgrades) that cut all
inbound traffic from the public interface to any container, and block the provider's
metadata service.

The policy can be absolute because the public path is the tunnel, which goes outward and
comes in through loopback: **no container needs to publish on `0.0.0.0`**. On top of
that, `daemon.json` sets `"ip": "127.0.0.1"`, so a `-p` without an address is born bound
to loopback.

The watchdog warns on Telegram if something starts listening outside loopback and isn't
on the allowlist (`tcp:22`), telling apart a Docker publish from a native process,
because the response is different.
A native process only triggers it after listening for 15 minutes straight
(`CLAUDE_RC_NET_GRACE`, in seconds): ufw already blocks it, and test servers that grab
a fresh port per run and die when it ends were 45 of 47 alerts in eleven days. A Docker
publish alerts right away, because Docker bypasses ufw.

**The warning carries a 🔇 Silence button**, and pressing it turns the message itself
into the confirmation and offers the reverse 🔊: a mistake is undone without leaving the
message. Before, it meant remembering a file path and logging in over SSH, which on a
development machine — a Vite preview, a binary in `target/debug` — doesn't scale, and
the result was seven warnings about the same port in one afternoon.

`/ports` is the inventory of what's listening, in three groups because they're three
situations and only one asks you to do something:

```
🔴 tcp:50051 — booking-engine · 9 d               ← will warn today, with its 🔇
🟢 tcp:22 — open 🔒                               ← silenced by hand, with the 🔊
· tcp:5173 — node vite dev --force · 4 h          ← 127.0.0.1 only: neither warns nor can
```

Next to the port, who serves it and how long it's been up. The 🔒 comes from
`CLAUDE_RC_NET_ALLOW` in the unit and not from the file, so the bot can't remove it.
Both `ss` **and** `docker ps` are needed even though it looks redundant: with the
userland proxy a published port does show up in `ss`, but as `docker-proxy` running as
root — a socket with no owner — and without the proxy the publish is pure DNAT and
there's nothing to see in `ss`. Where another user's process can't be seen, the owner is
left out rather than made up.

It also warns when a reboot is pending: `unattended-upgrades` installs kernel patches but
doesn't reboot on purpose — it would take the sessions down — so without that warning
the machine runs indefinitely on an old kernel.

Runtime versions can be pinned from outside. `NODE_V` is **24** — the current LTS — and
it's a fixed major on purpose: patches keep arriving within that line, but you decide
when to jump to the next LTS. With `lts`, a future rerun would switch majors without
warning, and that breaks the promise that rerunning breaks nothing.

```bash
NODE_V=lts      # in config.env: follow the current LTS
GO_V=1.24
```

**This only pins the global version.** A project that needs a different one declares it
in its own repo with `.node-version`, `.nvmrc` or `.mise.toml`, and mise honors it when
entering the directory. With a trap worth knowing: if the requested version **isn't
installed**, mise neither fails nor installs it — it silently falls back to the global
one. Verified on this server. So when cloning a repo with its own pin, the first time:

```bash
cd ~/dev/<repo> && mise install
```

## Disk budget

Docker is what fills the disk, and not where it seems. `claude-docker-gc` sweeps daily
(a timer with `RandomizedDelaySec=1h`): **a 4 GB ceiling on the build cache**, dangling
layers, containers stopped for more than a week, and orphaned networks.

A ceiling and not an age, and this cost one sweep that reclaimed nothing: BuildKit's
`until` filter looks at *last use*, not creation time, so a layer from three weeks ago
that a build touched yesterday counts as new — with `until=336h` the first sweep
reclaimed **0 B out of 8.3 GB**. With the ceiling, BuildKit evicts in order of last use
and keeps the working set.

What it does **not** do, and not by oversight:

- **Volumes, never.** An idle volume is what's left between a `compose down` and the
  next `up` — someone's database. `--volumes` doesn't appear in the script.
- **Unused tagged images.** They're usually the biggest chunk (measured: 7.45 GB, 85 %
  of image space), but they only go with `-a`, and with them go `php:8.4-cli` or
  `postgres:17-alpine`, which the next build downloads again.

A machine can't tell "an experiment from two weeks ago" from "tomorrow's database", so
those two are decided by a person — and **`/disk` is where they're decided**. An image
goes with one tap, because it comes back with a pull or a build; a volume **asks first**
and shows the name, because it doesn't come back. Before, this only appeared if the disk
went over 75 %, and it had sat at 56 % for months: that warning had never gone off.

Buttons **never repeat text**, and that's a fix, not a detail: when their tags were
stripped to make them fit, `php:8.4-cli` and `php:8.3-cli` both ended up as `🗑 php` —
two identical buttons with different effects, which is exactly how you delete what you
didn't mean to.

**Docker wasn't what filled the disk.** In October it reached 93-98 % three days in a
row, and the daily alert fired every time — with a percentage and a list of images. What
had to be cleaned by hand was **33.8 GB of Rust `target/` directories** and **11 GB of npm
cache**, which `/disk` didn't even show. So it now has two more sections:

- 🦀 **Build artefacts**: every `target/` under `~/dev`, found by the `CACHEDIR.TAG` cargo
  writes in it (a folder that's merely called `target` is left alone), with its size and
  when it was last built. A button per project, up to three, cleans it — unless a
  `cargo` or `rustc` is running inside that project, in which case the line says so and
  there's no button.
- 📦 **Package caches**: npm, pnpm, yarn, Go, cargo, uv and pip in one line and one
  button. Go's module cache is read-only on purpose, so it goes through
  `go clean -modcache`; the npx cache is skipped while something (an MCP server, say)
  runs from it. Playwright's browsers are not a cache — tests need them — and stay.

Both are regenerable, so they go in one tap, like an image. **"All unused images"**
asks first: one at a time is too slow when there are sixteen, and all at once means
every project's next build fetches them again. Nothing here is on a timer: the daily
sweep still only does what a machine can decide alone. What it does now is ask the bot
(`claude-rc-bot --reclaimable`) for the three biggest things that can go, and put them
in the alert.

Cleanups run **in the background**. The bot is single-threaded, and the first cache
cleanup — Go's module cache alone is thousands of files — kept it deaf for 63 seconds:
no tap and no command got an answer, and the button was pressed again because nothing
seemed to happen. Now the bot answers at once, keeps serving everything else, reports
when the job is done, ignores a second tap on a job already running, and doesn't
reload itself in the middle of one.

`/disk` itself takes 3 to 16 seconds, and for that long nothing showed. It now answers
at once with "Measuring the disk…" and ticks each step (disk space, Docker, artefacts
and caches) as it finishes; that same message becomes the report. A result — an image
deleted, a cache cleaned — carries only **🗄 Back to Disk**, which turns that message
back into the report: results used to replace the report with the whole session menu.

The pending steps carry an animated ⌛ and the finished ones an animated ✅. Telegram
only lets a bot use animated custom emoji while its owner has Telegram Premium (or the
bot owns a Fragment username); if it refuses them, `api()` resends the same message
with the plain emoji they wrap, the same way it resends as plain text when the HTML is
rejected. To pick another one, send it to the bot: the journal logs the custom emoji
ids of incoming messages, never their text.

Telegram caps a message at 4,096 characters and cuts the end, and the end of `/disk` is
the explanation. Each section shows six lines at most, then "…and N more": a test
builds the worst case — fifty long-path projects, forty images, thirty volumes — and
checks it fits (about 2,300 characters) and that no button's data passes 64 bytes.

## Principles

- **No containers.** Containerizing Claude means mounting the Docker socket so it can use
  compose and testcontainers, and that amounts to giving it root on the host: the
  isolation that justified the container disappears. A dedicated user + restrictive
  permissions is simpler and no less secure.
- **Separate from production.** This VPS serves nothing public. An experiment can't take
  a site down.
- **Everything in user space.** Claude is installed under `~/.local`, never with
  `sudo npm -g`.
- **Git as the meeting point.** The VPS and your laptop are independent machines; they
  sync through git, not rsync.
- **Nothing on the allowlist that runs arbitrary code.** `python3`, `make`, `npm run`,
  `uv run`, `mise` and `docker compose` are left out on purpose. With them in, denying
  `sudo` was decorative: `python3 -c 'os.system("sudo …")'` doesn't start with `sudo`,
  and with `NOPASSWD` that's root without a single prompt. And with
  `--permission-mode acceptEdits` the agent can *write* the Makefile first and run it
  afterwards. The realistic trigger isn't the agent misbehaving, it's a prompt
  injection: these sessions read web pages, issues and dependency READMEs. Those
  commands now ask, and that's what the remote control on your phone is for.
- **Detect by presence, not by absence.** A signal not showing up proves nothing: a
  narrow pane truncates it and a subagent pushes it out of the window. Both false
  positives this system has produced came from inferring one state from the absence of
  another.
