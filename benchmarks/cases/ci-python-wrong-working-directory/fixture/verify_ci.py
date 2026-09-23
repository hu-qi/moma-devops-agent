from pathlib import Path


workflow = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
if "working-directory: service" not in workflow:
    raise SystemExit("CI workflow must run commands from the service directory")

if not Path("service/test_app.py").exists():
    raise SystemExit("fixture is invalid: service/test_app.py is missing")
