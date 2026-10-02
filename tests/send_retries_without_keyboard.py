"""What still belongs to send(): if the keyboard kills the send, it goes without it.

The HTML retry is NOT tested here any more -- it lives inside api(), so
replacing bot.api would skip it entirely. api_guards_every_send covers that,
hooking OPEN.
"""
import pathlib, os
import harness as H
bot = H.bot
bot.sessions = lambda: ["travel"]
bot.login_days = lambda s: 30
bot.is_alive = lambda s: True
bot.blocked = lambda: set()

tries = []
_next = [400]
def api(method, **p):
    if method == "sendMessage":
        tries.append("with keyboard" if "reply_markup" in p else "without keyboard")
        if "reply_markup" in p:
            return {"ok": False, "error_code": 400,
                    "description": "Bad Request: REPLY_MARKUP_TOO_LONG"}
        _next[0] += 1
        H.CHAT[_next[0]] = {"text": p["text"], "kb": None}
        return {"ok": True, "result": {"message_id": _next[0]}}
    return {"ok": True, "result": []}
bot.api = api

bot._reply_to = None
H.CHAT.clear()
mid = bot.send("an alert that matters")
print("tries  :", tries)
print("arrived:", repr(H.CHAT[mid]["text"]) if mid else "DID NOT ARRIVE")
assert tries == ["with keyboard", "without keyboard"], tries
assert mid and H.CHAT[mid]["text"] == "an alert that matters"
print("\n==> OK")
