"""Every tap leaves a line with how long it took -- and never the user's text.

The bursts of "query is too old" on 19 and 22 September could not be
explained: the bot went ~20 s without answering and the journal only had
errors. And what CANNOT happen when fixing it: when the bridge is waiting for
a login code, the message IS the code.
"""
import io, sys, contextlib, time
import harness as H
bot = H.bot
bot.sessions = lambda: []
bot.waiting = lambda: ["travel"]          # the bridge is waiting for a code

def msg(uid, txt):
    return {"update_id": uid, "message": {"message_id": uid, "text": txt,
            "chat": {"id": bot.CHAT}, "from": {"id": bot.CHAT}, "date": 0}}
def tap(uid, data):
    return {"update_id": uid, "callback_query": {"id": str(uid),
            "from": {"id": bot.CHAT}, "data": data, "message": {"message_id": 1}}}

bot.send_status = lambda *a, **k: None
_slow = lambda *a, **k: time.sleep(bot.SLOW + 0.2)
bot.send_disk = _slow

err = io.StringIO()
with contextlib.redirect_stderr(err):
    bot.dispatch([msg(1, "SECRET-4F7K-CODE"), msg(2, "/status something"),
                  tap(3, "disk")], 0)
log = err.getvalue()
print(log)
assert "SECRET" not in log, "the login code has ended up in the journal!"
assert "message" in log, "the message is not even logged"
assert "command /status" in log and "something" not in log, "of the command, only the name"
assert "SLOW tap disk" in log, "does not mark the slow tap"
assert log.count("\n") == 3, "one line per update"
print("==> OK")
