# Runbook

## Adding a new project

From your phone, `/new` in the bot. With a slash it clones straight away; without one it
asks with buttons whether you want to clone, create a private repo or an empty session.

From SSH:

```bash
claude-repos add <owner>/<repo>        # or gitlab:group/repo
claude-repos pick                      # choose from a list of your repos
```

**You don't need to prepare the config dir by hand.** `claude-session` seeds it at startup:
it creates `~/.claude-<repo>/`, copies `~/.claude.json` as a seed, links `settings.json` to the
global one and —what really matters— writes
`projects["<dir>"].hasTrustDialogAccepted = true`. Without that the session stays stuck at
*"Quick safety check… Yes, I trust this folder"* and never reaches the prompt.

The **credentials are deliberately not seeded**: copying the global token into each session
hands the same refresh token to several of them, and OAuth ones are single-use — that
race is what left three sessions without credentials. Each session does its own `/login`, and the
bridge restarts the service when the credential is the first one, because Remote Control
requires the account at startup and `/login` doesn't bring it up on its own.

The service name **must** match the directory name in `~/dev/`: the unit uses
`%i` both for `WorkingDirectory` and for the Remote Control session name.
With two forges, two repos can produce the same basename; `claude-repos` resolves it with a
suffix (`-gh`/`-gl`) and writes it to `repos.conf` so it stays stable.

## Secrets

Never through git. Manual copy and restrictive permissions:

```bash
scp ~/path/.secrets.json dev@<IP>:~/dev/<repo>/.secrets.json
ssh dev@<IP> 'chmod 600 ~/dev/<repo>/.secrets.json'
```

`~/.claude/settings.json` denies reading `.env`, `.secrets.json`, `*.pem`, `*.key`
and `id_rsa`/`id_ed25519`, so Claude can't leak them into a commit or a log.

## Removing a project

```bash
systemctl --user disable --now claude@<project>
tmux -L claude-<project> kill-server
rm -rf ~/dev/<project> ~/.claude-<project>
```

Check first that there's no unpushed work left: `git status --porcelain`,
`git log @{u}..` and `git stash list`.

## Day-to-day operation

Each session has its own `CLAUDE_CONFIG_DIR`, so you can restart them all at once
without them overwriting each other's configuration (see failure 8).

```bash
systemctl --user status  claude@<project>
systemctl --user restart claude@<project>
systemctl --user stop    claude@<project>
systemctl --user list-units 'claude@*'
```

Get into the session exactly as Claude sees it:

```bash
ssh dev@<IP> -t tmux -L claude-<project> attach -t claude-<project>
```

`Ctrl-b d` to leave without killing it.

### A session without Remote Control

`claude-rc-status` marks it 🟠 *Remote Control off*. It's almost always a session that
started without credentials: the bridge requires the account at launch and `/login` doesn't
bring it up afterwards. Restarting it fixes it, and the watchdog does that on its own if it's armed.

```bash
systemctl --user restart claude@<project>
# check the good signal, not the pane:
python3 -c 'import glob,json;print([json.load(open(f)).get("bridgeSessionId") for f in glob.glob("'"$HOME"'/.claude-<project>/sessions/*.json")])'
```

If instead it shows ⚪ *stuck on a dialog*, restarting does **not** fix it: go in through tmux and
answer it. And don't send it Enter blindly — the default option is *No, exit*.

### Open-port alerts

The watchdog alerts once a day for each port listening outside loopback.
When the port is yours and you know what it does —a Vite preview, a binary in
`target/debug`— **the alert itself carries a 🔇 Mute button**. It's undone in the
same message, with the 🔊 that appears once you mute it.

`/ports` is the full inventory of what's listening. Three groups, because they're
three different situations and only one asks you to do something:

```
🔌 Ports

Alerting daily
🔴 tcp:50051 — booking-engine · 9 d

Muted
🟢 tcp:22 — open 🔒
⚪ udp:5353 — not listening · muted 3 d ago

Local only (11)
· tcp:5001 — 🐳 map-tiles · 2 weeks
· tcp:5173 — node vite dev --force · 4 h
· tcp:9464 — booking-engine · 9 d
· tcp:8092

[🔇 tcp:50051] [🔊 udp:5353]
```

