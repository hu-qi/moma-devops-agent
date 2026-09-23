# OpenJiuwen Skill Evolution Candidate

This experiment is the first live candidate-generation step in DevOpsPilot's
governed self-evolution loop.

Input evidence:

- DevOpsBench case: ci.python.wrong_working_directory.001
- target Skill: build-debug
- evolution signal: execution failure caused by incorrect working directory

Safety boundary:

1. the repository skills directory is copied to a temporary sandbox;
2. OpenJiuwen SkillEvolutionRail runs with auto_save=False;
3. external evolution requires approval;
4. DevOpsPilot reads only the staged PendingChange payload;
5. the OpenJiuwen approve/persist API is never called;
6. production skills/build-debug/evolutions.json must remain absent.

The produced JSON is a candidate artifact only. It is uploaded as CI evidence
and is not promoted to the production Skill.
