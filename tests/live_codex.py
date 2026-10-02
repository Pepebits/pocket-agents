"""/codex against the real Codex and systemd."""
import subprocess, pathlib, os
import harness as H
bot = H.bot
bot.HOME = pathlib.Path("/home/dev")
bot.CODEX_BIN = pathlib.Path("/home/dev/.codex/packages/standalone/current/bin/codex")
bot.run_cmd = lambda cmd, timeout=300, cwd=None: (
    lambda r: (r.returncode, (r.stdout + r.stderr).strip()))(
    subprocess.run(cmd, capture_output=True, text=True, timeout=timeout))
bot.sessions = lambda: []
# The harness sets a fake HOME; Codex keeps its credentials and its socket
# there, so without this the report comes out all red because of the test
# itself.
import os as _os
def run_cmd(cmd, timeout=300, cwd=None):
    # Same contract as the bot's own run_cmd: a missing binary is an error
    # result, not an exception. On a machine without Codex (it's optional) the
    # report must say so instead of the test crashing.
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                           env={**_os.environ, "HOME": "/home/dev",
                                "CODEX_HOME": "/home/dev/.codex"})
        return r.returncode, (r.stdout + r.stderr).strip()
    except Exception as e:
        return 1, f"{type(e).__name__}: {e}"
bot.run_cmd = run_cmd

print("codex_installed():", bot.codex_installed())
e = bot.codex_state()
print("state:", {k: v for k, v in e.items() if k != "since"})
print()
txt, kb = bot.codex_text()
print(txt)
print("\nbuttons:", [(b["text"], b["callback_data"]) for r in kb["inline_keyboard"] for b in r])
