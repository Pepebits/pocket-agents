"""Three taps on Resume in the same batch."""
import harness as H
bot = H.bot

CHAT = bot.CHAT
bot.sessions = lambda: ["flex-url", "travel"]

paused = {"flex-url"}
bot.is_alive = lambda s: s not in paused

started = []
def fake_systemctl(cmd, timeout=300, cwd=None):
    started.append(cmd)
    if cmd[:3] == ["systemctl", "--user", "start"]:
        paused.discard(cmd[3].split("@")[1])
    return 0, "ok"
bot.run_live = fake_systemctl
bot.settle = lambda *a, **k: None

acks = []
_api = H.api
def api(method, **p):
    if method == "answerCallbackQuery":
        acks.append(p.get("callback_query_id"))
        return {"ok": True}
    return _api(method, **p)
bot.api = api
H.CHAT.clear()

# the menu that is on screen
mid = bot.api("sendMessage", text="menu", reply_markup=bot.menu())["result"]["message_id"]

def tap(uid, cbid, data):
    return {"update_id": uid,
            "callback_query": {"id": cbid, "from": {"id": bot.CHAT_ID if hasattr(bot, "CHAT_ID") else bot.CHAT},
                               "data": data,
                               "message": {"message_id": mid,
                                           "reply_markup": bot.menu()}}}

# Counting the systemctl calls is NOT enough: resume() also checks whether the
# session is already alive, so removing the dedup entirely would still give a
# single start. They are two defences for the same thing and this tests the
# upper one -- how many times the tap arrives, not how many take effect.
arrivals = []
_resume = bot.resume
bot.resume = lambda x: (arrivals.append(x), _resume(x))[1]

batch = [tap(1, "a", "resume:flex-url"),
         tap(2, "b", "resume:flex-url"),
         tap(3, "c", "resume:flex-url")]
off = bot.dispatch(batch, 0)

print("offset          :", off, "(expected 4)")
print("systemctl start :", [c[3] for c in started], "(expected 1)")
# Asserted and not just printed: the previous version showed the number and
# carried on, so removing the dedup entirely broke nothing here.
assert len(started) == 1, f"three taps launched {len(started)} services"
print("taps handled    :", len(arrivals), "(expected 1)")
assert len(arrivals) == 1, f"the same button was handled {len(arrivals)} times"
assert acks == ["b", "c", "a"], acks
print("acks            :", acks, "(b and c answered in the pre-pass; a by handle)")
print("is_alive(flex-url):", bot.is_alive("flex-url"))
print("final text      :", H.CHAT[mid]["text"][:70])

# --- A fourth tap, now in another batch: the session is alive.
started.clear()
batch2 = [tap(4, "d", "resume:flex-url")]
off = bot.dispatch(batch2, off)
print("\nsecond batch -- systemctl:", [c[3] for c in started], "(expected none)")
assert not started, "relaunched a session that was already alive"
print("final text      :", H.CHAT[mid]["text"][:80])
kb = H.CHAT[mid]["kb"]["inline_keyboard"]
print("flex-url buttons:", [b["text"] for r in kb for b in r if "resume" in b.get("callback_data","") or "pause" in b.get("callback_data","")])
