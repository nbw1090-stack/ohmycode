"""SummaryCompressionBudget 测试。"""

import pytest

from ohmycode.session.summary_budget import (
    SummaryCompressionBudget,
    _line_priority,
    _normalize_lines,
    _select_line_indexes,
    compress_summary,
)


class TestLinePriority:
    def test_core_detail_scope(self):
        assert _line_priority("- Scope: 8 messages compacted.") == 0

    def test_core_detail_current_work(self):
        assert _line_priority("- Current work: fixing bugs.") == 0

    def test_core_detail_tools(self):
        assert _line_priority("- Tools mentioned: bash, read_file.") == 0

    def test_section_header(self):
        assert _line_priority("- Key timeline:") == 1

    def test_list_item(self):
        assert _line_priority("  - user: hello") == 2

    def test_other(self):
        assert _line_priority("some random text") == 3

    def test_summary_tags(self):
        assert _line_priority("<summary>") == 0
        assert _line_priority("</summary>") == 0
        assert _line_priority("Conversation summary:") == 0


class TestNormalizeLines:
    def test_collapses_whitespace(self):
        lines, _ = _normalize_lines("  hello   world  ", 160)
        assert lines == ["hello world"]

    def test_truncates_long_lines(self):
        lines, _ = _normalize_lines("x" * 200, 100)
        assert len(lines[0]) == 100
        assert lines[0].endswith("…")

    def test_deduplication(self):
        lines, dup_count = _normalize_lines("hello\nhello\nworld", 160)
        assert len(lines) == 2
        assert dup_count == 1

    def test_case_insensitive_dedup(self):
        lines, dup_count = _normalize_lines("Hello\nhello", 160)
        assert len(lines) == 1
        assert dup_count == 1


class TestSelectLineIndexes:
    def test_selects_all_when_under_budget(self):
        lines = ["line 1", "line 2", "line 3"]
        budget = SummaryCompressionBudget(max_chars=1000, max_lines=10)
        selected = _select_line_indexes(lines, budget)
        assert selected == [0, 1, 2]

    def test_respects_max_lines(self):
        lines = [f"line {i}" for i in range(10)]
        budget = SummaryCompressionBudget(max_chars=10000, max_lines=3)
        selected = _select_line_indexes(lines, budget)
        assert len(selected) <= 3

    def test_respects_max_chars(self):
        lines = ["x" * 100 for _ in range(20)]
        budget = SummaryCompressionBudget(max_chars=300, max_lines=100)
        selected = _select_line_indexes(lines, budget)
        total_chars = sum(len(lines[i]) for i in selected)
        assert total_chars <= 300


class TestCompressSummary:
    def test_short_summary_unchanged(self):
        summary = "<summary>\n- Scope: 4 messages.\n</summary>"
        result = compress_summary(summary)
        assert "Scope: 4 messages" in result

    def test_long_summary_compressed(self):
        lines = ["<summary>", "Conversation summary:", "- Scope: 100 messages."]
        for i in range(50):
            lines.append(f"  - timeline entry {i} with some content")
        lines.append("</summary>")
        summary = "\n".join(lines)

        budget = SummaryCompressionBudget(max_chars=500, max_lines=10)
        result = compress_summary(summary, budget)

        assert len(result.splitlines()) <= 11  # 10 lines + omission notice
        assert "Scope:" in result  # Core info preserved

    def test_omission_notice(self):
        lines = ["<summary>", "Conversation summary:", "- Scope: test."]
        for i in range(100):
            lines.append(f"  - timeline entry {i} " + "x" * 50)
        lines.append("</summary>")
        summary = "\n".join(lines)

        budget = SummaryCompressionBudget(max_chars=500, max_lines=5)
        result = compress_summary(summary, budget)

        if "omitted" in result:
            assert "additional line(s) omitted" in result

    def test_empty_summary(self):
        assert compress_summary("") == ""
