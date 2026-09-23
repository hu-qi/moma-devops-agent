# Build-Debug Skill Evolution A/B

This experiment evaluates an OpenJiuwen-generated Skill Experience candidate
against the same deterministic DevOpsBench CI-debug case.

The only intended capability difference is the Skill experience overlay:

- baseline: build-debug SKILL.md only;
- candidate: the same Skill plus the staged working-directory experience.

Both variants use the same:
- MoMA endpoint;
- role model configuration;
- OpenJiuwen AgentTeam executor;
- benchmark fixture;
- file constraints;
- independent oracle.

The candidate is materialized only into a temporary Skill sandbox through
OpenJiuwen EvolutionStore. Production skills/build-debug is never modified.

A candidate that fails the regression gate is a valid experimental result and
is recorded as REJECTED; it does not make the workflow itself fail.


## Experiment isolation

Each A/B variant carries a unique execution_id. OpenJiuwen Team names and
session ids include that attempt identity so baseline, candidate, retries, and
parallel evaluations cannot inherit one another's AgentTeam context.
