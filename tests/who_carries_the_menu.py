"""Who carries the menu and who does not."""
import pathlib, os
import harness as H
bot = H.bot
bot.sessions = lambda: ["travel", "CalEngine"]
bot.login_days = lambda s: 30
bot.is_alive = lambda s: True
bot.blocked = lambda: set()

def msg(uid, txt):
    return {"update_id": uid, "message": {"message_id": 900+uid, "text": txt,
            "chat": {"id": bot.CHAT}, "from": {"id": bot.CHAT}, "date": 0}}

off = 0
for i, c in enumerate(["/help", "/start", "/nope", "/login", "/close", "/status"]):
    H.CHAT.clear()
    off = bot.dispatch([msg(i+1, c)], off)
    mid = max(H.CHAT)
    rows = ((H.CHAT[mid]["kb"] or {}).get("inline_keyboard") or [])
    print(f"  {c:9} -> {len(rows)} rows of buttons   {H.CHAT[mid]['text'][:38]!r}")

print()
print("=== and /help does not steal the live menu")
H.CHAT.clear(); bot.MENUS.clear()
off = bot.dispatch([msg(50, "/status")], off)
real_menu = max(H.CHAT)
off = bot.dispatch([msg(51, "/help")], off)
still = [m for m, v in H.CHAT.items() if ((v["kb"] or {}).get("inline_keyboard") or [])]
print(f"  menu in {real_menu}, with buttons after /help: {still}")
assert real_menu in still, "/help took the buttons off the live menu"
print("\n==> OK")
