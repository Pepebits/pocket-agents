import harness as H
bot = H.bot
# This tests api() itself: what gets faked is OPEN, the network layer.
bot.api = H.REAL_API
import io, urllib.error

class Resp(io.BytesIO):
    def __enter__(self): return self
    def __exit__(self, *a): return False

calls = []
def first_one_hangs(url, data, timeout=None):
    calls.append(timeout)
    if len(calls) == 1:
        raise TimeoutError("The read operation timed out")
    return Resp(b'{"ok":true,"result":true}')

bot.OPEN = first_one_hangs
r = bot.api("answerCallbackQuery", callback_query_id="x", text="hello")
print("tries:", calls)
assert r.get("ok"), r
assert len(calls) == 2, "a tap that does not get out on the first try is retried"
# Two tries have to fit in the ~15 s Telegram keeps the tap alive.
assert sum(calls) < 15, f"{sum(calls)} s: the tap would already have expired"
print("✓ the ack is retried, and both tries fit within the deadline")

calls.clear()
def always_fails(url, data, timeout=None):
    calls.append(timeout)
    raise urllib.error.URLError(ConnectionResetError(104, "reset"))
bot.OPEN = always_fails
assert bot.api("answerCallbackQuery", callback_query_id="x") == {}
assert len(calls) == 2, f"it is retried ONCE, not {len(calls)}"
print("✓ only one retry")

# A send is not repeated blindly: it could arrive twice.
calls.clear()
bot.api("sendMessage", chat_id=1, text="hello")
assert calls == [45], calls
print("✓ sendMessage is neither retried nor given a different deadline")
print("\n==> OK")
