# GitHub Reference Adapter Smoke

Credential-free behavioral test for the first real DevOpsPilot provider adapter.

It validates:
- Repository mapping
- Issue mapping
- PR create/read mapping
- PR review mapping
- Webhook normalization + HMAC SHA-256 verification
- GitHub Actions run normalization
- Job log collection
- Retry-failed behavior
- Artifact mapping

The fake GitHub client exists only in this experiment. Production adapter code depends on the `GitHubAPIClient` protocol.

## Run

```bash
PYTHONPATH=src python experiments/github-reference-adapter-smoke/main.py
```
