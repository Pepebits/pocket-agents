"""/close and /login with no argument: pick one, or get out."""
import pathlib, os
import harness as H
bot = H.bot
bot.sessions = lambda: ["travel", "billing-api", "budget-app"]
bot.login_days = lambda s: 30
bot.is_alive = lambda s: True
bot.blocked = lambda: set()

def msg(uid, txt):
    return {"update_id": uid, "message": {"message_id": 950+uid, "text": txt,
            "chat": {"id": bot.CHAT}, "from": {"id": bot.CHAT}, "date": 0}}
def tap(uid, data, mid):
    return {"update_id": uid, "callback_query": {"id": str(uid),
            "from": {"id": bot.CHAT}, "data": data, "message": {"message_id": mid}}}

off = 0
H.CHAT.clear()
off = bot.dispatch([msg(1, "/close")], off)
mid = max(H.CHAT)
print("/close  ->", repr(H.CHAT[mid]["text"]))
for r in H.CHAT[mid]["kb"]["inline_keyboard"]:
    print("   ", [(b["text"], b["callback_data"]) for b in r])

print("\n--- is_menu() must NOT recognise it, or refresh_menus() eats it")
print("   is_menu:", bot.is_menu({"reply_markup": H.CHAT[mid]["kb"]}), "(expected False)")
assert not bot.is_menu({"reply_markup": H.CHAT[mid]["kb"]})

print("\n--- Cancel")
off = bot.dispatch([tap(2, "new!:x", mid)], off)
print("   ->", repr(H.CHAT[max(H.CHAT)]["text"][:40]))

print("\n--- picking one leads to the usual confirmation")
H.CHAT.clear()
off = bot.dispatch([msg(3, "/close")], off)
mid = max(H.CHAT)
off = bot.dispatch([tap(4, "pick:c:travel", mid)], off)
m2 = max(H.CHAT)
print("   ->", repr(H.CHAT[m2]["text"][:60]))
print("   ", [(b["text"], b["callback_data"]) for r in H.CHAT[m2]["kb"]["inline_keyboard"] for b in r])

print("\n--- /login with no argument")
H.CHAT.clear()
off = bot.dispatch([msg(5, "/login")], off)
mid = max(H.CHAT)
for r in H.CHAT[mid]["kb"]["inline_keyboard"]:
    print("   ", [b["text"] for b in r])

print("\n--- no sessions at all")
bot.sessions = lambda: []
H.CHAT.clear()
off = bot.dispatch([msg(6, "/close")], off)
mid = max(H.CHAT)
print("   ->", repr(H.CHAT[mid]["text"]), "| buttons:", bool(H.CHAT[mid]["kb"]))
print("\n==> OK")
