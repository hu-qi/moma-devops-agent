import sys

try:
    from a import compute_a
    result = compute_a()
    assert result == 30, f"Expected 30, got {result}"
    print("CI Verify Passed: 0")
    sys.exit(0)
except Exception as exc:
    sys.stderr.write(f"CI Verify Failed: {exc}\n")
    sys.exit(1)
