# 10 — CNB Adapter Strategy

Date: 2026-09-23  
Status: **Transport scaffold implemented; command/response mapping pending CI evidence**

## Why CNB

CNB's official documentation confirms:
- OpenAPI at `https://api.cnb.cool`;
- Bearer token authentication;
- official `@cnbcool/cnb-cli`;
- repository / Issue / PR operations;
- PR review and status checks through official Skills;
- pipeline triggering;
- build status and log querying.

This makes CNB a strong first domestic end-to-end DevOpsPilot provider candidate.

## Adapter Strategy

V1 uses a layered design:

```text
SCMProvider / CIProvider
          ↓
CNB Domain Mapper
          ↓
CNB Transport
     ┌────┴────┐
     ↓         ↓
  CNB CLI    Raw OpenAPI
  (Spike)     (future)
```

The first spike uses the official CLI because CNB documents it as a command-line interface to the full OpenAPI surface.

The product contracts do not know whether the transport is CLI or HTTP.

## Current Implementation

```text
src/devopspilot/adapters/cnb/client.py
```

The client:
- invokes `cnb` without a shell;
- injects `CNB_TOKEN` only through process environment;
- injects `CNB_API_ENDPOINT`;
- captures stdout/stderr;
- provides text and JSON execution modes;
- never persists credentials.

## Evidence Gate

Before implementing `CNBSCMProvider` and `CNBCIProvider`, CI must capture the real current CLI surface for:

- repos
- issues
- pulls
- build

Workflow:

```text
.github/workflows/cnb-cli-surface.yml
```

After the command names and output conventions are verified, the next commit will implement provider mapping and a credential-free fake-transport contract smoke.

## Future Live Spike

When a CNB test token/repository is available:

```text
Issue
 ↓
CNBSCMProvider
 ↓
PR
 ↓
CNBCIProvider
 ↓
failing pipeline
 ↓
logs
 ↓
retry
```

The same DevOpsPilot domain objects used by GitHub must be produced.
