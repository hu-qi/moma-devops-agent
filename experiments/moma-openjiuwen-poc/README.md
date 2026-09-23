# MoMA × OpenJiuwen PoC

Purpose: validate that a MoMA endpoint can be consumed through OpenJiuwen's generic OpenAI-compatible model client and then used by DeepAgent.

## Requirements

- Python 3.11–3.13
- `openjiuwen==0.1.18` for the initial baseline
- a valid MoMA API credential and model ID

## Environment

```bash
export MOMA_API_BASE="<value from MoMA console/docs>"
export MOMA_API_KEY="<secret>"
export MOMA_MODEL="<model id>"
```

Do not commit credentials.

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

OpenJiuwen 0.1.18 explicitly defines a generic `openai_compatible` endpoint profile. This avoids coupling the experiment to official OpenAI endpoint-specific behavior while retaining the OpenAI Chat Completions protocol family.
