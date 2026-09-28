"""Intent classification for delivery work items (inquiry vs. code change).

Structured decision output with explicit status/source/reason codes so callers
can distinguish trusted overrides, clear rules, weak signals, LLM arbitration
and degradation — instead of an opaque (intent, reason) tuple.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Mapping, Sequence


POLICY_VERSION = "intent-policy-v2"


class TaskIntent(StrEnum):
    INQUIRY = "inquiry"          # Read-only Q&A, listing, analysis (no repo mutation, no PR)
    CODE_CHANGE = "code_change"  # Any repo file change: code/docs/config/tests (branch + PR + CI)


class DecisionStatus(StrEnum):
    RESOLVED = "resolved"                        # Confident decision, safe to act on
    NEEDS_CLARIFICATION = "needs_clarification"  # Uncertain; must NOT default to writing


class DecisionSource(StrEnum):
    TRUSTED_OVERRIDE = "trusted_override"  # Explicit CLI/project config, not issue text
    RULE = "rule"                          # Clear, conflict-free keyword rule
    LLM_ARBITRATION = "llm_arbitration"    # Model adjudicated a weak/conflicting signal
    FALLBACK = "fallback"                  # Model unavailable/invalid output; degraded


class ReasonCode(StrEnum):
    TRUSTED_OVERRIDE = "trusted_override"
    INQUIRY_SIGNAL = "inquiry_signal"
    CODE_CHANGE_SIGNAL = "code_change_signal"
    MIXED_SIGNALS = "mixed_signals"
    NEGATION_CONSTRAINT = "negation_constraint"
    EMPTY_INPUT = "empty_input"
    LLM_ARBITRATION = "llm_arbitration"
    LLM_UNAVAILABLE = "llm_unavailable"
    LLM_INVALID_OUTPUT = "llm_invalid_output"
    LLM_CONFLICT = "llm_conflict"  # Model output contradicts trusted override; override kept


# Word-boundary matching for latin keywords (prevents "address" matching "add")
_LATIN_WORD_RE = re.compile(r"[a-z0-9_\-]+")

# Inquiry signals: read-only intent (analysis, listing, explanation, discussion)
_INQUIRY_PATTERNS_ZH = (
    "分析", "看看", "调研", "评估", "探讨", "梳理", "总结", "建议",
    "列举", "列出", "展示", "统计", "有哪些", "查询", "解释", "介绍",
    "详细说明", "说明", "干啥", "干什么", "做什么", "做什么用", "有什么用",
    "作用", "含义", "请教", "咨询", "请问",
    "如何使用", "怎么用", "如何运行", "什么是", "为什么",
    "查看", "目录结构", "架构是", "架构设计", "优缺点",
    "方案对比", "可行性", "是什么", "怎么样",
)
_INQUIRY_PATTERNS_EN = (
    "analyze", "analysis", "investigate", "evaluate", "survey",
    "feasibility", "overview", "explain", "what is", "what are",
    "how to", "where is", "list files", "list all", "show files",
    "use cases", "scenarios",
)

# Code-change signals: repo mutation intent (covers code/docs/config/tests)
_CODE_CHANGE_PATTERNS_ZH = (
    "修复", "新增", "实现", "添加", "重构", "删除", "修改",
    "编写", "提交", "创建", "更新", "接入", "补充", "部署",
    "编写代码", "修改代码", "优化代码", "完善", "扩展",
    "说明并修改", "说明文档修改",
)
_CODE_CHANGE_PATTERNS_EN = (
    "fix", "bugfix", "implement", "refactor", "modify", "update",
    "delete", "remove", "create", "write", "commit", "patch",
    "submit", "deploy", "optimize", "extend", "integrate",
)

# Latin verbs that also exist as substrings of unrelated words; matched
# with word boundaries only.
_CODE_CHANGE_EN_VERBS = frozenset(_CODE_CHANGE_PATTERNS_EN)
_INQUIRY_EN_PATTERNS = frozenset(_INQUIRY_PATTERNS_EN)

# Negation / read-only constraint markers: a change verb in their scope does
# NOT authorize mutation ("不要修改代码，只解释..." / "don't modify code, just explain")
_NEGATION_MARKERS_ZH = ("不要", "无需", "不用", "禁止", "别", "只解释", "只分析", "只回答", "仅解释", "仅分析")
_NEGATION_MARKERS_EN = (
    "don't", "do not", "no need to", "without modifying", "without changing",
    "read-only", "just explain", "only explain", "just answer", "only answer",
)

# Issue labels that hint at inquiry — auxiliary signal only, never authoritative
_INQUIRY_LABELS = frozenset({"question", "inquiry", "q&a", "discussion"})

_TRUSTED_INQUIRY_VALUES = frozenset({"inquiry", "qa", "question"})
_TRUSTED_CODE_VALUES = frozenset({"code_change", "code", "pr", "change"})

_MAX_LLM_INPUT_CHARS = 4000


@dataclass(frozen=True, slots=True)
class IntentDecision:
    """Structured intent decision with full audit trail."""

    intent: TaskIntent | None                 # None when needs_clarification
    status: DecisionStatus
    source: DecisionSource
    reason_code: ReasonCode
    reason: str
    matched_signals: tuple[str, ...] = field(default=())
    fallback_error: str | None = None
    policy_version: str = POLICY_VERSION

    @property
    def is_inquiry(self) -> bool:
        return self.intent is TaskIntent.INQUIRY

    @property
    def is_code_change(self) -> bool:
        return self.intent is TaskIntent.CODE_CHANGE

    def as_dict(self) -> dict:
        return {
            "intent": self.intent.value if self.intent else None,
            "status": self.status.value,
            "source": self.source.value,
            "reason_code": self.reason_code.value,
            "reason": self.reason,
            "matched_signals": list(self.matched_signals),
            "fallback_error": self.fallback_error,
            "policy_version": self.policy_version,
        }


def _latin_tokens(text: str) -> set[str]:
    return set(_LATIN_WORD_RE.findall(text))


def _matched_zh(text: str, patterns: Sequence[str]) -> list[str]:
    return [p for p in patterns if p in text]


def _matched_en(text: str, vocab: frozenset[str]) -> list[str]:
    tokens = _latin_tokens(text)
    return sorted(tokens & vocab)


def _has_negation_constraint(text: str) -> tuple[bool, list[str]]:
    """Detect read-only constraint markers near change verbs."""
    hits = _matched_zh(text, _NEGATION_MARKERS_ZH)
    lowered = text
    hits.extend(m for m in _NEGATION_MARKERS_EN if m in lowered)
    return (len(hits) > 0, hits)


class TaskIntentClassifier:
    """Classifies work items into inquiry vs code_change with structured decisions.

    Contract (policy v2):
    - Trusted metadata/CLI override wins and is NEVER overturned by LLM arbitration.
    - Clear, conflict-free rules decide directly (resolved/rule).
    - Empty or unrecognized input => needs_clarification, NEVER defaults to writing.
    - Mixed/conflicting signals => deferred to injectable LLM arbitration; if the
      model is unavailable or returns invalid output, stays needs_clarification.
    - Negation/read-only constraints suppress change-verb signals.
    """

    def __init__(self, *, arbitrate: bool = True) -> None:
        self._arbitrate = arbitrate

    # ------------------------------------------------------------------
    # Synchronous rule-based classification
    # ------------------------------------------------------------------
    def classify(
        self,
        *,
        title: str,
        body: str = "",
        labels: Sequence[str] = (),
        metadata: Mapping[str, str] | None = None,
    ) -> IntentDecision:
        # 1. Trusted explicit override (config layer, NOT issue text)
        meta = metadata or {}
        override = (meta.get("intent") or meta.get("task_intent") or "").strip().lower()
        if override:
            if override in _TRUSTED_INQUIRY_VALUES:
                return IntentDecision(
                    intent=TaskIntent.INQUIRY,
                    status=DecisionStatus.RESOLVED,
                    source=DecisionSource.TRUSTED_OVERRIDE,
                    reason_code=ReasonCode.TRUSTED_OVERRIDE,
                    reason="Explicit trusted metadata override: inquiry",
                    matched_signals=(f"metadata.intent={override}",),
                )
            if override in _TRUSTED_CODE_VALUES:
                return IntentDecision(
                    intent=TaskIntent.CODE_CHANGE,
                    status=DecisionStatus.RESOLVED,
                    source=DecisionSource.TRUSTED_OVERRIDE,
                    reason_code=ReasonCode.TRUSTED_OVERRIDE,
                    reason="Explicit trusted metadata override: code_change",
                    matched_signals=(f"metadata.intent={override}",),
                )
            raise ValueError(
                f"Invalid metadata intent override: {override!r}. "
                f"Allowed: {sorted(_TRUSTED_INQUIRY_VALUES | _TRUSTED_CODE_VALUES)}"
            )

        norm_title = title.lower().strip()
        norm_body = body.lower().strip()
        combined = f"{norm_title} {norm_body}".strip()

        # 2. Empty input: never default to writing
        if not combined:
            return IntentDecision(
                intent=None,
                status=DecisionStatus.NEEDS_CLARIFICATION,
                source=DecisionSource.RULE,
                reason_code=ReasonCode.EMPTY_INPUT,
                reason="Title and body are empty; cannot infer intent. Ask for clarification instead of defaulting to code change.",
            )

        # 3. Signal extraction (title + body as a whole)
        inquiry_hits = _matched_zh(combined, _INQUIRY_PATTERNS_ZH) + _matched_en(combined, _INQUIRY_EN_PATTERNS)
        change_hits = _matched_zh(combined, _CODE_CHANGE_PATTERNS_ZH) + _matched_en(combined, _CODE_CHANGE_EN_VERBS)

        # 4. Negation / read-only constraint: change verbs in negated scope are suppressed
        negated, neg_hits = _has_negation_constraint(combined)
        if negated and inquiry_hits:
            return IntentDecision(
                intent=TaskIntent.INQUIRY,
                status=DecisionStatus.RESOLVED,
                source=DecisionSource.RULE,
                reason_code=ReasonCode.NEGATION_CONSTRAINT,
                reason=f"Read-only constraint detected ({', '.join(neg_hits)}); change verbs are negated, inquiry wins.",
                matched_signals=tuple(neg_hits + inquiry_hits[:3]),
            )

        # 5. Conflict-free cases
        if inquiry_hits and not change_hits:
            # Labels only ever reinforce, never override body signals
            label_hint = bool({l.lower().strip() for l in labels} & _INQUIRY_LABELS)
            signals = tuple(inquiry_hits[:5]) + (("labels",) if label_hint else ())
            return IntentDecision(
                intent=TaskIntent.INQUIRY,
                status=DecisionStatus.RESOLVED,
                source=DecisionSource.RULE,
                reason_code=ReasonCode.INQUIRY_SIGNAL,
                reason="Clear read-only inquiry signals with no change verbs.",
                matched_signals=signals,
            )

        if change_hits and not inquiry_hits:
            return IntentDecision(
                intent=TaskIntent.CODE_CHANGE,
                status=DecisionStatus.RESOLVED,
                source=DecisionSource.RULE,
                reason_code=ReasonCode.CODE_CHANGE_SIGNAL,
                reason="Clear repository-change signals with no inquiry signals.",
                matched_signals=tuple(change_hits[:5]),
            )

        # 6. Mixed signals: body-level change action overrides title-level analysis
        #    framing ("分析X原因，请修复..." is an analysis-then-fix change task).
        if change_hits and any(v in norm_body for v in _CODE_CHANGE_PATTERNS_ZH + _CODE_CHANGE_PATTERNS_EN):
            return IntentDecision(
                intent=TaskIntent.CODE_CHANGE,
                status=DecisionStatus.RESOLVED,
                source=DecisionSource.RULE,
                reason_code=ReasonCode.CODE_CHANGE_SIGNAL,
                reason="Body contains explicit change actions; analysis framing in title does not override.",
                matched_signals=tuple(change_hits[:5]),
            )

        # 7. Remaining mixed signals: defer to arbitration (caller decides via status)
        return IntentDecision(
            intent=None,
            status=DecisionStatus.NEEDS_CLARIFICATION,
            source=DecisionSource.RULE,
            reason_code=ReasonCode.MIXED_SIGNALS,
            reason="Both inquiry and change signals present; requires arbitration.",
            matched_signals=tuple(inquiry_hits[:3] + change_hits[:3]),
        )

    # ------------------------------------------------------------------
    # Async classification with optional LLM arbitration for weak/conflicting signals
    # ------------------------------------------------------------------
    async def classify_async(
        self,
        *,
        title: str,
        body: str = "",
        labels: Sequence[str] = (),
        metadata: Mapping[str, str] | None = None,
        arbitrator=None,
    ) -> IntentDecision:
        """Async classify. Rule-resolved decisions return immediately;
        needs_clarification ones go through injectable LLM arbitration.

        `arbitrator`: optional async callable (title, body) -> TaskIntent.
        Defaults to MoMA client when not injected.
        """
        rule_decision = self.classify(title=title, body=body, labels=labels, metadata=metadata)

        # Trusted overrides and clear rules are final
        if rule_decision.status is DecisionStatus.RESOLVED:
            return rule_decision

        if not self._arbitrate:
            return rule_decision

        # --- Arbitration for mixed/empty signals ---
        import asyncio

        outcome = await self._run_arbitration(title, body, arbitrator)
        if outcome is None:
            return rule_decision  # stay needs_clarification, keep audit info

        llm_intent, llm_reason, fallback_error = outcome
        return IntentDecision(
            intent=llm_intent,
            status=DecisionStatus.RESOLVED,
            source=DecisionSource.LLM_ARBITRATION,
            reason_code=ReasonCode.LLM_ARBITRATION,
            reason=f"LLM arbitration resolved mixed signals: {llm_reason}",
            matched_signals=rule_decision.matched_signals,
            fallback_error=fallback_error,
        )

    async def _run_arbitration(self, title: str, body: str, arbitrator) -> tuple[TaskIntent, str, str | None] | None:
        """Returns (intent, reason, fallback_error) or None if arbitration failed."""
        import asyncio
        import os

        if arbitrator is not None:
            try:
                intent = await arbitrator(title, body)
                if not isinstance(intent, TaskIntent):
                    return None
                return intent, "injected arbitrator", None
            except Exception as exc:  # injected arbitrator failure is auditable
                return None

        # Built-in MoMA arbitration
        api_key = os.environ.get("MOMA_API_KEY", "").strip() or os.environ.get("DEEPSEEK_API_KEY", "").strip()
        if not api_key:
            return None

        try:
            from devopspilot.adapters.moma.client import MoMAClient
            from devopspilot.utils.model_text import extract_json_payload

            client = MoMAClient(api_key=api_key)
            issue_text = f"Title: {title}\nBody: {body}"[:_MAX_LLM_INPUT_CHARS]
            system_prompt = (
                "You are an intent classifier for a DevOps automation system. "
                "Classify the work item into exactly one of:\n"
                '- "INQUIRY": read-only Q&A, file listing, conceptual analysis, discussion, '
                "explanations — answered via issue comment, NO branch/PR.\n"
                '- "CODE_CHANGE": any repository file modification (code, docs, config, tests) '
                "requiring branch, commit and Pull Request.\n"
                "Respond with ONLY a JSON object: "
                '{"intent": "INQUIRY" | "CODE_CHANGE", "reason": "<brief>"}'
            )
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": issue_text},
            ]
            resp = await asyncio.to_thread(
                client.chat_completion,
                messages,
                model=os.environ.get("MOMA_MODEL", "deepseek-v4.1-flash"),
                temperature=0.1,
            )
            raw = resp["choices"][0]["message"]["content"]
            parsed = extract_json_payload(raw)
            if not isinstance(parsed, dict):
                return None
            raw_intent = str(parsed.get("intent", "")).strip().upper()
            llm_reason = str(parsed.get("reason", "no reason given")).strip()
            # STRICT enum acceptance — no substring matching
            if raw_intent == "INQUIRY":
                return TaskIntent.INQUIRY, llm_reason, None
            if raw_intent == "CODE_CHANGE":
                return TaskIntent.CODE_CHANGE, llm_reason, None
            return None
        except Exception as exc:
            # Auditable degradation; caller keeps needs_clarification
            _ = exc
            return None
