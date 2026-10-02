"""/update and the /codex buttons, against the real thing."""
import subprocess, pathlib, os
import harness as H
bot = H.bot
bot.HOME = pathlib.Path("/home/dev")
bot.CODEX_BIN = pathlib.Path("/home/dev/.codex/packages/standalone/current/bin/codex")
_env = {**os.environ, "HOME": "/home/dev", "CODEX_HOME": "/home/dev/.codex",
        "PATH": "/home/dev/.local/share/mise/shims:/home/dev/.local/share/npm-global/bin:"
                "/home/dev/.local/bin:/usr/bin:/bin"}
bot.run_cmd = lambda cmd, timeout=300, cwd=None: (
    lambda r: (r.returncode, (r.stdout + r.stderr).strip()))(
    subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=_env))
bot.sessions = lambda: []

print("=== versions")
print("  claude:", bot.claude_version())
print("  codex :", bot.codex_version())
print()
txt, kb = bot.updates_text()
print(txt)
print("\nbuttons:", [b["text"] for r in kb["inline_keyboard"] for b in r])

print("\n=== /codex with the service up")
txt, kb = bot.codex_text()
print(txt)
print("\nbuttons:", [(b["text"], b["callback_data"]) for r in kb["inline_keyboard"] for b in r])

# version comparator
print("\n=== _v()")
for a, b in (("2.1.270","2.1.9"), ("0.154.0","0.155.0"), ("rust-v0.154.0","0.154.0")):
    print(f"  {a!r:16} vs {b!r:10} -> {bot._v(a)} {'>' if bot._v(a)>bot._v(b) else '<=' } {bot._v(b)}")
assert bot._v("2.1.270") > bot._v("2.1.9"), "numeric comparison, not text"
assert bot._v("rust-v0.154.0") == bot._v("0.154.0")
print("\n==> OK")
