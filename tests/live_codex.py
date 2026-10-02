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
bot.run_cmd = lambda cmd, timeout=300, cwd=None: (
    lambda r: (r.returncode, (r.stdout + r.stderr).strip()))(
    subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                   env={**_os.environ, "HOME": "/home/dev",
                        "CODEX_HOME": "/home/dev/.codex"}))

print("codex_installed():", bot.codex_installed())
e = bot.codex_state()
print("state:", {k: v for k, v in e.items() if k != "since"})
print()
txt, kb = bot.codex_text()
print(txt)
print("\nbuttons:", [(b["text"], b["callback_data"]) for r in kb["inline_keyboard"] for b in r])
