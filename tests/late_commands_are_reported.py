"""What arrived while the bot was away: handled, reported, or ignored.

The previous version of this test REWROTE the startup block instead of
calling it, so it was checking a copy. You could remove the whole notice from
the bot and this file stayed green. Now it calls handle_backlog().
"""
import time
import harness as H
bot = H.bot
bot.sessions = lambda: []
bot.waiting = lambda: []

now = int(time.time())
def msg(uid, txt, age):
    return {"update_id": uid, "message": {"message_id": uid, "text": txt,
            "chat": {"id": bot.CHAT}, "from": {"id": bot.CHAT},
            "date": now - age}}

handled = []
bot.send_status = lambda *a, **k: handled.append("/status")
bot.send_codex = lambda *a, **k: handled.append("/codex")

H.CHAT.clear()
off = bot.handle_backlog([
    msg(1, "/update", 600),          # old: reported
    msg(2, "/codex", 300),           # old: reported
    msg(3, "hello", 900),             # old loose text: ignored
    msg(4, "/status", 5),            # recent: run
    {"update_id": 5, "callback_query": {"id": "x", "from": {"id": bot.CHAT},
     "data": "up_claude", "message": {"message_id": 9}}},   # never
])
notices = [v["text"] for v in H.CHAT.values() if "/update" in v["text"]]
print("  offset      :", off, "(expected 6)")
print("  run         :", handled, "(expected only /status)")
print("  notice      :", (notices[0].splitlines()[0][:70] if notices else "NONE"))
assert off == 6
assert handled == ["/status"], handled
assert notices, "did not report the discarded commands"
assert "/update" in notices[0] and "/codex" in notices[0]
assert "hello" not in notices[0], "a loose text is not a command"

print("\n--- and if the bridge is waiting for a code, the loose text IS handled")
H.CHAT.clear(); handled.clear()
bot.waiting = lambda: ["travel"]
received = []
bot.handle = lambda u: received.append((u.get("message") or {}).get("text"))
bot.handle_backlog([msg(10, "ABC123", 900), msg(11, "/status", 5)])
print("  handled     :", received, "(the code yes, the command no)")
assert received == ["ABC123"], received
print("\n==> OK")
