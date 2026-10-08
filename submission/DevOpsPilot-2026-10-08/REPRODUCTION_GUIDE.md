# 评审复现指南

## 离线证据浏览

解压作品包，打开EVIDENCE_REPLAY.html。它只回放随包真实证据与截图，无需.env或数据库。标题明确说明回放，不能将其当作新一次模型执行。证据JSON和PR/CI链接可独立核对；MP4也采用同一来源。

## 源码安装与离线回归

解压DevOpsPilot-源码.zip进入源码根目录，使用Python 3.11创建.venv。以下命令需首次联网下载依赖，但执行离线检查不读取用户.env，不消耗模型额度。

```bash
python3.11 -m venv .venv
uv pip install --python .venv/bin/python -e '.[test]' -r requirements-lock.txt
PYTHONPATH=src DEVOPSPILOT_NO_DOTENV=1 .venv/bin/python scripts/run_offline_checks.py --fail-fast
PYTHONPATH=src DEVOPSPILOT_NO_DOTENV=1 .venv/bin/python benchmarks/devopsbench/runner.py validate-fixtures
```

## Web与Live

```bash
uv pip install --python .venv/bin/python -r requirements-runtime.txt
.venv/bin/python scripts/serve_dashboard.py --port 8080
```

打开http://127.0.0.1:8080。没有持久化记录应显示空状态，不自动生成演示数据。操作员自行配置MOMA_API_KEY/MOMA_API_BASE/角色模型、GITHUB_TOKEN/GITHUB_REPOSITORY、数据库路径。真实查询需要凭据，创建分支/PR只对操作员明确选择的Issue执行。可信项目配置必须包含测试命令及路径边界。

当前版本仅可信本机使用。Runtime已知超时限制、首次发布后补审及修复后Live待重跑见方案书。不会自动合并PR或生产部署。外部API不可用时应停止Live并切换本包证据回放，不伪造在线成功。

## 提交前彩排

在备用电脑先验证PDF、PPTX和MP4可打开，再运行无凭据离线路径。联网试运行明确记录源码SHA、模型、预算、Issue、PR、CI与运行健康。未执行的第二人复现不得签PASS；本包的检查记录不替代独立评审。
