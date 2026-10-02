# Problems found and solved

Five real failures during the setup. All are already fixed in `setup.sh`; they are
documented because they will come back if anyone rewrites these pieces.

## 1. `mise activate` doesn't work in non-interactive shells

**Symptom.** Phase 2 died silently right at the "Claude Code" step. `npm` didn't
exist even though mise said it had installed node.

**Cause.** `mise activate bash` installs a **prompt hook** (`PROMPT_COMMAND`). In a
non-interactive shell —`ssh host 'cmd'`, a script, a systemd unit— that hook never
runs and the PATH is never updated. `set -e` finished the script off with no message.

**Fix.** Use the **shims**, which are real binaries and don't depend on the hook:

```bash
export PATH="$HOME/.local/share/mise/shims:$PATH"
```

`mise activate` stays in `.bashrc` for interactive sessions only.

## 2. A single tmux server means only the first session starts

**Symptom.** `systemctl --user start claude@X` for four projects: the first one
`active`, the other three `inactive (dead)` without a single error in the journal.

**Cause.** With the default socket, the first service starts the tmux **server**
inside *its* cgroup. The second `tmux new-session -d` just talks to that
already-running server and exits immediately, leaving its own cgroup empty: with
`Type=forking`, systemd concludes the service has finished.

**Fix.** One tmux server per service, with its own socket:

```ini
ExecStart=/usr/bin/tmux -L claude-%i new-session -d -s claude-%i "exec .../claude ..."
ExecStop=/usr/bin/tmux -L claude-%i kill-server
```

Careful: when attaching you have to repeat the `-L`.

## 3. The first-run wizard blocks the sessions

**Symptom.** The sessions start and get stuck. They don't show up in the app.

**Cause.** The first interactive `claude` launches the onboarding (theme → login method →
workspace trust). With nobody to answer, the session never reaches the prompt.
Worse: its login step **doesn't reuse** the credential already saved by `claude auth login`
and starts a new OAuth flow.

**Fix.** Authenticate first and mark the onboarding as done in `~/.claude.json`:

```json
{ "hasCompletedOnboarding": true, "theme": "dark" }
```

The workspace trust dialog is separate, and there's one per project.

**Since 2026-09-03 `claude-session` seeds it at startup** and you shouldn't see it
again: it writes `projects["<path>"].hasTrustDialogAccepted = true` into the
session's `.claude.json` before launching Claude. Only trust and onboarding — the
credentials are deliberately not copied: sharing the same refresh token between
sessions is what left three of them without credentials in August (§8).

If you ever do see it, **go in and answer it yourself**:

```bash
ssh dev@<IP> -t 'tmux -L claude-<project> attach'
```

> **Don't send Enter blindly.** The previous version of this page recommended
> `send-keys ... Enter` to every pane at once. Today the dialog's default highlighted
> option is **`No, exit`**, so that command doesn't accept the trust:
> **it closes the sessions, one by one.** Checked on a test instance.

Don't rely on `--permission-mode acceptEdits` either: it doesn't cover this dialog,
they're different gates.

Sign that everything went fine: `/rc` in the pane's bottom bar. Careful, **its absence
proves nothing**: if subagents are running the bar gets pushed out of the last lines,
and in a narrow pane `/rc` itself gets truncated. That's why `claude-rc-status` detects
the hang by looking for the dialog's text, not for the missing `/rc`.

## 4. The session starts, but Claude can't find any tool

**Symptom.** Everything looks right: `node -v` works over SSH, the sessions are
`active`, Claude answers. But as soon as you ask it to run `npm run dev` or
`go test`, the command doesn't exist. It only sees the system `python3`.

**Cause.** systemd **doesn't read** `.bashrc` or `.profile`. A unit without `Environment=PATH`
starts with the system's minimal PATH, without the mise shims or `npm-global/bin`. The
service starts anyway because `ExecStart` invokes `claude` by absolute path — which is
why the failure doesn't show until Claude tries to use a tool.

It's the third face of problem 1: `.bashrc` serves interactive shells, `.profile`
login shells, and systemd is neither.

**Fix.** Explicit PATH in the unit, with the shims first:

```ini
Environment=PATH=%h/.local/share/mise/shims:%h/.local/share/npm-global/bin:%h/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
```

Check it on the live process, not on your shell — it's the only place where the
answer is reliable:

```bash
PID=$(pgrep -f "claude --remote-control <project>" | head -1)
tr '\0' '\n' < /proc/$PID/environ | grep ^PATH=
```

## 5. `claude auth login` needs a TTY that `ssh 'cmd'` doesn't provide

**Symptom.** The login prints the OAuth URL and sits at `Paste code here` unable to
receive anything.

