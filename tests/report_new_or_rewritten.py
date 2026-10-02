"""Sending /codex twice: is a new message born or is the old one rewritten?"""
import pathlib, os
import harness as H
bot = H.bot
bot.sessions = lambda: []
bot.codex_text = lambda: ("codex report " + str(len(H.LOG)), {"inline_keyboard": [[{"text": "x", "callback_data": "codex"}]]})

def msg(uid, txt):
    return {"update_id": uid, "message": {"message_id": 800+uid, "text": txt,
            "chat": {"id": bot.CHAT}, "from": {"id": bot.CHAT}, "date": 0}}

off = 0
for i in (1, 2, 3):
    before = sorted(H.CHAT)
    H.LOG.clear()
    off = bot.dispatch([msg(i, "/codex")], off)
    print(f"  send #{i}: calls={H.LOG}  messages in chat={sorted(H.CHAT)}")
    assert "sendMessage" in H.LOG, f"#{i}: did not send a new one"
    # What used to be checked only by eye, and that is why it caught nothing:
    # deleting the previous report takes away a message the user asked for.
    assert "deleteMessage" not in H.LOG, f"#{i}: deleted the previous report"
    assert all(m in H.CHAT for m in before), f"#{i}: an old message disappeared"
print()
print("=== and now mixed with another command")
H.LOG.clear(); off = bot.dispatch([msg(9, "/help")], off)
print("  /help  :", H.LOG, sorted(H.CHAT))
H.LOG.clear(); off = bot.dispatch([msg(10, "/codex")], off)
print("  /codex :", H.LOG, sorted(H.CHAT))

print()
print("=== the refresh button DOES rewrite in place")
def tap(uid, data, mid):
    return {"update_id": uid, "callback_query": {"id": str(uid),
            "from": {"id": bot.CHAT}, "data": data,
            "message": {"message_id": mid}}}
last = max(H.CHAT)
before = sorted(H.CHAT)
H.LOG.clear()
off = bot.dispatch([tap(20, "codex", last)], off)
print("  tap    :", H.LOG, "| same messages:", sorted(H.CHAT) == before)
assert sorted(H.CHAT) == before, "the button chained a new message"
assert "editMessageText" in H.LOG

print()
print("=== the old reports stay, without buttons")
# Only the REPORTS: the menu that comes with /help has buttons by every right
# and is not one of these.
reports = [m for m, v in H.CHAT.items()
           if any(b.get("callback_data") == "codex"
                  for r in ((v["kb"] or {}).get("inline_keyboard") or [])
                  for b in r)]
print("  in the chat:", len(H.CHAT), "| tappable reports:", reports)
assert len(reports) == 1, f"more than one tappable report: {reports}"
assert reports[0] == max(H.CHAT), "the tappable one is not the last one"
print("\n==> OK")
