from harness import *
from harness import _next

# Two fake sessions: the menu takes 1 + 2*2 = 5 rows.
bot.sessions = lambda: ["flex-url", "share-stories"]
bot.blocked = lambda: set()
bot.login_days = lambda s: 30

failures = []
def check(tag):
    dump(tag)
    if len(menus_on_screen()) > 1:
        failures.append(f"{tag}: {len(menus_on_screen())} menus")

# 1. Startup after a restart, with two old menus alive in the chat.
for _ in range(2):
    _next[0] += 1
    CHAT[_next[0]] = {"text": "old menu", "kb": bot.menu()}
    bot.MENUS[_next[0]] = json.dumps(bot.menu(), sort_keys=True)
dump("before startup (as it was)")
bot.send("bot running\n" + "status…")
check("1. startup")

# 2. /new project  ->  picker
bot._reply_to = None
bot.new_session("radio download")
check("2. /new radio download")
picker = max(CHAT)

# 3. tap on "Empty": the answer goes IN the picker
bot._reply_to = picker
bot.api("editMessageReplyMarkup", chat_id=42, message_id=picker,
        reply_markup={"inline_keyboard": []})
bot.sessions = lambda: ["flex-url", "share-stories", "radio-download"]
bot.init_empty("radio-download")
check("3. session created")

# 4. the health check arrives minutes later: NEW message, it notifies
bot._reply_to = None
bot.send(bot.t("hc_ok", x="radio-download"))
check("4. health check (the bug's case)")

# 5. two /status in a row
bot._reply_to = None
bot.send_status()
r1 = max(CHAT)
bot._reply_to = None
bot.sessions = lambda: ["flex-url"]      # the status changes
bot.send_status()
check("5. second /status")
if r1 in CHAT:
    failures.append("5: the old report is still in the chat")

print("\n==>", "OK" if not failures else "FAILURES: " + "; ".join(failures))
import sys; sys.exit(1 if failures else 0)