🔴 listens outside loopback and isn't muted: it will alert today, and carries its button
to mute it without waiting for the alert. 🟢/⚪ are the ones muted by hand, with the
reverse button. The `·` ones only listen on `127.0.0.1`: they don't alert and can't, but
they're half of what runs on the machine and not seeing them left the command
half-done. They carry no button because there's nothing to mute.

After the port, who serves it and how long it's been up. A 🐳 is a
container: that comes from `docker ps`, and both queries are needed even though they
look redundant — with the userland proxy the port does show up
in `ss`, but as `docker-proxy` running as root, i.e. a socket with no
owner; without the proxy the publication is pure DNAT and there's nothing in `ss`. And where
`ss` can't see someone else's process (`tcp:8092`, `tcp:53`) the owner is left out
rather than made up. Only the basename of each path, which is what makes
`node vite dev --force` readable in 44 characters.

The 🔒 marks ports that come from `CLAUDE_RC_NET_ALLOW` in the unit, not from the
file: the bot can't remove them. Both units repeat the literal and
**have to say the same thing**.

In writing, if that's quicker than finding the button:

```bash
/ports tcp:4173         # mute
/ports -tcp:4173        # unmute
echo tcp:4173 >> ~/.config/claude-rc/net-allow    # by hand, still works
```

The file is the same as always with the same format —one port per line,
`proto:port`, hash for comments— and it's read on every pass, so there's nothing
to reload. The only thing the bot adds is a `# since <epoch>` in the
comment, which the watchdog already ignored and here is used to say how long it's been
muted. Unmuting also deletes the daily-alert mark, so if
the port is still open you hear about it again on the next pass (~70 s), not
tomorrow.

The alert is informational: what stops the traffic is ufw's default *deny*,
and for containers the `DOCKER-USER` rule. Check from outside with
`nc -vz -w3 <IP> <port>` before you worry.

## The bot reloads itself

Installing a new version leaves the file in place, but the process carries on
with the old one in memory: a freshly added button **doesn't exist** for it, and the
only clue was a spinner that did nothing. It happened three times.

Now at the end of every pass the bot compares the `mtime` and size of its
own file and of `i18n.json` with the ones it loaded. If they changed, it says so on
Telegram and exits; `Restart=always` brings it back in `RestartSec=10` with the
new code. The menus are on disk, so the one that starts readopts them.

```bash
install -m755 bin/claude-* ~/.local/bin/                               # and that's it
install -m644 share/i18n.json ~/.local/share/claude-rc/i18n.json
```

It doesn't exit if what's on disk doesn't compile: with the old version in memory the bot
keeps working, and a file that doesn't load would mean a restart every ten
seconds forever. It complains once per version in the journal and carries on.

What does **not** reload on its own are the **units**. That's still on you:

```bash
systemctl --user daemon-reload
```

And if a button gives you *"I do not know this button"*, this is exactly why: the message
was drawn by a newer version than the one running.

## Rebooting the machine

`unattended-upgrades` installs kernel and libc patches but **doesn't
reboot**, on purpose: it would take the sessions with it. The measured result is a
machine with 24 days of uptime and four packages waiting. What holds back the
reboot isn't the risk, it's not knowing what gets lost.

`/reboot` tells you before asking:

```
🔁 Reboot the machine

📦 Waiting on a reboot: libc6 linux-image-6.8.0-139-generic …
⏱ Up for 24 d.

⚠️ Working right now: travel. A reboot interrupts whatever they have in flight.
💾 Unbacked work in job-queue, budget-app.

[🔁 Reboot now] [🔁 Re-check]
```

Less is lost than it seems: the files don't go anywhere, the instances stay
enabled and each session comes back with `--continue`. The only thing interrupted is
whatever an agent was doing **at that moment**, and you see that in the
pane's bar (`esc to interrupt` while it's working).

Rebooting the machine **isn't a user operation**. If polkit doesn't grant it to the
bot, it says so and gives you the command instead of failing silently:

```bash
sudo systemctl reboot
```

And the login-expiry alert now carries its own **🔑 Renew \<session\>**,
just like the ports' 🔇: the alert brings the action, it doesn't send you hunting for
the menu.

## The other agent: Codex

Codex comes with **its own remote control**, so it isn't wrapped like Claude. And its
model is the opposite: **one daemon with N threads**, not N processes with a shared
config. All the `claude@<project>` machinery —one service per repo, one
tmux server per service, one `CLAUDE_CONFIG_DIR` per session— was born from the
`.claude.json` race, and Codex doesn't have it. Here there's only **one** unit.

