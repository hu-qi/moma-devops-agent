# Provider Contract Smoke

Credential-free smoke test for DevOpsPilot's provider-neutral `SCMProvider` and `CIProvider` contracts.

The test intentionally uses fake providers. Its purpose is to protect the domain boundary before implementing GitHub, CNB, GitCode, AtomGit, GitLink or Gitee adapters.

## Run

```bash
PYTHONPATH=src python experiments/provider-contract-smoke/main.py
```

Expected:

```text
SCM_PROVIDER_CONTRACT_OK
CI_PROVIDER_CONTRACT_OK
```

This test validates structure only. Real provider adapters require separate credentialed integration tests.
