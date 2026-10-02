"""run_live(): two ways to hang by not reading the pipe while the process
is alive. The bot is single-threaded -- while it is stuck here it does not
answer anything.

(a) More than ~64 KiB of output fills the pipe buffer; the child blocks
    writing and never finishes on its own, even if the work was already
    done. Measured before the fix: "yes hello | head -c 200000; exit 0" with
    timeout=5 came back with rc=1 and "[timeout]" at 5.0 s instead of
    finishing in milliseconds.
(b) After p.kill(), a p.communicate() with no deadline waits for ALL the
    processes that inherited stdout to close it, grandchildren included.
    Measured before the fix: "sleep 20 & exec sleep 999" with timeout=2 took
    20.0 s instead of ~2-4 s.
"""
import time
import harness as _H

bot = _H.bot
run_live = _H.REAL_RUN_LIVE          # the real one, not the harness stub
bot.api = lambda *a, **k: {"ok": True}       # the "typing..." must not go to the network

# --- (a) lots of output must not read as a timeout
t0 = time.time()
rc, out = run_live(["sh", "-c", "yes hello | head -c 200000; exit 0"], timeout=5)
dt = time.time() - t0
print(f"large output: rc={rc} len={len(out)} t={dt:.2f}s")
assert rc == 0, "a process that ends fine must not be reported as a timeout"
assert "[timeout]" not in out
assert len(out) >= 199999
assert dt < 3, f"took {dt:.2f}s because of the full pipe buffer"

# --- (b) a grandchild alive after the kill must not stretch the timeout
t0 = time.time()
rc, out = run_live(["sh", "-c", "sleep 20 & exec sleep 999"], timeout=2)
dt = time.time() - t0
print(f"grandchild after kill: rc={rc} out={out!r} t={dt:.2f}s")
assert rc == 1
assert out.endswith("[timeout]")
assert dt < 10, f"took {dt:.2f}s waiting for the grandchild instead of the communicate() deadline"

print("\n==> OK")
