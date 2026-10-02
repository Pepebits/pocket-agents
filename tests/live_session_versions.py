"""Which version each session on this machine is running."""
import subprocess, pathlib, os, types, shutil as _sh
import harness as H
bot = H.bot
_env = {**os.environ, "HOME": "/home/dev",
        "PATH": "/home/dev/.local/share/mise/shims:/home/dev/.local/share/npm-global/bin:"
                "/home/dev/.local/bin:/usr/bin:/bin:/usr/sbin:/sbin"}
bot.run_cmd = lambda cmd, timeout=300, cwd=None: (
    lambda r: (r.returncode, (r.stdout + r.stderr).strip()))(
    subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=_env))
bot.HOME = pathlib.Path("/home/dev")
bot.sessions = lambda: sorted(
    f.name[len("claude@"):-len(".service")] for f in
    pathlib.Path("/home/dev/.config/systemd/user/default.target.wants").glob("claude@*.service"))

rc, out = bot.run_cmd(["claude", "--version"])
print("on disk:", out.strip())
for s in bot.sessions():
    print(f"  {s:16} {bot.version_of(s) or '—'}")
print("\noutdated:", bot.outdated_sessions())

print()
txt, kb = bot.updates_text()
print(txt)
print("\nbuttons:", [b["text"] for r in kb["inline_keyboard"] for b in r])
