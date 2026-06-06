"""UsageTracker 测试。"""

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from ohmycode.session.models import Session, TokenUsage
from ohmycode.session.usage import UsageTracker


class TestUsageTracker:
    def test_initial_state(self):
        tracker = UsageTracker()
        assert tracker.cumulative.total_tokens == 0
        assert tracker.turns == 0

    def test_record(self):
        tracker = UsageTracker()
        usage = TokenUsage(input_tokens=100, output_tokens=50)
        tracker.record(usage)
        assert tracker.latest_turn.input_tokens == 100
        assert tracker.cumulative.input_tokens == 100
        assert tracker.turns == 1

    def test_cumulative(self):
        tracker = UsageTracker()
        tracker.record(TokenUsage(input_tokens=100))
        tracker.record(TokenUsage(input_tokens=200))
        assert tracker.cumulative.input_tokens == 300
        assert tracker.latest_turn.input_tokens == 200
        assert tracker.turns == 2

    def test_record_from_metadata(self):
        tracker = UsageTracker()
        tracker.record_from_metadata({
            "input_tokens": 150,
            "output_tokens": 30,
            "cache_creation_input_tokens": 10,
            "cache_read_input_tokens": 50,
        })
        assert tracker.cumulative.input_tokens == 150
        assert tracker.cumulative.cache_read_input_tokens == 50
        assert tracker.turns == 1

    def test_record_from_empty_metadata(self):
        tracker = UsageTracker()
        tracker.record_from_metadata(None)
        tracker.record_from_metadata({})
        assert tracker.turns == 2  # still counts turns
        assert tracker.cumulative.total_tokens == 0

    def test_from_session(self):
        session = Session()
        msg1 = AIMessage(content="hello")
        msg1.usage_metadata = {
            "input_tokens": 100,
            "output_tokens": 30,
            "cache_creation_input_tokens": 0,
            "cache_read_input_tokens": 0,
        }
        msg2 = AIMessage(content="world")
        msg2.usage_metadata = {
            "input_tokens": 200,
            "output_tokens": 50,
            "cache_creation_input_tokens": 10,
            "cache_read_input_tokens": 0,
        }
        session.push_message(HumanMessage(content="prompt"))
        session.push_message(msg1)
        session.push_message(HumanMessage(content="prompt2"))
        session.push_message(msg2)

        tracker = UsageTracker.from_session(session)
        assert tracker.cumulative.input_tokens == 300
        assert tracker.cumulative.output_tokens == 80
        assert tracker.cumulative.cache_creation_input_tokens == 10
        assert tracker.turns == 2

    def test_from_empty_session(self):
        session = Session()
        tracker = UsageTracker.from_session(session)
        assert tracker.cumulative.total_tokens == 0
        assert tracker.turns == 0

    def test_reset(self):
        tracker = UsageTracker()
        tracker.record(TokenUsage(input_tokens=500))
        tracker.reset()
        assert tracker.cumulative.total_tokens == 0
        assert tracker.turns == 0
        assert tracker.latest_turn.total_tokens == 0
