"""The reboot button only shows up if polkit grants it.

A button that cannot work is worse than no button: it looks like the machine
is broken. On this VPS polkit asks for a password, so the button would never
have worked -- and that was found out by trying pkcheck, not by reading.
"""
import harness as H
bot = H.bot
bot.sessions = lambda: []
bot.backup_status = lambda: []
bot.is_busy = lambda s: False

def with_polkit(allows):
    bot.can_reboot = lambda: allows
    txt, kb = bot.reboot_text()
    cbs = [b["callback_data"] for r in kb["inline_keyboard"] for b in r]
    # The text comes from i18n.json, in Spanish (the runner sets CLAUDE_RC_LANG=es) or English.
    says = "polkit" in txt or "contraseña" in txt or "password" in txt
    return cbs, says

cbs, says = with_polkit(True)
print("  grants      : buttons =", cbs)
assert "reboot!" in cbs, "does not offer to reboot when it can"
assert not says, "warns about polkit for no reason"

cbs, says = with_polkit(False)
print("  denies      : buttons =", cbs, "| explains it:", says)
assert "reboot!" not in cbs, "offers a button that is going to fail"
assert says, "removes it and does not say why"

cbs, says = with_polkit(None)
print("  unknown     : buttons =", cbs)
assert "reboot!" in cbs, "without knowing, better to offer it and report the failure"

print("\n==> OK")
