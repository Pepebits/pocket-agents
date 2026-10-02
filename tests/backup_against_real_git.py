"""backup_status(): real repos, made with real git."""
import os, pathlib, subprocess, shutil, time
import harness as _H                  # sets the fake HOME and loads the bot
ROOT = _H.TMP / "backup"
(ROOT / "dev").mkdir(parents=True)

def sh(*a, cwd=None):
    return subprocess.run(a, cwd=cwd, capture_output=True, text=True)

def repo(name, with_remote=True):
    d = ROOT / "dev" / name; d.mkdir(parents=True)
    sh("git", "init", "-qb", "main", cwd=d)
    sh("git", "config", "user.email", "t@t"); sh("git", "config", "user.name", "t", cwd=d)
    sh("git", "-C", str(d), "config", "user.email", "t@t")
    sh("git", "-C", str(d), "config", "user.name", "t")
    (d / "a.txt").write_text("1")
    sh("git", "-C", str(d), "add", "-A"); sh("git", "-C", str(d), "commit", "-qm", "one")
    if with_remote:
        bare = ROOT / "remotes" / (name + ".git"); bare.mkdir(parents=True)
        sh("git", "init", "-q", "--bare", str(bare))
        sh("git", "-C", str(d), "remote", "add", "origin", str(bare))
        sh("git", "-C", str(d), "push", "-q", "-u", "origin", "main")
    return d

clean    = repo("clean")
noremote = repo("noremote", with_remote=False)
behind   = repo("behind")
recent   = repo("recent")
stashed  = repo("stashed")

# behind: an unpushed commit, dated two days ago
old = str(int(time.time()) - 2 * 86400)
(behind / "b.txt").write_text("2")
sh("git", "-C", str(behind), "add", "-A")
subprocess.run(["git", "-C", str(behind), "commit", "-qm", "two"],
               env={**os.environ, "GIT_AUTHOR_DATE": old, "GIT_COMMITTER_DATE": old})
(behind / "c.txt").write_text("3")       # and something uncommitted

# recent: an unpushed commit from right now -> within the grace period
(recent / "b.txt").write_text("2")
sh("git", "-C", str(recent), "add", "-A"); sh("git", "-C", str(recent), "commit", "-qm", "two")

# stashed: an old stash
(stashed / "d.txt").write_text("4")
sh("git", "-C", str(stashed), "add", "-A")
subprocess.run(["git", "-C", str(stashed), "stash", "push", "-qm", "x"],
               env={**os.environ, "GIT_AUTHOR_DATE": old,
                    "GIT_COMMITTER_DATE": old})

H = _H
bot = H.bot
bot.HOME = ROOT                          # backup_status() looks at bot.HOME/dev/<ses>
bot.sessions = lambda: ["clean", "noremote", "behind", "recent", "stashed"]
bot.run_cmd = lambda cmd, timeout=300, cwd=None: (
    lambda r: (r.returncode, (r.stdout + r.stderr).strip()))(
    subprocess.run(cmd, capture_output=True, text=True, timeout=timeout))

for f in bot.backup_status():
    print(f"  {f['ses']:11} level={f['level']} push={str(f['push']):5} "
          f"dirty={f['dirty']} {f['parts']}")

print("\n--- report")
txt, kb = bot.backup_text()
print(txt)
print("buttons:", [b["text"] for r in kb["inline_keyboard"] for b in r])

# --- branch with no upstream
sh("git", "-C", str(recent), "checkout", "-qb", "loose")
(recent / "e.txt").write_text("5")
sh("git", "-C", str(recent), "add", "-A"); sh("git", "-C", str(recent), "commit", "-qm", "three")
f = [x for x in bot.backup_status() if x["ses"] == "recent"][0]
print("\n--- branch with no upstream:", f["level"], f["parts"])
assert f["level"] == 2

# --- the push button, against the real bare repo
bot.run_live = bot.run_cmd
H.CHAT.clear()
bot.push("behind")
print("--- push:", H.CHAT[max(H.CHAT)]["text"][:60])
f = [x for x in bot.backup_status() if x["ses"] == "behind"][0]
print("    after pushing:", f["level"], f["parts"], "(expected 0, only the uncommitted part is left)")
assert f["level"] == 0

# --- a push that fails does not lie
sh("git", "-C", str(behind), "remote", "set-url", "origin", "/does/not/exist.git")
(behind / "f.txt").write_text("6")
sh("git", "-C", str(behind), "add", "-A"); sh("git", "-C", str(behind), "commit", "-qm", "four")
H.CHAT.clear(); bot.push("behind")
print("--- broken push:", H.CHAT[max(H.CHAT)]["text"].splitlines()[0])

# --- the daily alert is stamped once
H.CHAT.clear()
mark = bot.STATE / "backup.alert"
mark.unlink(missing_ok=True)
bot.alert_backup(); n1 = len(H.CHAT)
bot.alert_backup(); n2 = len(H.CHAT)
print(f"--- daily alert: {n1} message, and the second time {n2} (does not repeat)")
assert n1 == 1 and n2 == 1
print("\n==> OK")
