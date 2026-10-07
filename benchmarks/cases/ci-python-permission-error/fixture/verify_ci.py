import sys
import os
import tempfile

# verify_ci.py -- checks that save_report handles PermissionError gracefully
# by falling back to a temp directory instead of crashing.

try:
    from app import save_report

    # First, verify it handles the unwritable path gracefully (returns fallback)
    result = save_report("CI test report", path="/readonly/report.txt")

    if result.get("status") != "saved":
        raise AssertionError(f"Expected status 'saved', got {result.get('status')!r}")

    # The path must NOT be /readonly/report.txt (that can't work in CI)
    if result["path"] == "/readonly/report.txt":
        raise AssertionError(
            "save_report wrote to /readonly/report.txt -- "
            "expected a fallback path"
        )

    # The fallback file must actually exist
    if not os.path.isfile(result["path"]):
        raise AssertionError(
            f"Fallback path {result['path']} does not exist on disk"
        )

    # Verify content
    with open(result["path"], "r") as f:
        content = f.read()
    assert content == "CI test report", f"Wrong content: {content!r}"

    # Cleanup
    os.remove(result["path"])

    print("CI Verify Passed: 0")
    sys.exit(0)
except Exception as exc:
    sys.stderr.write(f"CI Verify Failed: {exc}\n")
    sys.exit(1)
