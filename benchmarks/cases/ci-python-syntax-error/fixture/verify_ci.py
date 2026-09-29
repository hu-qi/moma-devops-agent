import sys

try:
    from app import classify
    assert classify(5) == "positive"
    assert classify(-3) == "negative"
    assert classify(0) == "zero"
    print("CI Verify Passed: 0")
    sys.exit(0)
except Exception as exc:
    sys.stderr.write(f"CI Verify Failed: {exc}\n")
    sys.exit(1)
