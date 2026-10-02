"""Edge cases of the report: nothing muted, port already closed, limit."""
import os, pathlib, time
os.environ["CLAUDE_RC_NET_ALLOW"] = ""          # no fixed ports from the unit

import harness as H
bot = H.bot
F = pathlib.Path(os.environ["CLAUDE_RC_NET_ALLOW_FILE"])
bot.sessions = lambda: []
bot.run_cmd = lambda cmd, *a, **k: (0, "")        # nothing listening

print("1) empty:", bot.ports_text()[0])
print("   buttons:", [b["text"] for r in bot.ports_text()[1]["inline_keyboard"] for b in r])

# a port muted three days ago that no longer listens
F.write_text(f"udp:5353\t# since {int(time.time()) - 3*86400}\nudp:6000\n")
txt, kb = bot.ports_text()
print("\n2) closed:\n" + txt)

# button limit
F.write_text("".join(f"tcp:{9000+i}\n" for i in range(15)))
txt, kb = bot.ports_text()
print("\n3) buttons:", sum(len(r) for r in kb["inline_keyboard"]) - 1, "(limit 12)")
print("   tail:", txt.splitlines()[-3])
