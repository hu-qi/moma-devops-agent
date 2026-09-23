# GitHub Live Delivery E2E\n\nFirst controlled live proof of the DevOpsPilot product path:\n\nGitHub Issue -> OpenJiuwen AgentTeam on MoMA -> constrained edit -> independent verification -> exact local commit -> branch publish -> Pull Request -> GitHub Actions -> CI correlation -> Delivery Report.\n\nSafety boundary:\n- allowed: e2e/fixtures/github_delivery/app.py\n- forbidden: e2e/fixtures/github_delivery/test_app.py\n- max changed files: 1\n\nThe workflow triggers only for newly opened Issues whose title starts with [DevOpsPilot E2E].\n\nGitHub suppresses most recursive workflow events created by GITHUB_TOKEN, so the dedicated fixture CI is explicitly started through workflow_dispatch.

## GitHub write credential

The workflow prefers `DEVOPSPILOT_GITHUB_TOKEN` when configured and falls back to the repository `GITHUB_TOKEN`.

A dedicated token is needed when repository policy disables:

```text
Allow GitHub Actions to create and approve pull requests
```

The first live E2E proved that the default token can still publish the exact validated branch, while PR creation may be rejected by that repository-level policy.
