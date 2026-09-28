"""Unit tests for task intent classification (policy v2, structured decisions).

Covers the counterexample set from docs/intent-assessment-2026-09-28.md plus
the original 7 positive cases. All async tests mock the model — no real
credentials are read.
"""

import asyncio
from unittest.mock import patch

import pytest

from devopspilot.routing.intent import (
    DecisionSource,
    DecisionStatus,
    ReasonCode,
    TaskIntent,
    TaskIntentClassifier,
)


def make_classifier() -> TaskIntentClassifier:
    return TaskIntentClassifier()


# ---------------------------------------------------------------------------
# Original positive cases
# ---------------------------------------------------------------------------

def test_classify_inquiry_file_listing():
    d = make_classifier().classify(title="[Test]列举当前有哪些文件", body="请说明各个文件的作用")
    assert d.is_inquiry
    assert d.status is DecisionStatus.RESOLVED


def test_classify_inquiry_how_to():
    d = make_classifier().classify(title="如何运行开发环境", body="请说明具体步骤")
    assert d.is_inquiry


def test_classify_code_change_bugfix():
    d = make_classifier().classify(title="fix: 修复零除异常", body="当分母为0时抛出ValueError")
    assert d.is_code_change
    assert d.status is DecisionStatus.RESOLVED


def test_classify_code_change_add_feature():
    d = make_classifier().classify(title="新增用户认证模块", body="实现JWT验证逻辑")
    assert d.is_code_change


def test_classify_inquiry_analysis_scenarios():
    d = make_classifier().classify(
        title="[Test] 分析 openjiuwen 的workswarm ，看看我们能基于它落地哪些场景的应用",
        body="",
    )
    assert d.is_inquiry


def test_classify_inquiry_architecture_survey():
    d = make_classifier().classify(
        title="调研与评估当前项目的多模型路由可行性",
        body="探讨适合落地哪些具体的生产业务场景",
    )
    assert d.is_inquiry


def test_classify_explicit_override():
    d = make_classifier().classify(title="fix: something", metadata={"intent": "inquiry"})
    assert d.is_inquiry
    assert d.source is DecisionSource.TRUSTED_OVERRIDE
    assert d.reason_code is ReasonCode.TRUSTED_OVERRIDE


# ---------------------------------------------------------------------------
# Counterexamples from the assessment report (P0/P1)
# ---------------------------------------------------------------------------

def test_analysis_title_with_fix_body_is_code_change():
    """Title '分析登录失败原因' + body '请修复认证逻辑并添加回归测试' -> code_change."""
    d = make_classifier().classify(
        title="分析登录失败原因",
        body="请修复认证逻辑并添加回归测试",
    )
    assert d.is_code_change
    assert d.reason_code is ReasonCode.CODE_CHANGE_SIGNAL


def test_label_cannot_override_body_change_request():
    """'登录异常' + body '修复认证逻辑' with help wanted label -> code_change."""
    d = make_classifier().classify(
        title="登录异常",
        body="修复认证逻辑",
        labels=("help wanted",),
    )
    assert d.is_code_change


def test_doc_change_with_explicit_pr_is_code_change():
    """'更新部署说明' + body '修改 README 并提交 PR' -> code_change."""
    d = make_classifier().classify(
        title="更新部署说明",
        body="修改 README 并提交 PR",
    )
    assert d.is_code_change


def test_negation_readonly_is_inquiry():
    """'不要修改代码，只解释 fix 的含义' -> inquiry (negation constraint)."""
    d = make_classifier().classify(
        title="不要修改代码，只解释 fix 的含义",
        body="",
    )
    assert d.is_inquiry
    assert d.reason_code is ReasonCode.NEGATION_CONSTRAINT


def test_empty_input_needs_clarification():
    """Empty title and body -> needs_clarification, NOT code_change."""
    d = make_classifier().classify(title="", body="")
    assert d.intent is None
    assert d.status is DecisionStatus.NEEDS_CLARIFICATION
    assert d.reason_code is ReasonCode.EMPTY_INPUT


def test_latin_word_boundary_address_not_add():
    """'Explain address parsing' -> inquiry; 'add' must not substring-match 'address'."""
    d = make_classifier().classify(title="Explain address parsing", body="")
    assert d.is_inquiry


def test_mixed_evaluate_with_body_change_is_code_change():
    """'评估方案并落地' + body '将缓存接入服务，补充单元测试' -> code_change.

    Assessment allows either change or arbitration — but never pure inquiry.
    Body contains explicit change actions, so the rule layer resolves it.
    """
    d = make_classifier().classify(
        title="评估方案并落地",
        body="将缓存接入服务，补充单元测试",
    )
    assert d.is_code_change
    assert d.status is DecisionStatus.RESOLVED


def test_mixed_without_body_change_needs_clarification():
    """Mixed signals confined to the title (分析 + 修复) -> needs_clarification."""
    d = make_classifier().classify(
        title="分析并修复登录问题",
        body="详情见附件",
    )
    assert d.status is DecisionStatus.NEEDS_CLARIFICATION
    assert d.reason_code is ReasonCode.MIXED_SIGNALS
    assert d.intent is None


