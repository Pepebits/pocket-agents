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

def disk_messages():
    return [m for m, v in H.CHAT.items() if bot.t("dk_title") in v["text"]
            or bot.t("dk_p_title") in v["text"]]

# ---- 1. typed /disk: progress first, then the report; only the report stays ----
# The report goes out as a new message and the progress one is deleted: the
# phone kept drawing the progress after the edit into the report.
bot.dispatch([{"update_id": 1, "message": {"chat": {"id": bot.CHAT}, "from": {"id": bot.CHAT},
                                            "text": "/disk"}}], 0)
sends = [c for c in calls if c[0] == "sendMessage"]
assert len(sends) == 2, f"{len(sends)} sends for one /disk"
prog, mid = sends[0][1], sends[1][1]
assert bot.t("dk_p_title") in sends[0][2], "the first thing isn't the progress"
assert bot.EMOJI_WAIT[0] in sends[0][2], "the pending steps don't carry the animated ⌛"
steps = [c[2] for c in calls if c[0] == "editMessageText" and c[1] == prog]
assert any(bot.EMOJI_DONE[0] in x and bot.EMOJI_WAIT[0] in x for x in steps), "no step was ticked along the way"
assert ("deleteMessage", prog) in [(c[0], c[1]) for c in calls], "the progress message was left behind"
assert disk_messages() == [mid] and bot.t("dk_title") in H.CHAT[mid]["text"], disk_messages()
assert any(c[0] == "sendChatAction" for c in calls), "no 'typing…' while it works"
print(f"✓ /disk: progress with {len(steps)} ticks, then the report; only the report stays")

# ---- 2. deleting an image: result with only 'Back', no session menu ----
k = bot.short_key("node:24")
calls.clear()
tap("rmi:" + k, mid)
assert "node:24" in H.CHAT[mid]["text"], H.CHAT[mid]["text"]
assert buttons(mid) == ["disk:here"], f"result buttons: {buttons(mid)}"
assert not [c for c in calls if c[0] == "sendMessage"], "the result went out as a new message"
print("✓ the result replaces the report with just '🗄 Back to Disk'")

# ---- 3. 'Back': that message shows the progress, then gives way to the report ----
calls.clear()
tap("disk:here", mid)
assert any(c[0] == "editMessageText" and c[1] == mid and bot.t("dk_p_title") in c[2] for c in calls), \
    "the result didn't turn into the progress"
assert mid not in H.CHAT, "the result message was left behind"
left = disk_messages()
assert len(left) == 1 and "rmi*?" in buttons(left[0]), (left, buttons(left[0]) if left else None)
mid = left[0]
print("✓ Back: progress on that message, then one report with its buttons")

# ---- 4. a background job's result (a new message) leads back too ----
calls.clear()
bot._reply_to = None
bot.disk_reply(bot.t("dk_caches_done", s="1 GB"))
new = [c for c in calls if c[0] == "sendMessage"][0][1]
assert buttons(new) == ["disk:here"]
calls.clear()
tap("disk:here", new)
assert new not in H.CHAT
# Earlier reports stay as history, but without buttons: only the newest acts.
active = [m for m in disk_messages() if buttons(m)]
assert len(active) == 1 and "rmi*?" in buttons(active[0]), active
print("✓ a background job's message leads back to a single active report")

# ---- 5. without Premium Telegram may refuse custom emoji: resend with plain ones ----
import io, json
bot.api = H.REAL_API
seen = []
class Resp(io.BytesIO):
    def __enter__(self): return self
    def __exit__(self, *a): return False
def opener(url, data, timeout=None):
    body = dict(x.split("=", 1) for x in data.decode().split("&"))
    seen.append(bot.urllib.parse.unquote_plus(body.get("text", "")))
    if len(seen) == 1:
        raise bot.urllib.error.HTTPError(url, 400, "Bad Request", {},
            io.BytesIO(json.dumps({"ok": False, "error_code": 400,
                                   "description": "Bad Request: custom emoji not allowed"}).encode()))
    return Resp(b'{"ok":true,"result":{"message_id":7}}')
bot.OPEN = opener
r = bot.api("sendMessage", chat_id=1, parse_mode="HTML", text=bot.disk_progress_text({"df"}))
assert r.get("ok"), r
assert len(seen) == 2 and "<tg-emoji" in seen[0] and "<tg-emoji" not in seen[1], seen
assert "⌛" in seen[1] and "✅" in seen[1], seen[1]
print("✓ refused custom emoji: the same message goes again with plain ⌛ and ✅")
print("\n==> OK")
