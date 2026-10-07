"""The strict Live path obtains an independent, diff-bound model review."""

import pytest
from devopspilot.adapters.moma.review import review_diff
from devopspilot.contracts.review import ReviewVerdict, ReviewResult


class Client:
    def __init__(self, verdict="approved"):
        self.verdict = verdict
        self.requests = []

    def chat_completion(self, messages, **kwargs):
        self.requests.append((messages, kwargs))
        return {
            "choices": [
                {
                    "message": {
                        "content": '{"verdict":"'
                        + self.verdict
                        + '","summary":"checked","findings":[]}'
                    }
                }
            ],
            "usage": {"prompt_tokens": 100, "completion_tokens": 20},
        }


def test_independent_review_binds_actual_diff_and_model():
    client = Client()
    result, events = review_diff(
        client,
        model="configured-review-model",
        diff="actual diff",
        test_summary="tests passed",
        sequence=10,
    )
    assert (
        result.verdict is ReviewVerdict.APPROVED
        and result.diff_digest == ReviewResult.calculate_diff_digest("actual diff")
    )
    assert client.requests[0][1]["model"] == "configured-review-model"
    assert events[0].attributes["input_tokens"] == 100


def test_unknown_review_verdict_fails_closed():
    with pytest.raises(ValueError):
        review_diff(
            Client("maybe"), model="review", diff="d", test_summary="", sequence=0
        )


def test_rejected_review_remains_rejected():
    result, events = review_diff(
        Client("rejected"), model="review", diff="d", test_summary="", sequence=0
    )
    assert result.verdict is ReviewVerdict.REJECTED
