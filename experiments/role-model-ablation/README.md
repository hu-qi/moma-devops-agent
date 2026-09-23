# Role-model Ablation Runner

Manual-only live benchmark runner for MoMA/OpenJiuwen AgentTeam role selection.

It deliberately does not run automatically on every push.

Example:

```bash
PYTHONPATH=src python experiments/role-model-ablation/main.py \
  --label coding-qwen3 \
  --leader GLM-5.3 \
  --coding Qwen3-32B \
  --review deepseek-v4.1-flash \
  --repetition 1
```

Only models that passed the structured Tool Calling capability gate should be
used for tool-using roles.

V0.1 experiment order is documented in
`docs/research/14-devopsbench-role-model-ablation.md`.
