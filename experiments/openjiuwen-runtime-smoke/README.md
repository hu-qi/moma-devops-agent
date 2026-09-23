# OpenJiuwen Runtime Surface Smoke

This experiment has no model dependency and no credentials.

It verifies what is **actually importable from the installed OpenJiuwen distribution**, specifically:

- DeepAgent public factory
- Runner
- AgentTeam specs
- RSI / AutoHarness
- evaluator / optimizer / artifact provider surfaces

It also records the exact installed package version and callable signatures.

## Why

The GitHub mirror, GitCode upstream and PyPI release can temporarily differ. DevOpsPilot should make decisions based on the exact runtime used by the build.

## Local

```bash
pip install openjiuwen
python experiments/openjiuwen-runtime-smoke/main.py
```

Or configure an exact source:

```bash
pip install "openjiuwen==<version>"
python experiments/openjiuwen-runtime-smoke/main.py
```

## CI

Run the **Technical Spike** GitHub Actions workflow.

Set optional repository variable:

```text
OPENJIUWEN_INSTALL_SPEC
```

Examples:

```text
openjiuwen
openjiuwen==0.1.19
git+https://<official-source>/openJiuwen/agent-core.git@<tag-or-commit>
```

The workflow uploads the runtime surface as an artifact so the result becomes reproducible research evidence.
