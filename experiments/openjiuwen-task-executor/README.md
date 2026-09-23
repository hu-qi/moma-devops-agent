# OpenJiuwen TaskExecutor × DevOpsBench

This live spike validates the first real DevOpsPilot execution port.

It uses:
- MoMA as MaaS data plane
- OpenJiuwen AgentTeam as runtime
- dynamic DevOps Leader + Coding/Review teammates
- a temporary Git repository copied from a deterministic DevOpsBench fixture
- independent post-agent validation
- a local Git commit
- DevOpsBench oracle evaluation

The AgentTeam is not trusted merely because it says the task succeeded.

Success requires all of the following:
1. only `range_sum.py` changed;
2. `test_range_sum.py` was untouched;
3. independent `python test_range_sum.py` passes;
4. a local commit is created;
5. working tree is clean;
6. DevOpsBench oracle reports `task_success=true`.

The result remains `published=false`. Publishing to GitHub/CNB is a separate product port.