`/codex` shows it and fixes it:

```
🧠 Codex

🟢 Service up · app-server 0.154.0
🟢 The app-server answers on its control socket.
🟢 Logged in.

[⏸ Stop] [🔄 Restart] [🔗 Pair]
```

The three lines are checked separately on purpose: "not answering" and "not logged in"
are fixed in different ways, and a report that only says the first one sends you
off to restart a service that starts fine and falls over again.

The buttons change with the state, and only what can be done right now shows up:
offering **Stop** on a dead service, or **Pair** without a login, is
promising something that will fail. Stopped shows ⏸ and not 🔴, same criterion as with the
sessions: with `Restart=always`, `inactive` only happens if someone stopped it. It's
`stop` and not `disable`, so a machine reboot brings it back.

### Pairing, as many times as needed

```bash
codex remote-control pair --json
{"pairingCode":"0265823819…","manualPairingCode":"NVHP-3B8C",
 "environmentId":"env_e_6aa71b58fa38832a8d95146d8c25c551","expiresAt":1789338395}
```

The `environmentId` **doesn't change** between calls: it's this
machine's identity. What changes is the `manualPairingCode`, and it lasts about **ten minutes**.
In other words the code is a handshake, not state you keep — ask for it
as often as you like, it doesn't invalidate anything.

### What the bot can't do, and why that's fine

`/reboot` shows what a reboot costs, but **the button only appears if polkit
grants it**. Here it doesn't:

```bash
$ pkcheck --action-id org.freedesktop.login1.reboot --process $$
Authorization requires authentication and -u wasn't passed.
```

Rebooting isn't a user operation, and on a machine without a graphical environment
polkit asks for a password — which a bot doesn't have. So the button would never have
worked, and offering it would make you think the machine is broken. It
asks first and shows the command instead.

The same goes for `sudo` and `systemctl`, which `~/.claude/settings.json` denies to
Claude: that's not an obstacle to get around, it's what makes it defensible to leave an
agent running on a machine with access to your repos. Installing packages and
rebooting stay on your side:

```bash
sudo apt install bubblewrap      # Codex asks for it; without it it uses the bundled one
sudo systemctl reboot
```

`bubblewrap` is already in the phase 1 list, so a fresh install
brings it; this is only for machines that were set up earlier.

### Setup, with the three steps nobody finds twice

```bash
curl -fsSL https://chatgpt.com/codex/install.sh | sh   # 1
codex login --device-auth                              # 4
systemctl --user enable --now codex-app-server         # 5
codex remote-control pair                              # 6
```

Steps 2 and 3 are missing, and **no error message mentions them**:

2. In the ChatGPT settings, **enable device code authorization for
   Codex**. Without this the login just sits waiting, and that's it.
3. **MFA enabled on the account.** Enrollment fails with
   `HTTP 403 · {"detail":"Multi-factor authentication required"}`, and you only see it
   if you look at the output of `pair`.

Step 1 has to be the **standalone** one: the npm `codex` can't bring up
the daemon (`managed standalone Codex install not found`). If you have both
installed, whichever comes first in the `PATH` wins, and that's not the same in your shell
as in the units — remove the npm one with `npm rm -g @openai/codex`.

And step 5 goes **after** 4, not before: the app-server **doesn't re-read
`auth.json`**. Started without credentials it says `the connection is errored`, which
sounds like the network and actually means "you logged in afterwards". That's why the bot restarts the service
on its own when it detects that the login has just completed.

### Why the unit runs the app-server and not `daemon start`

```
ExecStart=…/codex app-server --remote-control --listen unix://
```

`codex app-server daemon start` launches the process and **exits**, so systemd would
find the cgroup empty and consider the service finished — the same failure
as the tmux socket that cost two days in this repo. With the real process
in front, `Restart=always` means something.

The price is the auto-updater the wrapper brings: here the version is
changed by hand, like Claude's. On a machine where "relaunching breaks nothing"
is a promise, a silent update in the early hours isn't a feature.

Side effect: `codex remote-control start` answers *"app server is running
but is not managed by codex app-server daemon"*. That's correct — under systemd, the
`start` is `systemctl`. `pair` still works, which is what gets used.

### The Telegram login comes almost for free

Claude's needs a whole bridge: it sends the URL, **waits for the code to come
back**, types it into the pane with `send-keys`. Codex's is one-way —
`login --device-auth` prints the URL and code and keeps polling on its
own—, so the bot only has to read two lines from it.

