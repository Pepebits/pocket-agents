"""first_getupdates(): if the startup getUpdates fails because of the
network, the bot cannot carry on as if the backlog were clean.

The real bug: 'api("getUpdates", timeout=0).get("result") or []' treats two
different things the same -- "I asked and there was nothing" (result=[]) and
"I could not even ask" (api() returns {} on a network failure, with no "ok"
key). With the second case read as "nothing pending", the offset stayed at
0, and the first getUpdates(offset=0) of main()'s loop asks for "everything
unconfirmed" -and THAT does get dispatched, running old callbacks. Exactly
what handle_backlog() exists to prevent.
"""
import harness as H
bot = H.bot

calls = []


def api_that_fails_twice(method, **p):
    calls.append(method)
    if len(calls) <= 2:
        return {}          # like the real api() on a network failure
    return {"ok": True, "result": [{"update_id": 7, "message": {"text": "hello"}}]}


bot.api = api_that_fails_twice
bot.time.sleep = lambda *a: None    # the test has no reason to really wait

result = bot.first_getupdates()
print("getUpdates calls:", len(calls), "result:", result)
assert len(calls) == 3, "it had to retry until it got a real answer"
assert result == [{"update_id": 7, "message": {"text": "hello"}}]

# And if there really is nothing pending (result=[] with ok=True), no retry.
calls.clear()
bot.api = lambda method, **p: (calls.append(method), {"ok": True, "result": []})[1]
result = bot.first_getupdates()
assert len(calls) == 1, "a real result=[] must not retry"
assert result == []

print("\n==> OK")
