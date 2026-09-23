# 18 — First Live GitHub Delivery E2E

Date: 2026-09-24
Status: **VERIFIED**

## End-to-End Path

    GitHub Issue #1
      -> MoMA
      -> OpenJiuwen AgentTeam
      -> constrained repository edit
      -> independent local test
      -> exact Git commit
      -> branch publish
      -> GitHub Pull Request #2
      -> GitHub Actions
      -> Delivery Report

## Evidence

- Issue: https://github.com/hu-qi/moma-devops-agent/issues/1
- Pull Request: https://github.com/hu-qi/moma-devops-agent/pull/2
- Validated commit: fb2e70b74f16859afa5ee2f015ef9e8c864353fb
- CI run: https://github.com/hu-qi/moma-devops-agent/actions/runs/35907083104
- CI conclusion: SUCCESS

## Change Boundary

PR #2 changed exactly one file:

    e2e/fixtures/github_delivery/app.py

Observed patch:

    return "broken"
    ->
    return "fixed"

The forbidden oracle file was untouched:

    e2e/fixtures/github_delivery/test_app.py

## Agent Runtime

Role models:

    Leader: GLM-5.3
    Coding: Qwen3-32B
    Review: deepseek-v4.1-flash

The AgentTeam produced a correct patch and test evidence, but its stream did not terminate cleanly within 180 seconds.

Therefore:

    task_success = true
    runtime_clean_completion = false
    runtime_degradation_reason = agentteam_timeout

This validates the decision to evaluate task correctness separately from runtime lifecycle health.

## SCM Control Plane Finding

The built-in GitHub Actions GITHUB_TOKEN successfully published the branch but repository policy rejected Pull Request creation with HTTP 403:

    GitHub Actions is not permitted to create or approve pull requests.

The external GitHub control plane then created PR #2 from the exact same validated commit without re-running the Agent.

This proves that DevOpsPilot should keep:

    Execution Credential
    != 
    SCM Control Credential

The product must support a GitHub App/PAT/OAuth control identity instead of assuming the GitHub Actions token is sufficient.

## Result

**First real Issue -> AgentTeam -> Commit -> PR -> CI delivery is VERIFIED.**

## Next

Feed this live trajectory and delivery outcome into the Evolution pipeline:

    Trajectory
      -> Evidence normalization
      -> DevOpsBench outcome
      -> Failure/success mining
      -> RSI candidate
      -> offline evaluation
      -> no automatic production promotion