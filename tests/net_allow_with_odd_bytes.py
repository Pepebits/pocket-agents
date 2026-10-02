"""read_allow()/mute()/unmute(): a ports file edited by hand and saved in an
encoding that is not UTF-8 must not bring anything down.

The real bug: 'NET_ALLOW_F.read_text(encoding="utf-8")' lived inside a
'try/except OSError', and UnicodeDecodeError is not an OSError -it is a
ValueError. A stray latin-1 byte (an accent typed with an editor that does
not save in UTF-8, for example) killed /ports and the mute buttons entirely.
read_allow()'s docstring promises that "one crooked line must not leave the bot
without a list"; with bytes that do not even decode, it used to.
"""
import os, pathlib
import harness as H
bot = H.bot
F = pathlib.Path(os.environ["CLAUDE_RC_NET_ALLOW_FILE"])

# 'ó' in latin-1 is a byte UTF-8 cannot decode as valid text.
F.write_bytes("tcp:22\t# revisi\xf3n manual\n".encode("latin-1"))

out = bot.read_allow()
print("read_allow():", out)
assert out == [], "a file that does not decode must not kill the list, only empty it"

# mute() must not blow up nor lose the attempt to add the new port
ok = bot.mute("tcp:9999")
print("mute():", ok)
assert ok is True

# unmute() on a broken file must not blow up either
F.write_bytes("tcp:22\t# revisi\xf3n manual\n".encode("latin-1"))
ok = bot.unmute("tcp:22")
print("unmute():", ok)
assert ok is False, "it could not read the list, so it cannot know what to remove"

print("\n==> OK")
