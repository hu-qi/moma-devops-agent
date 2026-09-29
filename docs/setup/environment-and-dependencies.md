# DevOpsPilot 环境配置与依赖管理指南

基线日期：2026-09-26  
对应任务：`TODO.md` T01 · P1 · 工程基础

## 1. 干净环境一键安装

DevOpsPilot 支持 Python 3.11+。在干净的虚拟环境中，执行以下命令即可完成基础及行业工程包安装：

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e .
```

若需安装可选依赖：
- 包含测试工具（pytest + pytest-asyncio）：`pip install -e ".[test]"`
- 包含完整开发依赖：`pip install -e ".[all]"`
- 使用固定版本锁定文件安装：`pip install -r requirements-lock.txt`

测试套件中的异步用例（`tests/test_intent_classification.py`）使用 `pytest.mark.asyncio` 标记，依赖 `pytest-asyncio`。pytest 配置为 `asyncio_mode = "strict"`，`pytest-asyncio` 属于 `[test]`/`[all]` extras，干净环境仅需 `pip install -e ".[test]"` 即可运行全部测试；未安装时异步用例会因未知 marker 失败，属预期行为。

## 2. 依赖分组与分层设计

DevOpsPilot 严格遵守 Core / Runtime / MaaS / SCM 的分层设计，并将离线主链与重型在线运行时依赖解耦：

| 分组 | 依赖包 | 用途与约束 |
|---|---|---|
| **Core / 离线主链** (默认) | `pyyaml>=6.0.1` | 用于 Industry Engineering Pack (`pack.yaml`) 解析、配置读取与离线验证主链。标准库覆盖 dataclasses、sqlite3 等。 |
| **Test** (`[test]`) | `pytest>=8.0.0`、`pytest-asyncio>=0.24.0` | 单元测试框架、断言工具与异步用例支持（strict marker 模式）。 |
| **Industry** (`[industry]`) | `pyyaml>=6.0.1` | 行业规则规范包解析与加载。 |
| **Runtime** (`[runtime]`) | `openjiuwen[observability,sqlite]` | 在线 AgentTeam 执行引擎与 RSI 进化能力。仅在真实调用模型或本地运行 OpenJiuwen 运行时时需要。 |

## 3. OpenJiuwen Runtime 精确基线与版本记录

为保证执行环境可复现，且避免模糊的分支引用带来飘移，DevOpsPilot 明确记录 OpenJiuwen Runtime 的精确来源：

- **上游仓库**: `https://github.com/openJiuwen-ai/agent-core.git`
- **目标分支**: `release/v0.1.19`
- **精确锁定 Commit SHA**: `6f3a33fbb93aece65105c477c573057fead0e8dd`
- **安装 Specification**:
  ```text
  openjiuwen[observability,sqlite] @ git+https://github.com/openJiuwen-ai/agent-core.git@6f3a33fbb93aece65105c477c573057fead0e8dd
  ```
- **版本元数据说明（关键）**:
  截至 2026-09-23，从上述 commit 安装后，Python 包元数据 (`importlib.metadata.version("openjiuwen")` / `pip list`) 仍报告 `0.1.18`。工程记录中必须同时标明 **Source commit SHA (`6f3a33fbb93aece65105c477c573057fead0e8dd`)** 与 **Package metadata (`0.1.18`)**，不得将二者混淆。

## 4. 验证命令

完成安装后，执行以下命令验证基础环境与行业工程包导入成功：

```bash
# 验证核心模块与类型注解（含 typing.get_type_hints）
python -c "import devopspilot; from devopspilot.contracts.delivery import DeliveryTask; import typing; typing.get_type_hints(DeliveryTask); print('DELIVERY_CONTRACTS_OK')"

# 验证行业包导入与解析
python -c "import devopspilot.industry; from devopspilot.industry.loader import load_pack_from_directory; print('INDUSTRY_LOADER_OK')"
```
