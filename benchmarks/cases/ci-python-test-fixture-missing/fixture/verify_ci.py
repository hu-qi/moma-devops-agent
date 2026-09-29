import sys
import subprocess

try:
    result = subprocess.run(
        [sys.executable, "test_app.py"],
        capture_output=True, text=True, timeout=10
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"test_app.py failed (exit {result.returncode}): "
            f"{result.stderr.strip()}"
        )
    print("CI Verify Passed: 0")
    sys.exit(0)
except Exception as exc:
    sys.stderr.write(f"CI Verify Failed: {exc}\n")
    sys.exit(1)
