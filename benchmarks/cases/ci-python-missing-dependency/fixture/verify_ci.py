import sys

try:
    from app import compute
    result = compute([1, 2, 3, 4])
    assert result == 10
    print("CI Verify Passed: 0")
    sys.exit(0)
except Exception as exc:
    sys.stderr.write(f"CI Verify Failed: {exc}\n")
    sys.exit(1)
