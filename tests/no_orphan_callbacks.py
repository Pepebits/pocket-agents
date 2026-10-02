"""The callback chain is still whole: nothing falls into the 'I don't know'."""
import pathlib, os
import harness as H
bot = H.bot
bot.sessions = lambda: ["travel"]
bot.login_days = lambda s: 30
bot.is_alive = lambda s: True
bot.blocked = lambda: set()
for n in ("send_status","send_ports","send_backup","send_reboot",
          "send_disk","send_codex","send_updates","launch_login","refresh_menus",
          "pause","resume","close_session","push","codex_restart","codex_stop",
          "codex_start","codex_login","codex_pair","net_mute",
          "net_unmute","remove_image","ask_volume","remove_volume",
          "update_claude","update_codex","reboot","purge","clone",
          "create_repo","init_empty","bring_up"):
    if hasattr(bot, n):
        setattr(bot, n, lambda *a, **k: None)

DATA = ["status","update","up_claude","up_codex","codex","cx_stop","cx_start",
        "cx_restart","cx_login","cx_pair","disk","rmi:abc","rmv?:abc","rmv!:abc",
        "backup","push:travel","ports","mute:tcp:1","unmute:tcp:1","reboot",
        "reboot!","pause:travel","resume:travel","pick:l:travel","pick:c:travel",
        "close?:travel","close!:travel","purge?:travel","purge!:travel",
        "new!:x","login:travel"]
off, orphans = 0, []
for i, d in enumerate(DATA):
    H.CHAT.clear()
    off = bot.dispatch([{"update_id": 5000+i, "callback_query": {
        "id": str(i), "from": {"id": bot.CHAT}, "data": d,
        "message": {"message_id": 1}}}], off)
    texts = " ".join(v["text"] for v in H.CHAT.values())
    # The bot's reply comes from i18n.json, which the runner loads in Spanish.
    if "No conozco este bot" in texts or "no conozco este bot" in texts.lower():
        orphans.append(d)
print("callbacks tried:", len(DATA))
print("fell into 'I don't know':", orphans or "none ✓")
assert not orphans, orphans
print("\n==> OK")
