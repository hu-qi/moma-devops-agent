# DevOpsPilot 全新目录复现指引与交付物合规审计报告 (C30)

> **审计基准日期**：2026-09-29  
> **审计范围**：项目根目录、源码目录 `src/`、测试与用例 `tests/` `experiments/` `benchmarks/`、文档 `docs/`  
> **责任声明**：本仓库代码遵循开源合规要求，所有凭据均已完成脱敏，不存在明文硬编码密钥、私有数据库密码或非授权闭源依赖。

---

## 一、第二人独立复现操作规程 (Clean-Room Reproduction)

为确保任何评审专家或第三方工程师在全新环境下均能 100% 独立复现，请按以下标准化步骤操作：

### 1. 干净环境准备
```bash
# 推荐使用 Python 3.11 或以上干净环境
python3 --version  # 应输出 Python 3.11+ 或 3.14

# 克隆仓库并进入根目录
git clone https://github.com/hu-qi/moma-devops-agent.git
cd moma-devops-agent

# 创建并激活隔离虚拟环境
python3 -m venv .venv
source .venv/bin/activate
```

### 2. 安装项目依赖
```bash
# 采用开发与测试标准模式安装
pip install -e ".[test]"
```

### 3. 执行全量 41 项离线自动化回归测试
```bash
python3 scripts/run_offline_checks.py
```
- **预期输出**：
  ```text
  [+] script  devopsbench-runtime-metrics      PASS
  [+] tests   pytest-tests                     PASS
  [+] fixture fixture-lifecycle-smoke          PASS
  [+] fixture devopsbench-validate-fixtures    PASS
  ============================================================
  Summary: 41 passed, 0 failed in ~12.6s
  ```

### 4. 运行一键端到端确定性演示
```bash
./scripts/run_demo.sh deterministic
```
- **预期输出**：
  ```text
  === E2E INTEGRATION SUITE SUMMARY ===
  Run 1 (Standard Feature Delivery): VERIFIED_CLEAN (SHA: c8ec120d)
  Run 2 (Autonomous CI Remediation): VERIFIED_CLEAN (Fixed SHA: dce93361, Attempts: 1)
  Run 3 (Industry Compliance Pack):  VERIFIED_CLEAN (Pack: gov-compliance-pack-v1)
  ALL 3 INDEPENDENT INTEGRATION RUNS PASSED CLEANLY (11/11 V1 REQUIREMENTS VERIFIED).
  ```

---

## 二、交付物脱敏与安全自查报告 (Security & Desensitization Scan)

| 检查项 | 扫描范围 | 检查手段 | 审计结论 | 说明与佐证 |
|---|---|---|---|---|
| **API 密钥扫描** | `src/`, `docs/`, `experiments/`, `benchmarks/` | 正则匹配 `sk-`, `ghp_`, `AKID`, `secret` | **合规 (PASS)** | 无任何真实 API Key；文档中仅有形如 `ghp_xxxx` 的占位说明符 |
| **云服务密码** | 全仓库配置文件与脚本 | 检索 `password`, `conn_str`, `private_key` | **合规 (PASS)** | 本地采用 SQLite 内存/文件持久化，无远程数据库明文密码 |
| **真实个人敏感信息** | 政务行业合规包与测试 fixture | 检索真实身份证、手机号、企业税号 | **合规 (PASS)** | 所有 fixture 中的身份数据均为标准 GB 校验合规的合成虚构假数据 |
| **Git 历史敏感文件** | `.git/` 提交历史 | 检索 `.env`, `*.pem`, `*.p12` | **合规 (PASS)** | 均已纳入 `.gitignore`，历史提交中无敏感证书或环境配置 |

---

## 三、开源许可证与第三方依赖合规自查 (License Compliance)

### 1. 本项目开源许可证
- **主许可证**：`LICENSE` 文件已声明为 **Apache License 2.0**，兼容移动云开发者生态与各类商业企业级二次开发。
- **元数据对齐**：`pyproject.toml` 中的 `project.license` 明确指定为 `"Apache-2.0"`。

### 2. 第三方依赖许可证合规矩阵

| 依赖组件 | 声明版本 | 开源许可证 | 使用方式 | 兼容性评估 |
|---|---|---|---|---|
| **Python** | `>= 3.11` | PSF License | 运行时环境 | 100% 商业与开源兼容 |
| **pyyaml** | `>= 6.0.1` | MIT License | 行业规则与配置文件解析 | 宽松商业许可，完全兼容 |
| **pytest** | `>= 8.0.0` | MIT License | 离线自动化测试框架 | 宽松商业许可，完全兼容 |
| **openJiuwen (agent-core)** | `release/v0.1.19` (Git Pin) | Apache License 2.0 | 底层执行引擎适配器 | 相同 Apache-2.0 协议，完全兼容 |
| **DevOpsBench Fixtures** | 合成测试用例集 | CC0-1.0 / Apache-2.0 | 评测基准题库 | 公共领域贡献/标准协议，无版权纠纷 |

### 3. 合规自查总评
- **无传染性风险**：全项目未引用任何 GPL/AGPL 等强传染性开源协议库，满足央企与各类企业研发交付的合规准入要求。
- **无不可控网络下载**：离线测试脚本均设计为本地 fixture 运行，CI 执行过程不依赖任何非标准闭源私有镜像。
