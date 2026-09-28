import pytest
from devopspilot.routing.intent import (
    DecisionStatus,
    ReasonCode,
    TaskIntent,
    TaskIntentClassifier,
)


@pytest.mark.asyncio
async def test_chinese_file_listing_is_inquiry():
    classifier = TaskIntentClassifier()
    decision = await classifier.classify_async(
        title="[Test]列举当前有哪些文件",
        body="详细说明这些文件是干啥的",
    )
    assert decision.status == DecisionStatus.RESOLVED
    assert decision.intent == TaskIntent.INQUIRY
    assert decision.reason_code == ReasonCode.INQUIRY_SIGNAL


@pytest.mark.asyncio
async def test_trusted_intent_override():
    classifier = TaskIntentClassifier()
    decision = await classifier.classify_async(
        title="修复一个bug",
        body="请修复",
        metadata={"intent": "inquiry"},
    )
    assert decision.status == DecisionStatus.RESOLVED
    assert decision.intent == TaskIntent.INQUIRY
    assert decision.reason_code == ReasonCode.TRUSTED_OVERRIDE


@pytest.mark.asyncio
async def test_code_change_intent():
    classifier = TaskIntentClassifier()
    decision = await classifier.classify_async(
        title="修复登录接口超时问题",
        body="重构重试逻辑并提交代码",
    )
    assert decision.status == DecisionStatus.RESOLVED
    assert decision.intent == TaskIntent.CODE_CHANGE
