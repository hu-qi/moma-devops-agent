---
name: build-debug
description: Diagnose CI/build failures and produce the smallest verifiable repair.
---

# Build Debug

Use this Skill when a build or CI job fails and the root cause is not yet proven.

## Workflow

1. Read the failing job/stage logs before changing code.
2. Classify the failure: environment, dependency, build configuration, test, or application code.
3. Reproduce the smallest failing command when practical.
4. Inspect only the files relevant to the proven failure.
5. Apply the smallest repair.
6. Re-run the failing command and the repository's relevant verification.
7. Report the root cause, changed files, and verification evidence.

## Guardrails

- Do not change tests only to make a failure disappear.
- Do not retry blindly without a root-cause hypothesis.
- Do not broaden dependency or configuration changes beyond the proven failure.
- Preserve an audit trail of commands and evidence.
