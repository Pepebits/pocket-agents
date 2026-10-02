"""The reports, with the PATH the bot really has under systemd."""
import subprocess, pathlib, os, time
import harness as H
bot = H.bot
bot.HOME = pathlib.Path("/home/dev")
bot.CODEX_BIN = pathlib.Path("/home/dev/.codex/packages/standalone/current/bin/codex")
bot.sessions = lambda: []
PATH_UNIT = "/home/dev/.local/share/mise/shims:/home/dev/.local/share/npm-global/bin:/home/dev/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
_env = {"HOME": "/home/dev", "PATH": PATH_UNIT, "LANG": "C.UTF-8",
        "XDG_RUNTIME_DIR": "/run/user/1001"}
def run_cmd(cmd, timeout=300, cwd=None):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=_env)
        return r.returncode, (r.stdout + r.stderr).strip()
    except Exception as e:
        return 1, f"{type(e).__name__}: {e}"
bot.run_cmd = run_cmd

for name, fn in (("/codex", bot.codex_text), ("/update", bot.updates_text)):
    t0 = time.time()
    txt, kb = fn()
    print(f"=== {name}  ({time.time()-t0:.1f} s)")
    print(txt[:400])
    print()
