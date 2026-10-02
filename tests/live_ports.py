"""listeners() against the real machine, and the /ports command."""
import os, pathlib
import harness as H
bot = H.bot
bot.sessions = lambda: []
import subprocess
bot.run_cmd = lambda cmd, timeout=300, cwd=None: (lambda r: (r.returncode, r.stdout + r.stderr))(subprocess.run(cmd, capture_output=True, text=True, timeout=timeout))

print("== real listeners()")
for p, (who, how_long, loc) in sorted(bot.listeners().items()):
    print(f"  {p:12} {'local' if loc else 'OUT':5} {who or chr(8212):40} {how_long or chr(8212)}")

print("\n== /ports as text")
def msg(uid, txt):
    return {"update_id": uid, "message": {"message_id": 500 + uid, "text": txt,
                                          "chat": {"id": bot.CHAT},
                                          "from": {"id": bot.CHAT}, "date": 0}}
off = bot.dispatch([msg(1, "/ports")], 0)
last = max(H.CHAT)
print(H.CHAT[last]["text"])
print("\n== /ports tcp:4173  and  /ports -tcp:4173")
bot.dispatch([msg(2, "/ports tcp:4173")], off)
print(" ->", H.CHAT[max(H.CHAT)]["text"])
bot.dispatch([msg(3, "/ports -tcp:4173")], off)
print(" ->", H.CHAT[max(H.CHAT)]["text"])
print("\n== published commands:", [c for c, _ in bot.COMMANDS])
