"""dispatch() with an empty batch has to clear _reply_to just like with a
full one -- otherwise the async alert main() sends right after
(check_health, check_codex_login, alert_backup) EDITS a user's last bubble
instead of sending a new message, and editing does not notify.

The real bug: the _reply_to reset lived in the finally of a for loop over
the batch, and with an empty batch that loop does not run even once. A
long-poll getUpdates with nothing new -which is the normal case- leaves
_reply_to hooked to the last user message forever.
"""
import harness as H
bot = H.bot
bot.sessions = lambda: []

H.CHAT.clear()
bot._reply_to = None

# Simulates a normal user message: the bubble stays "hooked".
mid1 = bot.send("first", with_menu=False)
assert bot._reply_to == mid1

# A getUpdates that brings nothing new -the normal long-poll case- must not
# leave _reply_to hooked to that bubble.
offset = bot.dispatch([], 999)
assert offset == 999, "an empty batch must not move the offset"
assert bot._reply_to is None, (
    "dispatch() with an empty batch has to release _reply_to; "
    f"it stayed at {bot._reply_to!r}"
)

# And so an async alert sends a new bubble, it does not edit "first".
mid2 = bot.send("second", with_menu=False)
print("first :", H.CHAT[mid1]["text"])
print("second:", H.CHAT[mid2]["text"])
assert mid2 != mid1, "the second alert edited the first one instead of notifying"
assert H.CHAT[mid1]["text"] == "first", "editing the first one would be silent"
assert H.CHAT[mid2]["text"] == "second"

print("\n==> OK")
