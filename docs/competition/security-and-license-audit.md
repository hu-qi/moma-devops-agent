# DevOpsPilot 自动化安全与依赖许可证审计报告 (R22)

- **扫描器版本**：`0.2.0-r22`
- **审计日期**：`2026-10-03`
- **总体审计结论**：**PASS (通过)**

## 一、凭据与私钥泄露审计

未发现任何明文私钥、真实个人访问令牌 (PAT) 或已提交的 `.env` 配置文件。所有测试 Mock 均处于白名单中。

## 二、合成脱敏数据 Fixture 索引 (无明文外泄)

在工程基准题库与专项测试中，共发现 **8** 处合成脱敏用例（仅用于验证合规门禁与脱敏能力）：

| 文件路径 | 规则类型 | 合成数据属性 | 说明 |
|---|---|---|---|
| `benchmarks/cases/review-python-unmasked-pii/case.json:21` | `synthetic_cn_idcard` | 合成脱敏样例 | Synthetic test/benchmark case fixture |
| `benchmarks/cases/review-python-unmasked-pii/fixture/user_service.py:9` | `synthetic_cn_mobile` | 合成脱敏样例 | Synthetic test/benchmark case fixture |
| `benchmarks/cases/review-python-unmasked-pii/fixture/user_service.py:9` | `synthetic_cn_idcard` | 合成脱敏样例 | Synthetic test/benchmark case fixture |
| `experiments/end-to-end-integration-suite/main.py:385` | `synthetic_cn_idcard` | 合成脱敏样例 | Synthetic test/benchmark case fixture |
| `experiments/industry-gate-runner-smoke/main.py:84` | `synthetic_cn_idcard` | 合成脱敏样例 | Synthetic test/benchmark case fixture |
| `experiments/industry-gate-runner-smoke/main.py:125` | `synthetic_cn_mobile` | 合成脱敏样例 | Synthetic test/benchmark case fixture |
| `experiments/industry-rule-engine-smoke/main.py:31` | `synthetic_cn_mobile` | 合成脱敏样例 | Synthetic test/benchmark case fixture |
| `experiments/industry-rule-engine-smoke/main.py:31` | `synthetic_cn_idcard` | 合成脱敏样例 | Synthetic test/benchmark case fixture |

## 三、锁定依赖第三方许可证兼容性

| 依赖包名称 | 已安装版本 | 许可证类型 | 开源/商业兼容性 | 来源元数据 |
|---|---|---|---|---|
| **PyYAML** | `6.0.3` | `MIT` | **兼容 (PASS)** | https://pyyaml.org/ |
| **pytest** | `9.1.1` | `MIT` | **兼容 (PASS)** | Changelog, https://docs.pytest.org/en/stable/changelog.html |
| **pytest-asyncio** | `1.4.0` | `Apache-2.0` | **兼容 (PASS)** | Bug Tracker, https://github.com/pytest-dev/pytest-asyncio/issues |
| **iniconfig** | `2.3.0` | `MIT` | **兼容 (PASS)** | Homepage, https://github.com/pytest-dev/iniconfig |
| **pluggy** | `1.6.0` | `MIT` | **兼容 (PASS)** | https://pypi.org/project/pluggy |

---
*本报告由 `scripts/audit_security_and_licenses.py` 自动执行生成，不可篡改。*