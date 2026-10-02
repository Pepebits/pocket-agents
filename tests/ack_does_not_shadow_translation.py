"""Inside handle(), 'def ack(t=None)' shadowed the translation
function t() for the whole BODY of ack(): a t("...") written in there
-for the toast text, say- failed with 'str' or 'None' object is not
callable instead of translating anything. The parameter was renamed so
the next person who touches that function does not run into it.

It is checked by reading the real AST -not a text grep- so that passing the
function does not depend on how the line is formatted.
"""
import ast
import harness as H

source = H.BOT_PATH.read_text(encoding="utf-8")
tree = ast.parse(source)


def find(node, name):
    for child in ast.walk(node):
        if isinstance(child, ast.FunctionDef) and child.name == name:
            return child
    return None


handle = find(tree, "handle")
assert handle, "cannot find handle() in the source"
ack = find(handle, "ack")
assert ack, "cannot find the ack() function nested inside handle()"

names = [a.arg for a in ack.args.args]
print("ack() parameters:", names)
assert "t" not in names, (
    "ack()'s parameter is called 't' and shadows the translation function "
    "for the whole body of ack()"
)

print("\n==> OK")
