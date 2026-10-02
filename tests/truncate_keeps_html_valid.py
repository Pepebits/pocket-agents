"""truncate(): never leaves half-done HTML, whatever happens."""
import pathlib, os, html, re
import harness as H
bot = H.bot

CASES = [
  ("split tag",            "x"*3995 + "<code>abc</code>"),
  ("split entity",         "x"*3998 + "&amp;" + "y"*20),
  ("unclosed bold",        "<b>" + "x"*4100 + "</b>"),
  ("nested",               "<b><code>" + "x"*4100 + "</code></b>"),
  ("long pre",             "<pre>" + "x"*5000 + "</pre>"),
  ("right at the limit",   "x"*4000),
  ("short",                "<b>hello</b>"),
  ("all emoji",            "🟢"*4100),
  ("close without open",   "x"*3990 + "</b>" + "y"*30),
]
for name, text in CASES:
    r = bot.truncate(text, 4000)
    # Is there any '<' without its '>' or '&' without its ';'?
    half = r.rfind("<") > r.rfind(">") or r.rfind("&") > r.rfind(";")
    # Balanced?
    stack, ok = [], True
    for m in re.finditer(r"<(/?)([a-z]+)[^>]*>", r):
        if m.group(1):
            if stack and stack[-1] == m.group(2): stack.pop()
            else: ok = False
        else: stack.append(m.group(2))
    state = "OK " if (not half and not stack and ok and len(r) <= 4100) else "BAD"
    print(f"  {state} {name:22} len={len(r):5} end={r[-14:]!r}")
    assert not half, f"{name}: half a token"
    assert not stack, f"{name}: unclosed tags {stack}"

print("\n=== strip_html()")
for t in ("<b>hello</b> &amp; <code>x</code>", "🟢 <pre>a &lt; b</pre>"):
    print(f"  {t!r}\n    -> {bot.strip_html(t)!r}")
print("\n==> OK")
