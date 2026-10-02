from harness import *
from harness import _next

ALIVE = {"travel", "CalEngine"}
bot.sessions = lambda: ["travel", "CalEngine"]
bot.blocked = lambda: set()
bot.login_days = lambda s: 30
bot.is_alive = lambda s: s in ALIVE
bot.free_mem = lambda: 3300 if ALIVE == {"travel", "CalEngine"} else 3700
bot.settle = lambda *a, **k: None

executed = []
def fake_run_live(cmd, timeout=300, cwd=None):
    executed.append(" ".join(cmd))
    if cmd[:3] == ["systemctl", "--user", "stop"]:
        ALIVE.discard(cmd[3].split("@")[1])
    if cmd[:3] == ["systemctl", "--user", "start"]:
        ALIVE.add(cmd[3].split("@")[1])
    return (0, "ok")
bot.run_live = fake_run_live

def labels(mid):
    return [[b.get("text") for b in r]
            for r in (CHAT[mid]["kb"] or {}).get("inline_keyboard", [])]

def tap(mid, data):
    bot.handle({"callback_query": {"id": "1", "from": {"id": 42}, "data": data,
                "message": {"message_id": mid, "reply_markup": CHAT[mid]["kb"]}}})
    bot._reply_to = None

failures = []
bot.send("panel")
M = max(CHAT)
print("--- menu with both alive:")
for r in labels(M): print("   ", r)

tap(M, "pause:travel")
M2 = max(CHAT)
print("\n--- after tapping Pause on travel:")
for r in labels(M2): print("   ", r)
print("    executed:", executed[-1])
print("    text:", CHAT[M2]["text"].split("\n")[0][:70])

if "systemctl --user stop claude@travel" != executed[-1]:
    failures.append("did not run the right stop")
if not bot.is_menu({"reply_markup": CHAT[M2]["kb"]}):
    failures.append("is_menu() NO LONGER recognises the menu with a paused session")
if len(menus_on_screen()) != 1:
    failures.append(f"{len(menus_on_screen())} keyboards on screen")

tap(M2, "resume:travel")
M3 = max(CHAT)
print("\n--- after tapping Resume:")
for r in labels(M3): print("   ", r)
print("    executed:", executed[-1])
if "systemctl --user start claude@travel" != executed[-1]:
    failures.append("did not run the right start")
if len(menus_on_screen()) != 1:
    failures.append(f"{len(menus_on_screen())} keyboards after resuming")

print("\n==>", "OK" if not failures else "FAILURES: " + "; ".join(failures))
import sys; sys.exit(1 if failures else 0)
