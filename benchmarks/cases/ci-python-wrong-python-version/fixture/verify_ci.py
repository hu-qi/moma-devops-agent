import sys
import ast

# Simulate CI target: Python 3.7 does not support the walrus operator (:=).
# We parse app.py's AST and reject any NamedExpr nodes.

try:
    with open("app.py", "r") as f:
        source = f.read()

    tree = ast.parse(source, filename="app.py")

    for node in ast.walk(tree):
        if isinstance(node, ast.NamedExpr):
            raise SyntaxError(
                f"app.py line {node.lineno}: walrus operator (:=) is not "
                "supported in target Python 3.7"
            )

    # If parsing passes, also verify the function works correctly
    ns = {}
    exec(compile(tree, "app.py", "exec"), ns)
    result = ns["filter_long_names"](["Al", "Bob", "Charlie", "Dave", "Evelyn"])
    assert result == [("Charlie", 7), ("Evelyn", 6)], f"Unexpected result: {result}"
    print("CI Verify Passed: 0")
    sys.exit(0)
except Exception as exc:
    sys.stderr.write(f"CI Verify Failed: {exc}\n")
    sys.exit(1)
