"""A fake Telegram and a fake HOME, to test the whole bot.

Everything it writes goes to a temporary directory that is deleted on exit:
the tests must not be able to touch the ~/.config of whoever runs them, let
alone the muted-ports file or the saved menus of a running bot.
"""
import os, sys, json, pathlib, shutil, tempfile, atexit, importlib.util
import importlib.machinery

REPO = pathlib.Path(__file__).resolve().parent.parent
TMP = pathlib.Path(tempfile.mkdtemp(prefix="claude-rc-test-"))
atexit.register(shutil.rmtree, TMP, ignore_errors=True)

FAKE_HOME = TMP / "home"
(FAKE_HOME / ".local/share/claude-rc").mkdir(parents=True)
(FAKE_HOME / ".config/claude-rc").mkdir(parents=True)
(FAKE_HOME / "dev").mkdir()
shutil.copy(REPO / "share/i18n.json", FAKE_HOME / ".local/share/claude-rc/i18n.json")

# TG_CHAT=42 because several tests write that id by hand when they fabricate a
# tap. The bot demands credentials on import. A MADE-UP token on purpose: the
# harness replaces the network layer, so not one byte goes out to Telegram, and
# a test that slipped through with a real token would write to a real chat.
(FAKE_HOME / ".config/claude-rc-telegram").mkdir(parents=True)
(FAKE_HOME / ".config/claude-rc-telegram/config").write_text(
    "TG_TOKEN=0:TEST-NO-NETWORK\nTG_CHAT=42\n", encoding="utf-8")

os.environ["HOME"] = str(FAKE_HOME)
os.environ["XDG_STATE_HOME"] = str(TMP / "state")
# By default, the ports file lives in the fake HOME. A test that wants a
# different one sets it before importing this.
os.environ.setdefault("CLAUDE_RC_NET_ALLOW_FILE",
                      str(FAKE_HOME / ".config/claude-rc/net-allow"))
os.environ.setdefault("CLAUDE_RC_NET_ALLOW", "tcp:22")
sys.argv = ["claude-rc-bot", "--setup"]          # skips the lock

# No extension and no .py suffix: spec_from_file_location returns None for a
# name it does not recognise as a module, so the loader is given by hand.
BOT_PATH = REPO / "bin/claude-rc-bot"
spec = importlib.util.spec_from_loader(
    "bot", importlib.machinery.SourceFileLoader("bot", str(BOT_PATH)))
bot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bot)

# ---- fake Telegram -------------------------------------------------------
CHAT = {}          # mid -> {"text":..., "kb":[...]}
LOG = []
_next = [100]

def api(method, **p):
    LOG.append(method)
    if method == "sendMessage":
        _next[0] += 1
        mid = _next[0]
        CHAT[mid] = {"text": p.get("text",""), "kb": p.get("reply_markup")}
        return {"ok": True, "result": {"message_id": mid}}
    if method == "editMessageText":
        mid = p["message_id"]
        if mid not in CHAT:
            return {"ok": False, "error_code": 400, "description": "message to edit not found"}
        CHAT[mid] = {"text": p.get("text",""), "kb": p.get("reply_markup")}
        return {"ok": True, "result": {"message_id": mid}}
    if method == "editMessageReplyMarkup":
        mid = p["message_id"]
        if mid not in CHAT:
            return {"ok": False, "error_code": 400, "description": "message not found"}
        CHAT[mid]["kb"] = p.get("reply_markup")
        return {"ok": True}
    if method == "deleteMessage":
        return {"ok": bool(CHAT.pop(p["message_id"], None))}
    return {"ok": True, "result": []}

# The real one, for the tests that want to test api() itself -- the
# truncation, the HTML safety net -- rather than what sits on top of it. Those
# replace OPEN, which is the network layer, and keep the original api().
REAL_API = bot.api
bot.api = api
bot.run_cmd = lambda *a, **k: (0, "ok")
# The real one, for the test that checks run_live() itself -- draining the
# pipe while the process lives and the communicate() deadline after a kill.
REAL_RUN_LIVE = bot.run_live
bot.run_live = lambda *a, **k: (0, "ok")

def is_menu_kb(kb):
    rows = (kb or {}).get("inline_keyboard") or []
    return any(b.get("callback_data","").startswith("login:") or "disabled" in b
               for r in rows for b in r)

def menus_on_screen():
    return [m for m, v in CHAT.items() if is_menu_kb(v["kb"])]

def keyboards_on_screen():
    return [m for m, v in CHAT.items()
            if ((v["kb"] or {}).get("inline_keyboard") or [])]

def dump(tag):
    print(f"\n--- {tag}")
    for m, v in sorted(CHAT.items()):
        n = len(((v["kb"] or {}).get("inline_keyboard") or []))
        print(f"  [{m}] rows={n:<2} {v['text'][:52].splitlines()[0] if v['text'] else ''}")
    print(f"  menus on screen: {menus_on_screen()}")
