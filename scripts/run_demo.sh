#!/usr/bin/env bash
# ==============================================================================
# DevOpsPilot 一键演示脚本 (C26: Deterministic / Recorded / Live)
#
# 用法:
#   ./scripts/run_demo.sh deterministic  # 默认: 全离线确定性执行，零 API 消耗，完整门禁闭环
#   ./scripts/run_demo.sh recorded       # 真实历史轨迹与证据文件检视
#   ./scripts/run_demo.sh live           # 真实在线交付（需配置 GITHUB_TOKEN 与 MOMA_API_KEY）
# ==============================================================================

set -euo pipefail

MODE="${1:-deterministic}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${ROOT_DIR}"
export PYTHONPATH="${ROOT_DIR}/src:${PYTHONPATH:-}"

PYTHON_BIN="python3"
if [[ -f "${ROOT_DIR}/.venv/bin/python" ]]; then
  PYTHON_BIN="${ROOT_DIR}/.venv/bin/python"
fi

echo "============================================================"
echo "  DevOpsPilot V1 演示入口 (模式: ${MODE})"
echo "============================================================"

case "${MODE}" in
  deterministic)
    echo "[1/2] 运行确定性端到端集成套件（本地隔离 Git 仓库 + 完整门禁流转）..."
    "${PYTHON_BIN}" -m devopspilot.cli.main demo --mode deterministic
    echo "[2/2] 确定性演示运行完成。无外部网络依赖，全流程可复验。"
    ;;

  recorded)
    echo "[1/2] 检视已归档的历史真实运行轨迹与证据文件..."
    "${PYTHON_BIN}" -m devopspilot.cli.main demo --mode recorded
    echo "[2/2] 真实证据文件展示完毕。可查验 docs/evidence/ 下的原始产物。"
    ;;

  live)
    echo "[1/3] 检查 Live 运行凭据..."
    if [[ -z "${GITHUB_TOKEN:-}" ]] || [[ -z "${MOMA_API_KEY:-}" ]]; then
      echo "错误: Live 模式需要环境变量 GITHUB_TOKEN 与 MOMA_API_KEY。"
      echo "提示: 如需零凭据快速复现，请执行: ./scripts/run_demo.sh deterministic"
      exit 1
    fi
    if [[ -z "${GITHUB_REPOSITORY:-}" ]] || [[ -z "${DEVOPSPILOT_E2E_ISSUE:-}" ]]; then
      echo "错误: Live 模式需要设置目标仓库 GITHUB_REPOSITORY (如 owner/repo) 及 ISSUE 编号 DEVOPSPILOT_E2E_ISSUE。"
      exit 1
    fi
    echo "[2/3] 启动真实端到端交付主链..."
    "${PYTHON_BIN}" -m devopspilot.cli.main demo --mode live
    echo "[3/3] 交付流程结束，请查看对应 Issue 及 Pull Request。"
    ;;

  *)
    echo "未知模式: ${MODE}"
    echo "有效模式: deterministic | recorded | live"
    exit 2
    ;;
esac