def test_invalid_metadata_override_raises():
    with pytest.raises(ValueError):
        make_classifier().classify(title="anything", metadata={"intent": "nonsense"})


# ---------------------------------------------------------------------------
# Async arbitration (mocked model, no real credentials)
# ---------------------------------------------------------------------------

def test_trusted_override_not_arbitrated_even_when_llm_disagrees():
    """metadata.intent=code_change must win even if mock LLM says INQUIRY."""

    class FakeClient:
        def __init__(self, api_key=None):
            pass

        def chat_completion(self, messages, model=None, temperature=None):
            return {"choices": [{"message": {"content": '{"intent": "INQUIRY", "reason": "looks like a question"}'}}]}

    async def run():
        with patch("devopspilot.adapters.moma.client.MoMAClient", FakeClient), \
             patch.dict("os.environ", {"MOMA_API_KEY": "fake-key"}):
            return await make_classifier().classify_async(
                title="anything",
                metadata={"intent": "code_change"},
            )

    d = asyncio.run(run())
    assert d.is_code_change
    assert d.source is DecisionSource.TRUSTED_OVERRIDE


def test_llm_strict_enum_invalid_output_stays_unresolved():
    """LLM returns 'NOT_INQUIRY' (invalid enum) -> no substring acceptance, stays needs_clarification."""

    class FakeClient:
        def __init__(self, api_key=None):
            pass

        def chat_completion(self, messages, model=None, temperature=None):
            return {"choices": [{"message": {"content": '{"intent": "NOT_INQUIRY", "reason": "unsure"}'}}]}

    async def run():
        with patch("devopspilot.adapters.moma.client.MoMAClient", FakeClient), \
             patch.dict("os.environ", {"MOMA_API_KEY": "fake-key"}):
            return await make_classifier().classify_async(
                title="分析并修复登录问题",
                body="详情见附件",
            )

    d = asyncio.run(run())
    assert d.status is DecisionStatus.NEEDS_CLARIFICATION
    assert d.intent is None


def test_llm_resolves_mixed_signals():
    class FakeClient:
        def __init__(self, api_key=None):
            pass

        def chat_completion(self, messages, model=None, temperature=None):
            return {"choices": [{"message": {"content": '{"intent": "CODE_CHANGE", "reason": "title pairs analysis with fix"}'}}]}

    async def run():
        with patch("devopspilot.adapters.moma.client.MoMAClient", FakeClient), \
             patch.dict("os.environ", {"MOMA_API_KEY": "fake-key"}):
            return await make_classifier().classify_async(
                title="分析并修复登录问题",
                body="详情见附件",
            )

    d = asyncio.run(run())
    assert d.is_code_change
    assert d.source is DecisionSource.LLM_ARBITRATION
    assert d.reason_code is ReasonCode.LLM_ARBITRATION


def test_llm_unavailable_stays_unresolved():
    """No API key and no injected arbitrator -> stays needs_clarification (no silent CODE_CHANGE)."""
    env = {"MOMA_API_KEY": "", "DEEPSEEK_API_KEY": ""}

    async def run():
        with patch.dict("os.environ", env):
            return await make_classifier().classify_async(
                title="分析并修复登录问题",
                body="详情见附件",
            )

    d = asyncio.run(run())
    assert d.status is DecisionStatus.NEEDS_CLARIFICATION
    assert d.intent is None


def test_rule_resolved_skips_llm_entirely():
    """Clear rule decisions must not invoke the model at all."""

    calls = {"n": 0}

    class FakeClient:
        def __init__(self, api_key=None):
            pass

        def chat_completion(self, messages, model=None, temperature=None):
            calls["n"] += 1
            raise AssertionError("LLM must not be called for rule-resolved decisions")

    async def run():
        with patch("devopspilot.adapters.moma.client.MoMAClient", FakeClient), \
             patch.dict("os.environ", {"MOMA_API_KEY": "fake-key"}):
            return await make_classifier().classify_async(
                title="[Test]列举当前有哪些文件",
                body="请说明各个文件的作用",
            )

    d = asyncio.run(run())
    assert d.is_inquiry
    assert d.source is DecisionSource.RULE
    assert calls["n"] == 0


def test_injected_arbitrator_used_for_mixed():
    async def arb(title, body):
        return TaskIntent.INQUIRY

    async def run():
        return await make_classifier().classify_async(
            title="分析并修复登录问题",
            body="详情见附件",
            arbitrator=arb,
        )

    d = asyncio.run(run())
    assert d.is_inquiry
    assert d.source is DecisionSource.LLM_ARBITRATION


def test_decision_as_dict_roundtrip():
    d = make_classifier().classify(title="fix: 修复零除异常", body="")
    payload = d.as_dict()
    assert payload["intent"] == "code_change"
    assert payload["status"] == "resolved"
    assert payload["policy_version"].startswith("intent-policy-")
