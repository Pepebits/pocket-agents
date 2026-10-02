"""Hot reload: only when what is on disk is different AND compiles."""
import pathlib, shutil, time
import harness as H
bot = H.bot

tmp = H.TMP / "reload"; tmp.mkdir(exist_ok=True)
code, i18 = tmp / "bot.py", tmp / "i18n.json"
shutil.copy(H.BOT_PATH, code)
shutil.copy(H.REPO / "share/i18n.json", i18)
bot.SOURCES = (code, i18)
bot.STAMP = bot.stamp()

print("1) nothing touched     :", bot.reload_pending(), "(expected False)")

code.write_text(code.read_text() + "\n# one more line\n")
print("2) new, healthy code   :", bot.reload_pending(), "(expected True)")

bot.STAMP = bot.stamp()
code.write_text("def (:\n")          # does not compile
print("3) new, broken code    :", bot.reload_pending(), "(expected False)")
print("   and does not complain twice:", bot.reload_pending(), "(expected False)")

shutil.copy(H.BOT_PATH, code)
print("4) fixed               :", bot.reload_pending(), "(expected True)")

bot.STAMP = bot.stamp()
i18.write_text("{ this is not json")
print("5) broken i18n         :", bot.reload_pending(), "(expected False)")
shutil.copy(H.REPO / "share/i18n.json", i18)
print("6) fixed i18n          :", bot.reload_pending(), "(expected True)")

# Same size and same second: the mtime in ns tells them apart anyway.
bot.STAMP = bot.stamp()
t = code.read_text()
code.write_text(t[:-1] + "#")
print("7) same size           :", bot.reload_pending(), "(expected True)")
