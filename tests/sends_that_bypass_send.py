"""The two sends that bypass send() are covered too."""
import pathlib, os
import harness as H
bot = H.bot
ses = "a"*56
bot.sessions = lambda: [ses, "travel"]
bot.login_days = lambda s: 30
bot.is_alive = lambda s: True
bot.blocked = lambda: set()

seen = []
_api = H.api
def api(method, **p):
    if method in bot.LIMITS and "text" in p:
        seen.append((method, len(p["text"]), p.get("parse_mode")))
    return _api(method, **p)
bot.api = api

# The close?: path does not go through send() -- bare editMessageText and sendMessage
H.CHAT.clear()
mid = _api("sendMessage", text="menu", reply_markup=bot.menu())["result"]["message_id"]
bot.dispatch([{"update_id": 1, "callback_query": {"id": "1", "from": {"id": bot.CHAT},
    "data": f"close?:{ses}", "message": {"message_id": mid}}}], 0)
print("calls with text, along the close?: path:")
for m, n, pm in seen:
    print(f"   {m:18} len={n:4} parse_mode={pm}")
    assert n <= bot.LIMITS[m], f"{m} went over {bot.LIMITS[m]}"
print("   all within the limit ✓")

print("\nAnd the 56-character name in its callback:")
for r in H.CHAT[mid]["kb"]["inline_keyboard"]:
    for b in r:
        d = b.get("callback_data", "")
        if d: assert len(d.encode()) <= 64, (d, len(d.encode()))
print(f"   'close!:{ses[:8]}…' = {len(('close!:'+ses).encode())} bytes ✓")
print("\n==> OK")
