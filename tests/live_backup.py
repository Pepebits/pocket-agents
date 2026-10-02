"""The backup report against the real machine."""
import subprocess, os, pathlib
import harness as H
bot = H.bot
bot.HOME = pathlib.Path("/home/dev")
bot.run_cmd = lambda cmd, timeout=300, cwd=None: (
    lambda r: (r.returncode, (r.stdout + r.stderr).strip()))(
    subprocess.run(cmd, capture_output=True, text=True, timeout=timeout))
bot.sessions = lambda: sorted(
    f.name[len("claude@"):-len(".service")] for f in
    (pathlib.Path("/home/dev/.config/systemd/user/default.target.wants")).glob("claude@*.service"))
print(bot.backup_text()[0])
print("buttons:", [b["text"] for r in bot.backup_text()[1]["inline_keyboard"] for b in r])
