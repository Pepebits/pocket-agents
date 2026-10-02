"""dispatch(): if handle() blows up AND the error notice itself blows up
too (send() with no network, Telegram down, whatever), the exception must
not escape main()'s loop and take the whole bot down.

The real bug: 'send(t("internal_err", ...))' in dispatch()'s error handler
was not guarded. A notice that itself fails is exactly what you would expect
when something is already going wrong (the same reason handle() blew up),
and before, that took the whole process down with it.
"""
import harness as H
bot = H.bot
bot.sessions = lambda: []


def broken_handle(u):
    raise RuntimeError("boom")


def broken_send(*a, **k):
    raise RuntimeError("this does not get out either")


bot.handle = broken_handle
bot.send = broken_send

u = {"update_id": 5, "callback_query": {"id": "x", "from": {"id": bot.CHAT},
                                        "data": "status"}}
try:
    offset = bot.dispatch([u], 0)
except Exception as e:
    raise AssertionError(f"the exception escaped dispatch(): {e!r}")

print("offset:", offset)
assert offset == 6, "the offset has to move forward even if everything else fails"

print("\n==> OK")
