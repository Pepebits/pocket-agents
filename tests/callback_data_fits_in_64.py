"""No callback_data goes over 64 bytes, with the longest name possible."""
import pathlib, os, re
import harness as H
bot = H.bot

longest = "a" + "b"*55                   # 56, the most NAME_OK allows
assert bot.NAME_OK.match(longest), "the maximum should be accepted"
assert not bot.NAME_OK.match(longest + "c"), "one more should be rejected"
print(f"longest name accepted: {len(longest)} characters")

bot.sessions = lambda: [longest, "travel"]
bot.login_days = lambda s: 30
bot.is_alive = lambda s: True
bot.blocked = lambda: set()

def check(name, kb):
    bad = []
    for r in kb.get("inline_keyboard", []):
        for b in r:
            d = b.get("callback_data")
            if d and len(d.encode()) > 64:
                bad.append((d[:24]+"…", len(d.encode())))
    print(f"  {name:22} buttons={sum(len(r) for r in kb.get('inline_keyboard',[]))} "
          f"| over 64: {bad or 'none'}")
    return bad

bad = []
bad += check("menu()", bot.menu())
bad += check("pick_keyboard('c')", bot.pick_keyboard("c"))
bad += check("pick_keyboard('l')", bot.pick_keyboard("l"))
bad += check("new_keyboard()", bot.new_keyboard(longest))
assert not bad, bad

# And the ones that carry no session name
for d in (f"mute:udp:65535", "rmi:" + "f"*12, "rmv!:" + "f"*12, "cx_restart", "up_claude"):
    assert len(d.encode()) <= 64, d
print("  fixed callbacks          | all under 64 ✓")
print("\n==> OK")
