"""Resolving a volume's button does not pay for the 3.5 s 'docker system df -v'."""
import harness as H
bot = H.bot
calls = []
def run_cmd(cmd, timeout=300, cwd=None):
    calls.append(" ".join(cmd))
    if cmd[:3] == ["docker", "volume", "ls"]:
        return 0, "vol_a\nvol_b"
    return 0, ""
bot.run_cmd = run_cmd
bot.send = lambda *a, **k: None
k = bot.short_key("vol_a")
bot.ask_volume(k)
print("  calls:", calls)
assert not any("system df" in c for c in calls), "pays for the whole df to resolve a name"

print("\n--- and /disk launches the two 'system df' at once, not one after the other")
import time
launched = []
_popen = bot.subprocess.Popen
class Fake:
    def __init__(self, cmd, **k): launched.append((time.time(), cmd)); self.returncode = 0
    def communicate(self, timeout=None): time.sleep(0.3); return ("", None)
bot.subprocess.Popen = Fake
bot.run_cmd = lambda *a, **k: (0, "")
t0 = time.time(); bot.disk_text(); dt = time.time() - t0
bot.subprocess.Popen = _popen
print(f"  {len(launched)} launched, {launched[-1][0]-launched[0][0]:.2f}s apart; total {dt:.2f}s")
assert len(launched) == 2, launched
assert launched[-1][0] - launched[0][0] < 0.1, "the second one waited for the first"
print("\n==> OK")
