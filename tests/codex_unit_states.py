"""The four possible states of the Codex unit."""
import pathlib, os
import harness as H
bot = H.bot
bot.sessions = lambda: []
# It only has to EXIST: everything that gets run is replaced further down.
bot.CODEX_BIN = pathlib.Path(__file__)

SCENARIOS = {
 "up":         ("loaded", "active",     True,  True),
 "stopped":    ("loaded", "inactive",   False, True),
 "failing":    ("loaded", "activating", False, True),
 "no unit":    ("not-found", "inactive", True, True),
 "no login":   ("loaded", "active",     True,  False),
}
for name, (load, active, server, login) in SCENARIOS.items():
    def fake(cmd, timeout=300, cwd=None, _l=load, _a=active, _s=server, _g=login):
        if cmd[:3] == ["systemctl", "--user", "show"]:
            return 0, f"LoadState={_l}\nActiveState={_a}\nExecMainStartTimestamp="
        if "daemon" in cmd and "version" in cmd:
            return (0, '{"status":"running","appServerVersion":"0.154.0"}') if _s else (1, "")
        if cmd[-2:] == ["login", "status"]:
            return (0, "Logged in using ChatGPT") if _g else (0, "Not logged in")
        return 1, ""
    bot.run_cmd = fake
    txt, kb = bot.codex_text()
    print(f"--- {name}")
    for l in txt.splitlines()[2:]:
        if l.strip() and not l.startswith("Un daemon"):
            print("   ", l)
    print("    buttons:", [b["callback_data"] for r in kb["inline_keyboard"] for b in r])
    print()

# None of them offers something that is going to fail
bot.run_cmd = lambda cmd, timeout=300, cwd=None: (
    (0, "LoadState=loaded\nActiveState=inactive\nExecMainStartTimestamp=")
    if cmd[:3] == ["systemctl", "--user", "show"] else (1, ""))
cbs = [b["callback_data"] for r in bot.codex_text()[1]["inline_keyboard"] for b in r]
assert "cx_stop" not in cbs, "offers Stop on a stopped service"
assert "cx_pair" not in cbs, "offers Pair without a login"
assert "cx_start" in cbs
print("==> OK")