It runs in a detached process rather than blocking, because this waits for **a person**:
the CLI polls for up to fifteen minutes and the bot is single-threaded.

## Updating the agents

Neither of them updates itself, and in both cases that's deliberate: Claude
goes through npm, and Codex had its auto-updater removed when it was put under systemd
(the `daemon start` wrapper brought it). On a machine where "relaunching breaks
nothing" is a promise, a silent update in the early hours isn't a
feature — but neither is a version from four months ago, and without `/update` nobody
noticed.

```
🆙 Versions

🟢 Claude Code 2.1.270 — up to date
🟡 Codex 0.154.0 → 0.155.0

[⬆️ Codex]
```

It's only checked **on demand**: both questions go out to the network and the bot is
single-threaded. Checking them on every pass would cost latency to everything else to
answer something that changes once a week. If the network fails, it shows ⚪ and says so
— knowing that you don't know is worth more than a false green.

By hand:

```bash
npm update -g @anthropic-ai/claude-code     # Claude
codex update                                # Codex (has no --check)
```

**The two behave differently afterwards, and the bot reflects that.** Codex is *one*
service with no conversation to lose, and `current` is a link —the live process
keeps the old binary—, so the bot restarts it on its own. Claude doesn't:
each session is its own process and **keeps the version it started with**.

That's why `/update` counts them and gives you the button:

```
🟢 Claude Code 2.1.280 — up to date
⏳ 4 sessions are still running the version they started with (1 working right
   now). Updating the binary does not reach them.

[🔄 Restart 3]
```

The button **doesn't touch the ones that are working** and says which it skipped: the only
thing a restart costs is half-finished work, and deciding which one to interrupt isn't
a button's job. For those, ⏸ and ▶️ one at a time.

Each session's version comes from `~/.claude-<session>/sessions/<pid>.json`, which
Claude writes — the same file `bridgeSessionId` comes from. And only the record of a
**live** process counts: the directory also keeps the ones from
earlier starts.

**It isn't inferred from the binary's date**, even though that would be easier: Claude Code
auto-updates and rewrites its package every few minutes without changing version
— measured here, three different `mtime`s in twenty minutes with the same `2.1.280`
inside. Comparing dates would mark every session as outdated
forever, which is worse than not alerting.

The version comparison is **numeric**, not textual. `2.1.270` is newer
than `2.1.9`, and comparing strings gets it backwards.

## Work that only exists on this disk

A session that commits on its own produces the failure nobody sees coming. Measured on
2026-09-13 here: `job-queue` with 21 unpushed commits from 8 days earlier, and
`budget-app` —a **live** session— with a repo that didn't even have a remote.

`/backup` shows it, and the bot checks it once a day and only alerts if there's
something:

```
💾 Work with no backup

⛔ budget-app — no remote
⚠️ job-queue — 21 commits unpushed (8 d) · 1 uncommitted

✅ Pushed and clean: billing-api, podcast-dl, photo-sync, travel

[⬆️ job-queue]
```

⛔ has nowhere to go and a button doesn't fix that: you need to create a remote for it
(`/new` creates private repos). ⚠️ has one and hasn't gone, and there the `⬆️` does the
`git push`.

It fires on what **doesn't fix itself by waiting**: no remote, a branch that doesn't track
anything, unpushed commits and stashes. Uncommitted files do **not**
fire it on their own —that's a session at work, and an alarm that goes off
daily for normal things ends up ignored— but they're counted once there's already some of
the other.

And with a 6 h grace period (`CLAUDE_RC_BACKUP_GRACE`, in seconds): what's checked is
the age of the **oldest** unpushed commit, i.e. how long it's been without a
backup. A commit from five minutes ago isn't abandoned work.

`git push` is still denied to Claude in `~/.claude/settings.json`, and this doesn't
change that: the agent can't, and you're the one who taps the button. It's the same deliberate
decision, taken from your phone.

## Memory budget

Each session takes 0.5–1 GB. With 8 GB of RAM 4 fit comfortably; the 4 GB swap is the
cushion. If you're tight, start only the ones you use instead of leaving them all running.

That's what **⏸ Pause** in the bot is for, one button per session. It stops the service without
disabling it: it doesn't close or delete anything —repo, config dir and conversation stay
where they are— and **▶️ Resume** picks it up at the same point, because the unit
starts with `--continue`. The message tells you how much memory was freed.

