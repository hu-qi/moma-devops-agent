# 18 — GitHub Live Delivery E2E Evidence

Date: 2026-09-24  
Status: **VERIFIED end-to-end**

## Product path proven

    GitHub Issue #1
        ↓
    MoMA + OpenJiuwen AgentTeam
        ↓
    constrained repository edit
        ↓
    independent verification
        ↓
    exact local commit
        ↓
    branch publish
        ↓
    Pull Request #2
        ↓
    GitHub Actions fixture CI
        ↓
    VERIFIED

## Source task

- Issue: #1 — [DevOpsPilot E2E] Fix GitHub delivery fixture status
- Allowed file: e2e/fixtures/github_delivery/app.py
- Forbidden file: e2e/fixtures/github_delivery/test_app.py
- Max changed files: 1
- Acceptance test: python test_app.py in the fixture directory

## Agent execution evidence

- Workflow: GitHub Live Delivery E2E
- Run: 35906483773
- Leader model: GLM-5.3
- Coding model: Qwen3-32B
- Review model: deepseek-v4.1-flash
- Runtime degradation: agentteam_timeout at 180s
- Trajectory: df43e104d607bd752c1d8f8d13475da5
- Model calls: 17
- Tool calls: 14

Despite the OpenJiuwen Team stream termination degradation, deterministic engineering gates passed.

## Exact delivery artifact

- Branch: devopspilot/e2e-1-35906483773
- Commit: fb2e70b74f16859afa5ee2f015ef9e8c864353fb
- Commit author: DevOpsPilot
- Changed files: 1

## GitHub permission boundary discovered

The repository GITHUB_TOKEN successfully pushed the validated branch, but GitHub rejected PR creation with:

    GitHub Actions is not permitted to create or approve pull requests.

This is a repository-level Actions policy, not a model, OpenJiuwen, Git transport, or GitHub adapter failure.

DevOpsPilot therefore supports a dedicated repository secret:

    DEVOPSPILOT_GITHUB_TOKEN

and falls back to github.token when repository policy permits.

## PR and CI proof

- Pull Request: #2
- PR head SHA: fb2e70b74f16859afa5ee2f015ef9e8c864353fb
- Changed files: 1
- Fixture CI workflow: GitHub E2E Fixture CI
- CI run: 35907083104
- CI conclusion: success

The PR was created through the connected GitHub App using the already validated branch and commit. The Agent was not rerun.

## Final product conclusion

The following DevOpsPilot V1 path is no longer architectural only; it has been exercised against real GitHub state:

    Issue
      → AgentTeam
      → code change
      → independent verification
      → exact commit
      → branch publish
      → Pull Request
      → GitHub Actions
      → delivery verification

The remaining runtime issue is explicitly tracked as runtime health and does not invalidate task correctness.