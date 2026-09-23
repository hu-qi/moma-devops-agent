# 09 — MoMA Model Configuration Boundary

Date: 2026-09-23  
Status: **Architecture clarification**

## Decision

`MOMA_MODEL` is a **single bootstrap/default model** used for:
- basic compatibility probes;
- initial DeepAgent / AgentTeam smoke tests;
- fallback when no capability-specific route exists.

It is **not** the final DevOpsPilot model-routing design.

## Target Design

```text
TaskProfile
    ↓
ModelCapability
    ↓
RoutingPolicy
    ↓
FAST / REASONING / CODING / REVIEW / JUDGE
    ↓
MoMAProvider
    ↓
managed route or concrete model
```

Non-secret routing configuration lives in:

```text
configs/models/moma.yaml
```

Secrets remain outside the repository:

- GitHub Actions Secret: `MOMA_API_KEY`
- GitHub Actions Variable: `MOMA_API_BASE`
- GitHub Actions Variable: `MOMA_MODEL` (bootstrap only)

## Why

This prevents environment variables from becoming the product's routing schema and keeps future MaaS providers replaceable.

Once MoMA's intelligent-routing API parameters are live-verified, the same configuration can switch from fixed model IDs to managed route aliases without changing orchestration code.
