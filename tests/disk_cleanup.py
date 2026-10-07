"""/disk shows and cleans what really filled the disk: Rust target/ dirs and
package caches.

Two weeks at 93-98 % came from 33.8 GB of target/ and 11 GB of npm cache,
cleaned by hand because /disk only looked at Docker. And the message has to
fit Telegram: past 4096 characters the end is cut off, and a button's
callback_data can't pass 64 bytes.
"""
import os, pathlib, stat, subprocess
import harness as H
bot = H.bot
REAL_BUILDING = bot.building      # before the stubs below replace it
DEV = bot.DEV_DIR

def real_run(cmd, timeout=300, cwd=None):
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return r.returncode, (r.stdout + r.stderr).strip()

def make_target(rel, size=1000):
    t = DEV / rel / "target"
    (t / "debug").mkdir(parents=True, exist_ok=True)
    (t / "CACHEDIR.TAG").write_text("Signature: 8a477f597d28d172789f06886806bc55\n")
    (t / "debug" / "blob").write_bytes(b"x" * size)
    return t

# ---- 1. found by cargo's mark, not by the name ----
a = make_target("calengine/services/rust-engine")
b = make_target("queue/gateway")
(DEV / "webapp/target").mkdir(parents=True)          # a folder that's just called target
found = bot.rust_targets()
print("found:", [bot.target_label(x) for x in found])
assert set(found) == {a, b}, found
print("✓ two target/ found, the plain folder ignored")

# ---- 2. worst case fits: 50 long-path targets, 40 images, 30 volumes ----
targets = [DEV / f"project-with-a-rather-long-name-{i:02d}/services/some-deep/rust-engine-{i}/target"
           for i in range(50)]
sizes = "\n".join(f"{(50 - i) * 10**9}\t{t}" for i, t in enumerate(targets))
sizes += "\n" + "\n".join(f"{3 * 10**8}\t{c[1]}" for c in bot.CACHES)
bot.rust_targets = lambda: targets
bot.target_age_days = lambda p: 12
bot.building = lambda p: str(p).endswith("rust-engine-0/target")   # the biggest is building
bot.run_parallel = lambda cmds, timeout=60: [(0, "Build Cache|1.2GB (40%)\nContainers|0B"), (0, ""), (0, sizes)]
bot.unused_images = lambda: [(f"registry.example.com/some-team/image-number-{i:02d}:1.2.3-very-long-tag", "1.1GB")
                             for i in range(40)]
bot.dangling_volumes = lambda with_size=True, df_v=None: [("f" * 64 if i % 2 else f"volume-{i}", "300MB")
                                                         for i in range(30)]
bot.run_cmd = lambda *a, **k: (0, "Size Used Avail Use%\n96G 86G 11G 89%")
txt, kb = bot.disk_text()
limit = bot.LIMITS["sendMessage"] - bot.MARGIN
buttons = [btn for row in kb["inline_keyboard"] for btn in row]
longest = max(len(btn["callback_data"].encode()) for btn in buttons)
print(f"text: {len(txt)} of {limit} chars · {len(buttons)} buttons · longest callback_data {longest} bytes")
assert len(txt) <= limit, f"{len(txt)} chars: Telegram would cut the end"
assert longest <= 64, longest
assert len(buttons) <= 20, len(buttons)
assert txt.count("🦀") <= bot.MAX_LINES + 1, "more target lines than the cap"
assert bot.t("dk_more", n=50 - bot.MAX_LINES) in txt
print("✓ worst case fits, with the '…and N more' line")

# The one that is building shows it, and has no button.
assert bot.t("dk_building") in txt
tgt_buttons = [btn for btn in buttons if btn["callback_data"].startswith("tgt:")]
assert len(tgt_buttons) == 3, tgt_buttons
assert all("-00" not in btn["text"] for btn in tgt_buttons), "a building project got a clean button"
assert any(btn["callback_data"] == "caches" for btn in buttons)
assert any(btn["callback_data"] == "rmi*?" for btn in buttons)
print("✓ building project without a button; caches and 'all images' buttons present")

# ---- 2b. "building" is a real cargo running inside the project ----
# A process whose name is cargo (a link to sleep) with its cwd in the project.
fake = DEV / "bin-cargo"; fake.mkdir(exist_ok=True)
(fake / "cargo").symlink_to("/bin/sleep")
proc = subprocess.Popen([str(fake / "cargo"), "30"], cwd=str(a.parent))
try:
    assert REAL_BUILDING(a), "a cargo running in the project was not seen"
    assert not REAL_BUILDING(b), "a cargo in another project counted here"
finally:
    proc.kill(); proc.wait()
assert not REAL_BUILDING(a), "still 'building' after cargo ended"
print("✓ a real cargo in the project blocks cleaning it, and only that one")

# ---- 3. cleaning a target ----
bot.run_cmd = real_run
bot.rust_targets = lambda: [a, b]
bot.building = lambda p: False
sent = []
bot.send = lambda text, *x, **k: sent.append(text)
bot.clean_target(bot.short_key(bot.target_label(a)))
print("clean:", sent[-1].splitlines()[0])
assert not a.exists() and b.exists(), "removed the wrong one"
bot.building = lambda p: True
bot.clean_target(bot.short_key(bot.target_label(b)))
assert b.exists() and "⏳" in sent[-1], "cleaned a project that was building"
print("✓ removes the right target/, and refuses while it builds")

# ---- 4. caches: read-only Go modules, npx in use ----
for _, path, _ in bot.CACHES:
    path.mkdir(parents=True, exist_ok=True)
    (path / "f").write_bytes(b"y" * 5000)
mod = bot.HOME / "go/pkg/mod/example.com/x@v1"
mod.mkdir(parents=True)
(mod / "a.go").write_text("package x")
for p in (mod / "a.go", mod, mod.parent):
    os.chmod(p, stat.S_IRUSR | stat.S_IXUSR if p.is_dir() else stat.S_IRUSR)
bot.shutil.which = lambda name: None       # never the real go: it could touch a real cache
bot.npx_in_use = lambda: True
bot.clean_caches()
print("caches:", sent[-1].replace("\n", " "))
left = [str(p) for _, p, _ in bot.CACHES if p.exists()]
assert left == [str(bot.HOME / ".npm/_npx")], left
assert bot.t("dk_npx_busy").strip() in sent[-1]
print("✓ every cache gone, read-only Go modules included; npx kept while in use")

# ---- 5. all images asks first ----
bot.unused_images = lambda: [("a:1", "1GB"), ("b:2", "500MB")]
H.CHAT.clear()
bot.send = H.bot.send = lambda text, *x, markup=None, **k: sent.append((text, markup))
bot.ask_all_images()
text, markup = sent[-1]
datas = [btn["callback_data"] for row in markup["inline_keyboard"] for btn in row]
assert datas == ["disk", "rmi*!"], datas
assert "2" in text and "1.5 GB" in text, text
print("✓ 'all images' asks, with count and size, before anything goes")

# ---- 6. the alert names the biggest three ----
bot.rust_targets = lambda: [b]
items = bot.reclaimable(sizes={str(b): 30 * 10**9, str(bot.CACHES[0][1]): 2 * 10**9},
                        images=[("a:1", "9GB")])
print("top:", [line for _, line in items])
assert [n for n, _ in items] == sorted((n for n, _ in items), reverse=True)
assert "queue/gateway" in items[0][1]
print("\n==> OK")
