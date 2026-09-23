# MoMA × OpenJiuwen PoC

Purpose: validate that a MoMA endpoint can be consumed through OpenJiuwen's generic OpenAI-compatible model client and then used by DeepAgent.

## Requirements

- Python 3.11–3.13
- OpenJiuwen Agent Core
- a valid MoMA API credential and model ID

The exact OpenJiuwen build is intentionally configurable because public mirrors / package channels may not publish new versions at the same time.

## Local Environment

```bash
export MOMA_API_BASE="<value from MoMA console/docs>"
export MOMA_API_KEY="<secret>"
export MOMA_MODEL="<model id>"
```

Do not commit credentials.

## GitHub Actions

Recommended repository configuration:

### Secret
```text
MOMA_API_KEY
```

### Variables
```text
MOMA_API_BASE
MOMA_MODEL
OPENJIUWEN_INSTALL_SPEC
```

Examples for `OPENJIUWEN_INSTALL_SPEC`:

```text
openjiuwen
openjiuwen==0.1.19
git+https://<official-upstream>/openJiuwen/agent-core.git@<tag-or-commit>
```

Use an exact version/tag/commit for reproducible milestone builds.

## Run

```bash
python main.py
```

## Expected

1. `Model.invoke` returns a valid assistant message.
2. `DeepAgent.invoke` completes a minimal turn.

This does **not** yet prove:
- tool calling
- streaming
- intelligent routing
- AgentTeam
- RSI

Those are subsequent spikes defined in `docs/research/03-moma-openjiuwen-integration-spike.md`.

## Why endpoint_profile=openai_compatible?

OpenJiuwen explicitly defines a generic `openai_compatible` endpoint profile. This avoids coupling the experiment to official OpenAI endpoint-specific behavior while retaining the OpenAI Chat Completions protocol family.
