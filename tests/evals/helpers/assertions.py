"""自定义断言辅助函数 — 用于评估测试中的结构化检查。"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tests.evals.helpers.recorder import ToolCallRecorder


def assert_tool_called(
    recorder: ToolCallRecorder,
    tool_name: str,
    expected_args_subset: dict | None = None,
) -> None:
    """断言 agent 调用了指定工具。

    Args:
        recorder: 工具调用记录器
        tool_name: 期望的工具名称
        expected_args_subset: 如果提供，检查工具参数包含这些键值对

    Raises:
        AssertionError: 如果工具未被调用或参数不匹配
    """
    calls = recorder.find(tool_name)
    assert calls, (
        f"Expected tool '{tool_name}' to be called, "
        f"but only these tools were called: {recorder.tool_names}"
    )

    if expected_args_subset:
        matched = False
        for call in calls:
            if all(call.args.get(k) == v for k, v in expected_args_subset.items()):
                matched = True
                break
        assert matched, (
            f"Tool '{tool_name}' was called but no call matched args subset "
            f"{expected_args_subset}. Actual calls: "
            f"{[c.args for c in calls]}"
        )


def assert_tool_not_called(recorder: ToolCallRecorder, tool_name: str) -> None:
    """断言 agent 未调用指定工具。"""
    calls = recorder.find(tool_name)
    assert not calls, (
        f"Expected tool '{tool_name}' NOT to be called, "
        f"but it was called {len(calls)} time(s). "
        f"All tool calls: {recorder.tool_names}"
    )


def assert_tool_call_sequence(
    recorder: ToolCallRecorder,
    expected_names: list[str],
) -> None:
    """断言工具调用的顺序匹配期望序列。

    检查 expected_names 是否是 recorder.tool_names 的子序列。
    """
    actual = recorder.tool_names
    # 检查子序列匹配
    idx = 0
    for expected in expected_names:
        while idx < len(actual) and actual[idx] != expected:
            idx += 1
        assert idx < len(actual), (
            f"Expected tool call sequence {expected_names}, "
            f"but actual sequence was {actual}. "
            f"Missing '{expected}' after position {idx}."
        )
        idx += 1


def assert_response_contains(response: str, phrases: list[str]) -> None:
    """断言回复文本包含所有期望的短语。"""
    response_lower = response.lower()
    missing = [p for p in phrases if p.lower() not in response_lower]
    assert not missing, (
        f"Response does not contain expected phrases: {missing}. "
        f"Response: {response[:500]}..."
    )


def assert_response_contains_any(response: str, phrases: list[str]) -> None:
    """断言回复文本至少包含其中一个期望短语。"""
    response_lower = response.lower()
    found = any(p.lower() in response_lower for p in phrases)
    assert found, (
        f"Response does not contain any of: {phrases}. "
        f"Response: {response[:500]}..."
    )


def assert_response_not_contains(response: str, phrases: list[str]) -> None:
    """断言回复文本不包含指定的短语。"""
    response_lower = response.lower()
    found = [p for p in phrases if p.lower() in response_lower]
    assert not found, (
        f"Response unexpectedly contains phrases: {found}. "
        f"Response: {response[:500]}..."
    )
