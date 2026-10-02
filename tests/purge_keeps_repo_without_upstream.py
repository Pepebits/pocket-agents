"""git_pending(): a repo with no remote, or with a remote but no upstream,
has to count as pending work -- otherwise purge() deletes it with
shutil.rmtree() believing it is already safe.

The real bug: 'git log --oneline @{u}..' exits with rc!=0 when the branch is
not tied to any remote branch (or there is no remote), and the old code only
looked at 'if rc == 0 and out.strip()', so that case read as [] -- nothing to
lose. A repo just created with 'git init' + one commit, with no remote, was
deleted whole when the purge button was tapped.
"""
import subprocess
import harness as _H

ROOT = _H.TMP / "purge"
(ROOT / "dev").mkdir(parents=True)


def sh(*a, cwd=None):
    subprocess.run(a, cwd=cwd, capture_output=True, text=True)


def repo_without_remote(name):
    d = ROOT / "dev" / name
    d.mkdir(parents=True)
    sh("git", "init", "-qb", "main", cwd=d)
    sh("git", "-C", str(d), "config", "user.email", "t@t")
    sh("git", "-C", str(d), "config", "user.name", "t")
    (d / "a.txt").write_text("1")
    sh("git", "-C", str(d), "add", "-A")
    sh("git", "-C", str(d), "commit", "-qm", "one")
    return d


def repo_with_remote_without_upstream(name):
    d = ROOT / "dev" / name
    d.mkdir(parents=True)
    sh("git", "init", "-qb", "main", cwd=d)
    sh("git", "-C", str(d), "config", "user.email", "t@t")
    sh("git", "-C", str(d), "config", "user.name", "t")
    bare = ROOT / "remotes" / (name + ".git")
    bare.mkdir(parents=True)
    sh("git", "init", "-q", "--bare", str(bare))
    sh("git", "-C", str(d), "remote", "add", "origin", str(bare))
    (d / "a.txt").write_text("1")
    sh("git", "-C", str(d), "add", "-A")
    sh("git", "-C", str(d), "commit", "-qm", "one")
    # no push -u ever: the local branch does not track origin/main
    return d


bot = _H.bot
bot.run_cmd = lambda cmd, timeout=300, cwd=None: (
    lambda r: (r.returncode, (r.stdout + r.stderr).strip()))(
    subprocess.run(cmd, capture_output=True, text=True, timeout=timeout))

no_remote = repo_without_remote("noremote")
no_upstream = repo_with_remote_without_upstream("noupstream")

missing_nr = bot.git_pending(no_remote)
missing_nu = bot.git_pending(no_upstream)
print("no remote:   ", missing_nr)
print("no upstream: ", missing_nu)

assert missing_nr, "a repo with no remote has to count as pending"
assert missing_nu, "a repo with a remote but no upstream has to count as pending"

# And with the RIGHT reason, not just "something pending": no remote is fixed
# by creating one, no upstream with a 'push -u', and the message points to
# each. Without this, the two branches cover for each other and breaking
# either one on its own goes unnoticed -- checked.
assert missing_nr == [_H.bot.t("pend_noremote")], missing_nr
assert missing_nu == [_H.bot.t("pend_noupstream")], missing_nu

# --- and purge() must delete neither of them
_H.CHAT.clear()
bot.sessions = lambda: []
for ses, d in [("noremote", no_remote), ("noupstream", no_upstream)]:
    bot.HOME = ROOT
    (ROOT / f".claude-{ses}")  # no need to create it
    bot.purge(ses, confirmed=True)
    assert d.exists(), f"purge() deleted {ses} with nothing pushed"

print("\n==> OK")