A paused one shows as ⏸ in `/status`, not as ⛔: what tells them apart is that
`systemctl --user is-active` says `inactive`, and with `Restart=always` that only
happens if someone stopped it. The watchdog doesn't revive it either — when it finds no
tmux session it steps aside and leaves it to systemd.

After a machine reboot they all come back: the instance stays enabled. If
what you want is for it not to come back, that's **Close**, not Pause.

### Telegram's limits, measured

Not from the documentation, but tested against the API on 2026-09-14:

| | limit | what happens past it |
|---|---|---|
| Text | **4096 code points** | `message is too long` |
| `callback_data` | **64 bytes** | `BUTTON_DATA_INVALID` — and the **whole** message isn't sent |
| Malformed HTML | — | `can't parse entities` — the message **is lost** |

Text is counted in *code points*, **not** in UTF-16 or bytes: 4096 emoji
outside the BMP (8192 UTF-16 units) fit, and 4097 don't. So Python's
`len()` is the right count and a `text[:4000]` never runs over.

What did break things was **cutting in the middle of a tag**. Same text, measured:

```
truncate(text)            len=3995  ok=True
text[:4000]               ok=False  can't parse entities: Unclosed start tag
```

`truncate()` removes the half-cut token (`<cod`, `&am`) and closes whatever was left
open. And underneath there's a safety net: if Telegram rejects the markup anyway, the
bot resends **without HTML** instead of losing the message — an ugly message can be read, one
that doesn't arrive can't.

Both things live inside **`api()`**, which is the only point everything
going out to Telegram passes through. Putting them in `send()` was the first attempt and
left out two sends on the close path, which go to the API directly. If
tomorrow someone adds another `api("sendMessage", …)`, it's born protected.

