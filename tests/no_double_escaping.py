"""t() already escapes all its values (see its docstring). Passing it a value
the caller has already escaped with html.escape() escapes it twice: an '&'
becomes '&amp;' and then '&amp;amp;', which is what the user reads in
Telegram instead of a real '&'.

net_mute()/net_unmute() are a real case and easy to trigger: an invalid port
with a character HTML has to escape is enough.
"""
import harness as H
bot = H.bot

H.CHAT.clear()
bot.net_mute("tcp:1&2")               # does not match PORT_OK -> port_bad
txt = H.CHAT[max(H.CHAT)]["text"]
print("net_mute:", txt)
assert "&amp;" in txt, "the '&' has to arrive escaped once"
assert "&amp;amp;" not in txt, f"double escaped: {txt!r}"

H.CHAT.clear()
bot.net_unmute("udp:3&4")             # does not match either -> port_bad
txt = H.CHAT[max(H.CHAT)]["text"]
print("net_unmute:", txt)
assert "&amp;" in txt
assert "&amp;amp;" not in txt, f"double escaped: {txt!r}"

print("\n==> OK")
