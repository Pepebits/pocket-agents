from harness import *
from harness import _next

SES = ["flex-url", "share-stories"]
bot.sessions = lambda: list(SES)
bot.blocked = lambda: set()
bot.login_days = lambda s: 30

def tap(mid, data):
    """Simulates a button tap, as Telegram delivers it."""
    bot.handle({"callback_query": {"id": "1", "from": {"id": 42},
                "data": data,
                "message": {"message_id": mid,
                            "reply_markup": CHAT[mid]["kb"]}}})
    bot._reply_to = None        # main() clears it in its finally

def write(txt):
    bot.handle({"message": {"message_id": 1, "from": {"id": 42}, "text": txt,
                            "date": 0}})
    bot._reply_to = None

failures = []
def check(tag, min_keyboards=1):
    dump(tag)
    if len(menus_on_screen()) > 1:
        failures.append(f"{tag}: {len(menus_on_screen())} menus")
    if len(keyboards_on_screen()) < min_keyboards:
        failures.append(f"{tag}: the chat was left WITHOUT buttons")

bot.send("bot running")
check("0. startup")
M = max(CHAT)

tap(M, "close?:flex-url")
check("1. close confirmation")

tap(M, "close!:flex-url")
SES.remove("flex-url")          # systemctl already brought it down
check("2. closed: keep or delete")

tap(M, "new!:x")               # "Keep the files"
check("3. kept  <-- this is where it was left without buttons")

write("/close share-stories")
check("4. /close typed")
C = max(CHAT)
tap(C, "close!:share-stories")
SES.remove("share-stories")
check("5. second one closed")
tap(max(CHAT), "purge?:share-stories")
check("6. ask before deleting")

print("\n==>", "OK" if not failures else "FAILURES: " + "; ".join(failures))
import sys; sys.exit(1 if failures else 0)
