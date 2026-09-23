# 19 — OpenJiuwen Skill Evolution Candidate Evidence

Date: 2026-09-24  
Status: **LIVE VERIFIED — candidate only, no production promotion**

## Goal

Prove the first governed DevOpsPilot self-evolution step:

    failure evidence
      → OpenJiuwen Skill Evolution
      → staged candidate experience
      → DevOpsPilot EvolutionCandidate
      → no production write

## Live run

- Workflow: OpenJiuwen Skill Evolution Candidate
- Run: 35908155792
- Result: success
- Evolution model: GLM-5.3
- Target Skill: build-debug
- Generated records: 1
- Candidate ID: build-debug-wrong-working-directory-v1:7cd228112f5d
- OpenJiuwen pending request: skill_evolve_ea9ff1f2
- Uploaded Action artifact ID: 10772276851

## Input evidence

The source failure pattern is the deterministic DevOpsBench GitHub Actions working-directory case:

- CI command executed from an incorrect directory;
- service code lives under a subdirectory;
- correct repair is in workflow execution context, not application code or dependencies.

The canonical case ID used by subsequent runs is:

    ci.github_actions.working_directory.001

## Candidate experience

OpenJiuwen generated one body/Troubleshooting experience with the summary:

> When a CI build or test command fails, verify the workflow execution context and working-directory against the repository layout before changing code, dependencies, or retrying the build.

The generated guidance adds three reusable behaviors:

1. inspect workflow working-directory/defaults.run/job or container paths against repository layout;
2. treat file-not-found / no-tests-collected / module-not-found errors as possible execution-context mismatches before changing code;
3. reproduce the failing command from the same effective working directory before applying a repair.

## Governance proof

The Provider ran against a temporary copy of the Skill store with:

- auto_save=False;
- requires_approval=True;
- no call to OpenJiuwen approve/persist APIs.

CI then verified:

    skills/build-debug/evolutions.json does not exist
    git diff -- skills/build-debug is empty

Therefore the live optimizer generated a real candidate while the production Skill remained unchanged.

## Next gate

Candidate generation is not treated as proof of improvement.

The next experiment is:

    baseline build-debug
      vs
    build-debug + candidate experience
      ↓
    same MoMA models
    same AgentTeam
    same DevOpsBench fixture
      ↓
    RegressionGate
      ↓
    REJECTED or PENDING_HUMAN

Only a candidate that passes that gate can reach human approval.