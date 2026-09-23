# Jiuwen Dynamic AgentTeam Spike

## Question

Can DevOpsPilot implement a DevOps Leader that dynamically creates Coding and Review specialists using OpenJiuwen AgentTeams rather than a custom A2A implementation?

Target flow:

    DevOps Leader
        ↓ complexity requires team
    dynamic spawn
        ├── Coding Agent
        └── Review Agent
        ↓
    Leader verification

## Upstream Target

openJiuwen-ai/agent-core@release/v0.1.19

The public release branch exists. The package metadata on that branch may still show the previous package version while the release is being prepared, so this spike pins the branch rather than assuming a PyPI 0.1.19 artifact.

## Pass Criteria

- Team runtime starts.
- Leader does not complete the task alone.
- Two distinct teammates are dynamically created.
- Coding and review responsibilities are separated.
- Leader receives both results and produces one verified conclusion.
- No custom DevOpsPilot A2A endpoint is required.

## Optional Model Roles

Environment variables can later demonstrate multi-model routing:

    MOMA_REASONING_MODEL=...
    MOMA_CODING_MODEL=...

Both fall back to MOMA_MODEL.

## Run

Use the repository workflow:

Actions → MoMA × OpenJiuwen Spikes → Run workflow.
