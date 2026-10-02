import harness as H
bot = H.bot
bot.api = H.REAL_API
import io, sys, contextlib

err = io.StringIO()
def drop(url, data, timeout=None):
    raise ConnectionError("Remote end closed connection without response")

# An isolated drop of the long-poll leaves no trace in the journal...
bot.OPEN = drop
with contextlib.redirect_stderr(err):
    bot.api("getUpdates", timeout=20)
assert err.getvalue() == "", err.getvalue()
assert "Remote end closed" in bot.LAST_ERROR
print("✓ api() keeps quiet about the getUpdates drop and keeps the text")

# ...but any other method's does.
with contextlib.redirect_stderr(err):
    bot.api("sendMessage", chat_id=1, text="x")
assert "api error: sendMessage" in err.getvalue()
print("✓ the other methods still log their error")

now = [0.0]
o = bot.Outages(clock=lambda: now[0])
err = io.StringIO()
with contextlib.redirect_stderr(err):
    # The normal drop: an isolated one, and the next round goes fine.
    assert o.fail("drop") is False, "the first failure does not sleep"
    o.recover()
    assert err.getvalue() == ""
    # A real outage is logged once, and so is its recovery.
    o.fail("a")
    for e in ("b", "c", "d", "e"):
        assert o.fail(e) is True
    o.recover()
lines = err.getvalue().splitlines()
print("\n".join(lines))
assert lines == ["getUpdates: 3 consecutive failures, the last one: c",
                 "getUpdates: back after 5 consecutive failures"], lines
print("✓ the outage is reported once when it starts and once when it ends")

# And once a day, how many drops there were: without this you could not see
# whether the network is getting worse.
err = io.StringIO()
with contextlib.redirect_stderr(err):
    now[0] = 24 * 3600 + 1
    o.fail("x")
    o.recover()
    now[0] += 3600
    o.recover()
print(err.getvalue().strip())
assert err.getvalue() == "getUpdates: 7 network drops in 24 h\n", err.getvalue()
print("✓ daily summary, only once")
print("\n==> OK")
