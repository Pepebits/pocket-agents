"""The reboot report, against the real machine."""
import subprocess, pathlib, os
import harness as H
bot = H.bot
bot.HOME = pathlib.Path("/home/dev")
bot.run_cmd = lambda cmd, timeout=300, cwd=None: (
    lambda r: (r.returncode, (r.stdout + r.stderr).strip()))(
    subprocess.run(cmd, capture_output=True, text=True, timeout=timeout))
bot.sessions = lambda: sorted(
    f.name[len("claude@"):-len(".service")] for f in
    pathlib.Path("/home/dev/.config/systemd/user/default.target.wants").glob("claude@*.service"))
txt, kb = bot.reboot_text()
print(txt)
print("\nbuttons:", [(b["text"], b["callback_data"], b.get("style")) for r in kb["inline_keyboard"] for b in r])
print("\nis_busy(travel):", bot.is_busy("travel"), " is_busy(billing-api):", bot.is_busy("billing-api"))