**Cause.** `ssh host -t 'cmd'` doesn't allocate a pseudo-terminal if the local stdin isn't one either.

**Fix.** Launch it inside tmux, which does provide a pty, and inject the code:

```bash
ssh dev@<IP> "tmux new-session -d -s auth 'claude auth login'"
ssh dev@<IP> "tmux capture-pane -pJt auth -S -50 | grep -o 'https://claude.com/[^ ]*'"
# open the URL, authorize, and then:
ssh dev@<IP> "tmux send-keys -t auth '<code>' Enter"
```

`capture-pane -J` joins the lines wrapped by the pane width: without `-J` the URL comes
out chopped up and useless.

---

# Cloudflare Tunnel

Two more failures, both with the same pattern: the request arrives, something answers,
and the answer says nothing useful about the cause.

## 6. `curl: (35)` — the free certificate only covers one subdomain level

**Symptom.** DNS correctly resolves to Cloudflare's IPs, but every request dies in
40 ms with TLS error 35. No logs, neither at the edge nor at the origin.

**Cause.** Cloudflare's **Universal SSL** issues a certificate for `zone.com` and
`*.zone.com` — **a single level**. A host like `p8000.dev.zone.com` has two, isn't
in the SAN, and the handshake doesn't even start. Covering it requires Advanced
Certificate Manager, which is paid.

**Fix.** Flatten the name: `p8000-dev.zone.com` instead of `p8000.dev.zone.com`.
Ugly, free, and it works. Check what the certificate really covers:

```bash
echo | openssl s_client -connect <IP>:443 -servername zone.com 2>/dev/null \
  | openssl x509 -noout -text | grep -A2 "Subject Alternative Name"
```

## 7. The service ignores the config you just wrote

**Symptom.** You change the ingress hostnames, restart, and **everything** returns 404 —
including the ones that worked before.

**Cause.** The service runs as root and always reads `/etc/cloudflared/config.yml`, not
the one in your `$HOME`. And `cloudflared service install` **doesn't overwrite** that file
if it already exists: it keeps the first version forever. The 404 is the ingress's
closing `http_status:404`, triggered because no hostname matches — indistinguishable
from a routing error.

**Fix.** Publish the config explicitly on every run:

```bash
sudo install -m0644 ~/.cloudflared/config.yml /etc/cloudflared/config.yml
sudo systemctl restart cloudflared
```

Codes that help locate the failure:

| Code | Where the problem is |
|---|---|
| `curl: (35)` | TLS: the certificate doesn't cover that hostname |
| `404` | The ingress matches no hostname (catch-all) |
| `502` | The ingress matches, but nothing is listening on that port |
| `530` | The tunnel isn't connected to the edge |

## 8. The sessions share `~/.claude.json` and overwrite each other

**Symptom.** You restart the services after a change to the unit. They all come back
`active`, but several are stuck again on the trust dialog you had already
accepted. In `~/.claude.json` only one keeps `hasTrustDialogAccepted`.

**Cause.** All the sessions share **a single `~/.claude.json`**. Each process
loads it into memory at startup and rewrites it **whole** on exit, so the last one to
write overwrites what the others recorded. There is a `.claude.json.lock`, but it only
makes the write atomic: it doesn't protect against *read-modify-write*. That's why
staggering the startups narrows the window without closing it.

**Fix.** One configuration directory per session, with the credentials and the
permissions policy shared by symlink:

```ini
Environment=CLAUDE_CONFIG_DIR=%h/.claude-%i
```

```bash
for p in <projects>; do
  D="$HOME/.claude-$p"; mkdir -p "$D"
  cp -n ~/.claude.json "$D/.claude.json"          # keeps onboarding and trust
  ln -sfn ~/.claude/.credentials.json "$D/.credentials.json"   # a single login
  ln -sfn ~/.claude/settings.json     "$D/settings.json"       # a single policy
done
```

This works because the token lives in `.credentials.json`, **outside** `.claude.json`.
If it were inside, splitting the config would force authenticating each session separately.

Resulting split:

| File | Scope |
|---|---|
| `.claude.json` — config, trust, onboarding | per session |
| `.credentials.json` — the token | shared |
| `settings.json` — permissions | shared |
| `projects/` — history | per session |

Verify with the test that used to fail — restart **all of them at once**:

```bash
for p in <projects>; do systemctl --user restart "claude@$p" & done; wait
```

## Quick checks

```bash
claude auth status                      # loggedIn, email
systemctl --user list-units 'claude@*'
pgrep -af 'claude --remote-control'

# the PATH Claude really sees — not your shell's
PID=$(pgrep -f 'claude --remote-control <project>' | head -1)
tr '\0' '\n' < /proc/$PID/environ | grep ^PATH=
free -h                                 # 0.5-1 GB per session
```
