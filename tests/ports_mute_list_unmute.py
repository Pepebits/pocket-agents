"""Mute, list and unmute a port."""
import os, pathlib

import harness as H
bot = H.bot
F = pathlib.Path(os.environ["CLAUDE_RC_NET_ALLOW_FILE"])
bot.sessions = lambda: []

# Fake ss/docker: tcp:4173 is served by a native vite, tcp:8080 by a container.
def fake_run(cmd, timeout=300, cwd=None):
    if cmd[0] == "ss":
        return 0, ("tcp LISTEN 0 511 0.0.0.0:4173 0.0.0.0:* "
                   f'users:(("MainThread",pid={os.getpid()},fd=20))\n'
                   "tcp LISTEN 0 4096 0.0.0.0:22 0.0.0.0:*\n"
                   "udp UNCONN 0 0 *:45001 *:*\n")
    if cmd[0] == "docker":
        return 0, "compose-gateway-1|0.0.0.0:8080->8080/tcp|2 weeks ago\n"
    return 0, ""
bot.run_cmd = fake_run

def tap(uid, data, mid):
    return {"update_id": uid, "callback_query": {
        "id": str(uid), "from": {"id": bot.CHAT}, "data": data,
        "message": {"message_id": mid}}}

def text(mid): return H.CHAT[mid]["text"]
def buttons(mid):
    return [b["text"] for r in (H.CHAT[mid]["kb"] or {}).get("inline_keyboard", []) for b in r]

# --- 1. the watchdog's alert, with its button
alert = bot.api("sendMessage", text="🌐 tcp:4173 listening outside loopback…",
                reply_markup={"inline_keyboard": [[
                    {"text": "🔇 Mute tcp:4173", "callback_data": "mute:tcp:4173"}]]}
                )["result"]["message_id"]
print("1) alert:", buttons(alert))

# --- 2. Mute is tapped
bot.dispatch([tap(1, "mute:tcp:4173", alert)], 0)
print("2) after muting:", text(alert))
print("   buttons:", buttons(alert))
print("   file:", repr(pathlib.Path(os.environ["CLAUDE_RC_NET_ALLOW_FILE"]).read_text()))

# --- 3. another port, by hand and without a date (as a human would leave it)
with open(os.environ["CLAUDE_RC_NET_ALLOW_FILE"], "a") as f:
    f.write("tcp:8080   # the compose gateway\ngarbage\n")

# --- 4. the list
bot.dispatch([tap(2, "ports", alert)], 2)
print("\n4) report:\n" + text(alert))
print("   buttons:", buttons(alert))

# --- 5. unmute tcp:4173 from the list
bot.dispatch([tap(3, "unmute:tcp:4173", alert)], 3)
print("\n5) after unmuting:", text(alert))
print("   buttons:", buttons(alert))
print("   file:", repr(pathlib.Path(os.environ["CLAUDE_RC_NET_ALLOW_FILE"]).read_text()))

# --- 6. the unit's fixed one cannot be removed
bot.dispatch([tap(4, "unmute:tcp:22", alert)], 4)
print("\n6) tcp:22:", text(alert))
