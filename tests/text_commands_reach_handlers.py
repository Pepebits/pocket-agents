"""Do the text commands reach their handler?"""
import pathlib, os
import harness as H
bot = H.bot
bot.sessions = lambda: []
called = []
for name in ("send_updates", "send_codex", "send_disk", "send_status",
             "send_backup", "send_reboot"):
    setattr(bot, name, (lambda n: lambda *a, **k: called.append(n))(name))

def msg(uid, txt):
    return {"update_id": uid, "message": {"message_id": 700+uid, "text": txt,
            "chat": {"id": bot.CHAT}, "from": {"id": bot.CHAT}, "date": 0}}

off = 0
for i, c in enumerate(["/update", "/actualizar", "/codex", "/disk", "/status",
                       "/backup", "/reboot", "/update@mybot", "/nope"]):
    H.CHAT.clear(); called.clear()
    off = bot.dispatch([msg(i+1, c)], off)
    last = H.CHAT[max(H.CHAT)]["text"][:46] if H.CHAT else ""
    print(f"  {c:16} -> {called or last}")
