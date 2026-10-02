"""The disk report, against the real Docker."""
import subprocess, pathlib, os
import harness as H
bot = H.bot
bot.HOME = pathlib.Path("/home/dev")
bot.run_cmd = lambda cmd, timeout=300, cwd=None: (
    lambda r: (r.returncode, (r.stdout + r.stderr).strip()))(
    subprocess.run(cmd, capture_output=True, text=True, timeout=timeout))
bot.sessions = lambda: []
txt, kb = bot.disk_text()
print(txt)
print("\nbuttons:")
for r in kb["inline_keyboard"]:
    print("  ", [(b["text"], b["callback_data"]) for b in r])

# The short keys resolve back to the name, with no stored state
imgs = [n for n, _ in bot.unused_images()]
vols = [n for n, _ in bot.dangling_volumes()]
print("\nkey resolution:")
for n in (imgs[:1] + vols[:1]):
    k = bot.short_key(n)
    print(f"  {k} -> {bot.by_key(imgs + vols, k)}  (== {n}: {bot.by_key(imgs+vols,k)==n})")
print("  made-up key ->", bot.by_key(imgs + vols, "000000000000"))

# --- labels: never two the same, even if asked to
cases = ["php:8.4-cli", "php:8.3-cli",
         "reg.io/team/a-really-really-long-name-for-real:v1",
         "reg.io/other/a-really-really-long-name-for-real:v2",
         "a"*64, "b"*64]
e = bot.button_labels(cases)
print("\nlabels:")
for n, txt in e.items():
    print(f"  {txt!r:32} <- {n[:44]}")
assert len(set(e.values())) == len(cases), "two buttons with the same text!"
assert all(len(v) <= 23 for v in e.values()), [v for v in e.values() if len(v) > 23]
assert all(len(("rmv?:" + bot.short_key(n)).encode()) <= 64 for n in cases)
print("\n==> OK")
