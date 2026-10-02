"""Outdated is the one that started with a LOWER version, not the one whose
binary is newer.

Comparing the binary's date does not work: Claude Code auto-updates and
rewrites its package every few minutes without changing version -- measured,
three different mtimes in twenty minutes with the same 2.1.280 inside. A
date-based heuristic would mark all six sessions as outdated forever.
"""
import harness as H
bot = H.bot

SESSIONS = ["old", "current", "future", "no_file", "empty"]
bot.sessions = lambda: SESSIONS
bot.is_busy = lambda s: s == "old"
bot.run_cmd = lambda cmd, timeout=300, cwd=None: (
    (0, "2.1.280 (Claude Code)") if cmd[:2] == ["claude", "--version"] else (1, ""))

VERSIONS = {"old": "2.1.9", "current": "2.1.280", "future": "2.2.0",
            "empty": None, "no_file": None}
bot.version_of = lambda s: VERSIONS.get(s)

outdated = bot.outdated_sessions()
print("  outdated:", outdated)
assert outdated == [("old", True)], outdated
print("  2.1.9 < 2.1.280 as numbers, not as text ✓")
print("  the one with no record is not made up ✓")
print("  a version newer than the one on disk is not falling behind ✓")

print("\n--- without being able to ask the version on disk, nothing is claimed")
bot.run_cmd = lambda cmd, timeout=300, cwd=None: (1, "")
assert bot.outdated_sessions() == []
print("  ok")

print("\n--- the button only shows up if some session is idle")
bot.run_cmd = lambda cmd, timeout=300, cwd=None: (
    (0, "2.1.280") if cmd[:2] == ["claude", "--version"] else (1, ""))
bot.claude_version = lambda: ("2.1.280", "2.1.280")
bot.codex_version = lambda: (None, None)
_, kb = bot.updates_text()
cbs = [b["callback_data"] for r in kb["inline_keyboard"] for b in r]
print("  only 'old' outdated and it is busy ->", cbs)
assert "up_stale" not in cbs, "offers to restart when the only one is working"

bot.is_busy = lambda s: False
txt, kb = bot.updates_text()
cbs = [b["text"] for r in kb["inline_keyboard"] for b in r]
print("  now idle ->", cbs)
assert any("1" in c for c in cbs), cbs
print("\n--- restarting does NOT touch the ones that are working")
BUSY = {"busy_old"}
SES2 = ["idle_old", "busy_old", "up_to_date"]
bot.sessions = lambda: SES2
bot.is_busy = lambda s: s in BUSY
V2 = {"idle_old": "2.1.1", "busy_old": "2.1.1", "up_to_date": "2.1.280"}
bot.version_of = lambda s: V2.get(s)
bot.run_cmd = lambda cmd, timeout=300, cwd=None: (
    (0, "2.1.280") if cmd[:2] == ["claude", "--version"] else (1, ""))
restarted = []
bot.run_live = lambda cmd, timeout=300, cwd=None: (restarted.append(cmd[-1]), (0, "ok"))[1]
H.CHAT.clear()
bot._reply_to = None
bot.restart_outdated()
text = " ".join(v["text"] for v in H.CHAT.values())
print("  restarted:", restarted)
assert restarted == ["claude@idle_old"], restarted
assert "busy_old" in text, "does not say which one it skipped"
print("  the busy one is mentioned and left alone ✓")

print("\n--- if ALL the old ones are working, it restarts none")
BUSY = {"idle_old", "busy_old"}
restarted.clear(); H.CHAT.clear(); bot._reply_to = None
bot.restart_outdated()
print("  restarted:", restarted or "none")
assert not restarted
assert any("⏭" in v["text"] for v in H.CHAT.values()), "does not explain it"
print("  and it explains instead of keeping quiet ✓")

print("\n==> OK")
