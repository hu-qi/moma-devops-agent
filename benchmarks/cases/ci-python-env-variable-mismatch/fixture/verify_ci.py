import os
import sys

# CI sets APP_PORT=8080
os.environ["APP_PORT"] = "8080"
try:
    from config import get_port
    port = get_port()
    if port != 8080:
        sys.stderr.write(f"CI failed: expected port 8080, got {port}\n")
        sys.exit(1)
    print("CI Verify Passed: 8080")
    sys.exit(0)
except Exception as exc:
    sys.stderr.write(f"CI failed with exception: {exc}\n")
    sys.exit(1)
