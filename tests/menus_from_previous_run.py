from harness import *
from harness import _next

SES = ["a", "b", "c"]
bot.sessions = lambda: list(SES)
bot.blocked = lambda: set()
bot.login_days = lambda s: 30

bot.send("one"); bot._reply_to = None
bot.send("two"); bot._reply_to = None
bot.send("three"); bot._reply_to = None
dump("three messages in a row")

LOG.clear()
SES.append("d")                       # the menu changes
bot.refresh_menus()
dump("after refresh_menus")
print("  API calls:", LOG)
bad = [m for m in menus_on_screen() if m not in bot.MENUS]
print("\n==> live menus:", menus_on_screen(), "| MENUS:", list(bot.MENUS),
      "| orphans painted:", bad)