Session names are limited to **56 characters** for this very reason, and it's not
a round number: callback_data is 64 bytes and the longest prefix was `cerrar?:`,
8 bytes (today's `close?:` is 7). A longer name
wouldn't disable its button — it would bring down the send of the whole menu.

### Questions with a way out

`/close` and `/login` without a session ask "Which one?" and offer the sessions **plus
a Cancel**. Before, they hung the whole menu and there was no way to answer
"none": the only way to get the question off your back was to tap something.

The keyboard uses the `pick:` prefix and not `close?:`/`login:` even though they end up in the
same place, and that's not cosmetic — `is_menu()` classifies by those two prefixes, so
a keyboard that used them would be taken for the menu, `refresh_menus()` would
repaint it and take out precisely the Cancel.

Choosing a session leads to the usual close confirmation, which already has its
own **No**.

### What the bot does, in the journal

One line per tap or command, with how long it took; `SLOW` in front from
3 s on, which is when the next tap starts to be at risk:

```bash
journalctl --user -u claude-rc-bot -o cat | grep -E "^(SLOW )?(tap|command|message)"
```

Before, it only logged errors, and that left the bursts of `query is
too old` on 19 and 22 September unexplained: the bot spent ~20 s not attending and the
journal didn't say what it was doing. From a message's text **nothing** more than
the command name is ever recorded — when the bridge is waiting for a login code, the message
*is* the code.

### A long outage

The outage alert carries the login button, and it's spaced out: 1 h, 2 h, 4 h and then
every 8. job-queue's outage on 18 September —21 and a half hours, login
expired after three days of warnings— was 21 identical messages saying
"Tap 🔑" without the button being there. With this it would have been five, each one
fixable with one tap.

And the watchdog gives up **once**: after `MAX_RESTARTS` failed restarts it
notes "not insisting" and stops counting. Before, it kept writing three lines every
70 s —3,300 a day— with the counter climbing with no ceiling (`failure 9 of 3`).

### Typing a command versus tapping its button

They don't do the same thing, and the difference is deliberate:

| | what it does |
|---|---|
| Tapping 🔄 on the report | **rewrites it in place** — that's what refreshing means |
| Typing `/codex`, `/disk`… | sends a **new** one and leaves the previous one where it was |

The previous version also deleted the old report when you typed the command, and
deleting a message you asked for is disconcerting: you type `/codex`, the previous report
disappears from the history and it looks like it rewrote it instead of
answering you.

What the old one does lose is its **buttons**, which is the pattern the
menus here already use. It stays as readable history, and you can only act on the
latest — a button on a stale report would do what it says, but on figures
that are no longer the ones on screen.

`/status` is the exception and still deletes the previous one: it takes up a whole
screen and is stale state, not history.

### A command nobody answers

If you type `/update` and **nothing** happens —no reply, no error— it's almost always
because the bot was restarting. At startup it discarded commands older than
a minute, and it did so silently: from a phone that's indistinguishable from a
broken bot. Now it tells you which ones it dropped so you can repeat them.

Every bot update opens that window, so it happens more than it seems.

And if a report comes out one line short, suspect the **unit's PATH**,
not the report: systemd doesn't read `.bashrc`, so the bot only sees what
`Environment=PATH` says. It has fallen short twice — `ss` for `/ports`, and `npm`
and `claude` for `/update`, which made Claude Code disappear from the report without a
word.

```bash
systemctl --user show claude-rc-bot -p Environment
```

### A button that seems to do nothing

It almost always did. The bot polls Telegram with a long-poll and some
connections die quietly —about 80 a day—, so the tap can
take a while to arrive. Before, that showed as a button spinning forever and a
`query is too old` in the journal; now the bot answers the whole batch as soon as it
picks it up and discards the same button repeated, and Resume on a session that's
already alive says so instead of relaunching it.

Before repeating the tap, check the fact, not the chat:

```bash
journalctl --user -u 'claude@<project>' -n 5      # did it start?
systemctl --user is-active claude@<project>
```

## Disk budget

Docker is what fills the disk, and not where you'd expect. Look at `docker system df`
and read the "reclaimable" column carefully.

```
systemctl --user list-timers claude-docker-gc.timer   # is it armed?
systemctl --user start claude-docker-gc.service       # sweep now
claude-docker-gc --dry-run                            # look without touching anything
journalctl --user -u claude-docker-gc -n 30           # what it reclaimed
```

The daily sweep puts a **4 GB ceiling on the build cache** and takes away loose
layers, containers stopped for more than a week and orphaned networks. That's
all a machine can decide on its own.

A ceiling, not an age: BuildKit's `until` filter looks at *last use*, not when
it was created, so a layer from three weeks ago that a build touched yesterday counts
as new — with `until=336h` the first sweep reclaimed 0 B out of 8.3 GB. With
the ceiling, BuildKit evicts in order of last use and keeps the working set.

The total can stay above the ceiling without that being a failure: the ceiling
bites on the cache's **own** share, and the part shared with a live image isn't released
until the image is deleted.

What it does **not** do, and not by oversight:

- **Volumes.** An inactive volume is what's left between a `compose down` and
  the next `up` — someone's database. `--volumes` doesn't appear in the
  script.
- **Unused tagged images.** They're usually the fattest chunk (measured:
  6 of the 9.8 GB "reclaimable"), but they only go with `-a`, and with them go
  `php:8.4-cli`, `postgres:17-alpine` and the other bases the next build
  downloads again.

Those two are for a person to decide, and `/disk` is where they're decided:

```
🗄 Disk
54G of 96G used · 56 % · 43G free
🧹 The daily sweep already handles: Containers 16 kB · Build Cache 192 kB.

Tagged images no container is holding
🖼 stefda/osmium-tool:latest — 2.21GB
🖼 qe-a11y:latest — 1.44GB
…and 15 more, smaller.

Volumes with nothing attached
📦 infrastructure_pgdata — 162.1MB

[🗑 osmium-tool:latest] [🗑 qe-a11y:latest]
[🗑 infrastructure_pgdata]
```

An image goes **with one tap**: it comes back with a pull or a build. A volume
**asks first** and shows the name, because it doesn't come back. Before, this was only
visible if the disk went over 75 %, and it's been at 56 % for months: the alert had
never gone off.

The sizes are what Docker reports, i.e. the total: layers shared with
another image don't all come back. And the buttons **never repeat text** — with the
tag left off so they would fit, `php:8.4-cli` and `php:8.3-cli` both ended up
as `🗑 php`, which is how you delete what you didn't want to.

## Syncing with the laptop

They're independent machines: each with its own session history in
`~/.claude/projects/`. Commit before switching places and `git pull` when you arrive.
`git push` is denied in Claude's config: you run it yourself, deliberately.

## Updating Claude Code

```bash
ssh dev@<IP> 'bash -lc "npm update -g @anthropic-ai/claude-code"'
ssh dev@<IP> 'systemctl --user restart claude@travel'   # for each live session
```
