import harness as H
bot = H.bot
# This tests api() itself, not what sits on top of it: the original is
# restored and what gets faked is OPEN, the network layer.
bot.api = H.REAL_API
import urllib.request, urllib.error, io, json as _json

captured = {}
class Resp(io.BytesIO):
    def __enter__(self): return self
    def __exit__(self, *a): return False

def fake_ok(url, data, timeout=None):
    captured['url'] = url; captured['body'] = data.decode(); captured['sock'] = timeout
    return Resp(b'{"ok":true,"result":[]}')

bot.OPEN = fake_ok
r = bot.api("getUpdates", _sock=25, timeout=20, offset=7)
print("body sent:", captured['body'])
print("socket timeout:", captured['sock'])
assert "_sock" not in captured['body'], "_sock is being sent to Telegram!"
assert captured['sock'] == 25
assert "timeout=20" in captured['body'] and "offset=7" in captured['body']
assert bot.LAST_FAILURE is None
print("✓ _sock does not travel in the body, and it does set the socket")

def fake_timeout(url, data, timeout=None):
    raise TimeoutError("The read operation timed out")
bot.OPEN = fake_timeout
bot.api("getUpdates", _sock=25, timeout=20)
print("after timeout:", bot.LAST_FAILURE)
assert bot.LAST_FAILURE == "timeout"

def fake_reset(url, data, timeout=None):
    raise urllib.error.URLError(ConnectionResetError(104, "Connection reset by peer"))
bot.OPEN = fake_reset
bot.api("getUpdates")
print("after reset:", bot.LAST_FAILURE)
assert bot.LAST_FAILURE == "network"

bot.OPEN = fake_ok
bot.api("getMe")
assert bot.LAST_FAILURE is None
print("✓ it is cleared after a good call")
print("\n==> OK")
