"""/disk answers at once, and its results lead back to it.

It takes 3 to 16 s, and nothing showed meanwhile. And a result ("🗑 … gone")
replaced the report in place with the whole session menu under it: after
deleting an image you were looking at every session's status, not the disk.
"""
import harness as H
bot = H.bot

# A /disk with something in it, without touching the machine.
bot.rust_targets = lambda: []
bot.run_parallel = lambda cmds, timeout=60: [(0, ""), (0, ""), (0, "")]
bot.unused_images = lambda: [("node:24", "1.6GB"), ("php:8.4", "700MB")]
bot.dangling_volumes = lambda with_size=True, df_v=None: []
bot.run_cmd = lambda cmd, *a, **k: ((0, "1B-blocks Used Avail Use%\n96000000000 50000000000 46000000000 52%")
                                    if cmd[0] == "df" else (0, "Untagged: node:24"))

# Record every call with its message and text, on top of the fake Telegram.
calls = []
fake = bot.api
def api(method, **p):
    r = fake(method, **p)
    mid = p.get("message_id") or ((r.get("result") or {}).get("message_id") if isinstance(r.get("result"), dict) else None)
    calls.append((method, mid, p.get("text", "")))
    return r
bot.api = api

def tap(data, mid):
    bot.dispatch([{"update_id": 9000 + len(calls), "callback_query": {
        "id": "x", "from": {"id": bot.CHAT}, "data": data,
        "message": {"message_id": mid}}}], 0)

def buttons(mid):
    return [b["callback_data"] for row in (H.CHAT[mid]["kb"] or {}).get("inline_keyboard", []) for b in row]

# ---- 1. typed /disk: one message, progress first, then the report ----
bot.dispatch([{"update_id": 1, "message": {"chat": {"id": bot.CHAT}, "from": {"id": bot.CHAT},
                                            "text": "/disk"}}], 0)
sends = [c for c in calls if c[0] == "sendMessage"]
assert len(sends) == 1, f"{len(sends)} messages for one /disk"
mid = sends[0][1]
assert bot.t("dk_p_title") in sends[0][2] and "⏳" in sends[0][2], "the first thing isn't the progress"
steps = [c[2] for c in calls if c[0] == "editMessageText" and c[1] == mid and bot.t("dk_p_title") in c[2]]
assert any("✅" in s and "⏳" in s for s in steps), "no step was ticked along the way"
assert bot.t("dk_title") in H.CHAT[mid]["text"], "the message didn't end as the report"
assert any(c[0] == "sendChatAction" for c in calls), "no 'typing…' while it works"
print(f"✓ /disk: one message, {len(steps)} progress edits, then the report")

# ---- 2. deleting an image: result with only 'Back', no session menu ----
k = bot.short_key("node:24")
calls.clear()
tap("rmi:" + k, mid)
assert "node:24" in H.CHAT[mid]["text"], H.CHAT[mid]["text"]
assert buttons(mid) == ["disk:here"], f"result buttons: {buttons(mid)}"
assert not [c for c in calls if c[0] == "sendMessage"], "the result went out as a new message"
print("✓ the result replaces the report with just '🗄 Back to Disk'")

# ---- 3. 'Back' turns that same message into the report again ----
calls.clear()
tap("disk:here", mid)
assert not [c for c in calls if c[0] == "sendMessage"], "Back opened a new message"
assert bot.t("dk_title") in H.CHAT[mid]["text"]
assert "rmi*?" in buttons(mid), buttons(mid)
print("✓ Back: the same message is the report again, with its buttons")

# ---- 4. a background job's result (a new message) also leads back in place ----
calls.clear()
bot._reply_to = None
bot.disk_reply(bot.t("dk_caches_done", s="1 GB"))
new = [c for c in calls if c[0] == "sendMessage"][0][1]
assert buttons(new) == ["disk:here"]
calls.clear()
tap("disk:here", new)
assert not [c for c in calls if c[0] == "sendMessage"]
assert bot.t("dk_title") in H.CHAT[new]["text"]
print("✓ a background job's message leads back to the report in place too")
print("\n==> OK")
