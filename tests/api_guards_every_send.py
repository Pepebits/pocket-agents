"""Nothing leaves api() too long or with broken HTML -- wherever it comes from."""
import pathlib, os, sys, io, json, re, urllib.error
import harness as H
bot = H.bot
# The harness replaces bot.api with a fake Telegram; here we want to test
# api() ITSELF, so the original is restored and the network layer is faked.
bot.api = H.REAL_API

# A Telegram that behaves like the real one: it rejects what we measure.
sent, _n = [], [300]
class Resp(io.BytesIO):
    def __enter__(self): return self
    def __exit__(self, *a): return False

def fake(url, data, timeout=None):
    import urllib.parse
    p = dict(urllib.parse.parse_qsl(data.decode()))
    method = url.rsplit("/", 1)[-1]
    sent.append((method, p))
    txt = p.get("text", "")
    limit = bot.LIMITS.get(method)
    if limit and len(txt) > limit:
        raise urllib.error.HTTPError(url, 400, "Bad Request", {},
            io.BytesIO(json.dumps({"ok": False, "error_code": 400,
                "description": "Bad Request: message is too long"}).encode()))
    if p.get("parse_mode") == "HTML":
        stack = []
        if txt.rfind("<") > txt.rfind(">"):
            raise urllib.error.HTTPError(url, 400, "Bad Request", {},
                io.BytesIO(json.dumps({"ok": False, "error_code": 400,
                    "description": "Bad Request: can't parse entities: Unclosed start tag"}).encode()))
        for m in re.finditer(r"<(/?)([a-z]+)[^>]*>", txt):
            if m.group(1):
                if stack and stack[-1] == m.group(2): stack.pop()
                else: stack.append("ORPHAN")
            else: stack.append(m.group(2))
        if stack:
            raise urllib.error.HTTPError(url, 400, "Bad Request", {},
                io.BytesIO(json.dumps({"ok": False, "error_code": 400,
                    "description": "Bad Request: can't parse entities: Unmatched tag"}).encode()))
    for b in json.loads(p.get("reply_markup", '{"inline_keyboard":[]}')).get("inline_keyboard", []):
        for x in b:
            if len(str(x.get("callback_data", "")).encode()) > 64:
                raise urllib.error.HTTPError(url, 400, "Bad Request", {},
                    io.BytesIO(json.dumps({"ok": False, "error_code": 400,
                        "description": "Bad Request: BUTTON_DATA_INVALID"}).encode()))
    _n[0] += 1
    return Resp(json.dumps({"ok": True, "result": {"message_id": _n[0]}}).encode())

bot.OPEN = fake

# The cut has to fall INSIDE a tag, and that is the only place where it hurts:
# a poison that is merely long gets cut between padding and passes just as
# well with truncate() as with a bare [:n], so it proves nothing. The first
# version of this file had exactly that flaw and let the bug it came to catch
# live on.
CUT = bot.LIMITS["sendMessage"] - bot.MARGIN
POISONS = [
  # the tag starts just before the cut and ends after it
  ("tag at the cut", "x"*(CUT - 3) + "<code>abc</code>" + "x"*200),
  ("entity at the cut", "x"*(CUT - 2) + "&amp;" + "y"*200),
  ("unclosed bold", "<b>" + "y"*6000),
  ("orphan close", "z"*100 + "</b>" + "w"*50),
  ("giant pre", "<pre>" + "q"*9000 + "</pre>"),
  ("emoji galore", "🟢"*6000),
  ("deeply nested", "<b><i><code>" + "k"*5000 + "</code></i></b>"),
  # the cut falls between '<' and the tag name
  ("less-than at the end", "w"*(CUT - 1) + "<b>hello</b>"),
]
# A text that truncate() can leave valid has to arrive WITH its HTML. Arriving
# as plain text would be the safety net doing its job, yes -- but then the
# truncation is not doing its own, and the message loses its formatting. Only
# the 'orphan close' one comes broken from the start and no truncation can
# save it.
BROKEN_AT_SOURCE = {"orphan close"}
failures = []
for name, text in POISONS:
    for method, extra in (("sendMessage", {}),
                          ("editMessageText", {"message_id": 1}),
                          ("answerCallbackQuery", {"callback_query_id": "1"})):
        sent.clear()
        r = bot.api(method, chat_id=1, parse_mode="HTML", text=text, **extra)
        if not r.get("ok"):
            failures.append((name, method, r.get("description")))
            continue
        plain = "parse_mode" not in sent[-1][1]
        if plain and name not in BROKEN_AT_SOURCE and method != "answerCallbackQuery":
            failures.append((name, method, "arrived without HTML: the truncation broke it"))
    mark = "OK  " if not any(f[0] == name for f in failures) else "FAIL"
    print(f"  {mark} {name:22} tries={len(sent)}")

print("\n=== and with an impossible keyboard")
r = bot.api("sendMessage", chat_id=1, text="x", reply_markup={
    "inline_keyboard": [[{"text": "y", "callback_data": "c"*200}]]})
print("   200-byte callback_data ->", r.get("ok"), "|", r.get("description"))
print("   (api() cannot fix this one: NAME_OK prevents it at the source)")

print(f"\nfailures: {failures or 'none'}")
assert not failures, failures
print("\n==> OK")
