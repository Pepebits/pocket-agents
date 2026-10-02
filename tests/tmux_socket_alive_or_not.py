"""is_alive(): the socket EXISTING does not mean anyone is answering.

No other test touches is_alive() -they all replace it with a lambda- and
that was the crack: the 'Resume never shows up' bug could be reintroduced in
full without the suite saying a word. Here it is tested against real unix
sockets.
"""
import os, socket, pathlib
import harness as H
bot = H.bot

DIR = H.TMP / "tmux"
DIR.mkdir(exist_ok=True)
bot.TMUX_DIR = DIR

# 1. Not even a socket: there is no session.
print("  no file            :", bot.is_alive("ghost"), "(expected False)")
assert bot.is_alive("ghost") is False

# 2. A loose file, like the one tmux leaves when the server dies.
(DIR / "claude-dead").write_bytes(b"")
print("  regular file       :", bot.is_alive("dead"), "(expected False)")
assert bot.is_alive("dead") is False

# 3. A unix socket with NOBODY listening: it exists, and does not answer.
s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
s.bind(str(DIR / "claude-abandoned"))
s.close()                       # bind leaves the file; nobody serves it
exists = (DIR / "claude-abandoned").exists()
print(f"  abandoned socket   : {bot.is_alive('abandoned')} (exists={exists}, expected False)")
assert exists, "the file should still be there -- it is exactly the bug's case"
assert bot.is_alive("abandoned") is False, "an exists() would say True here"

# 4. A socket with someone listening: alive.
v = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
v.bind(str(DIR / "claude-alive")); v.listen(1)
print("  listening socket   :", bot.is_alive("alive"), "(expected True)")
assert bot.is_alive("alive") is True
v.close()

print("\n==> OK")
