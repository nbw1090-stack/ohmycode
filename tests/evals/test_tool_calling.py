"""工具调用评估 — 测试 Agent 是否正确选择和使用工具。

测试覆盖：
- TC-A: 正确工具选择
- TC-B: 参数传递
- TC-C: 多步工具链
- TC-D: 工具错误处理

所有测试需要 LLM API 调用。
"""

import pytest

from tests.evals.helpers.assertions import (
    assert_response_contains,
    assert_tool_called,
    assert_tool_call_sequence,
    assert_tool_not_called,
)
from tests.evals.helpers.recorder import run_agent_turn
from tests.evals.judge.prompts import RUBRIC_TOOL_SELECTION


# ====================================================================
# Category A: 正确工具选择
# ====================================================================

@pytest.mark.e2e
@pytest.mark.timeout(120)
class TestToolSelection:
    """TC-A: Agent 是否为不同任务选择了正确的工具。"""

    async def test_a01_read_file(self, eval_graph, recorder, eval_workspace):
        """TC-A01: 'Show me the contents of main.py' → read_file"""
        response = await run_agent_turn(eval_graph, recorder, "Show me the contents of main.py")
        assert_tool_called(recorder, "read_file")
        assert_response_contains(response, ["def "])

    async def test_a02_list_files(self, eval_graph, recorder, eval_workspace):
        """TC-A02: 'What files are in this project?' → list_files"""
        response = await run_agent_turn(eval_graph, recorder, "What files are in this project?")
        assert_tool_called(recorder, "list_files")

    async def test_a03_search_files(self, eval_graph, recorder, eval_workspace):
        """TC-A03: 'Find where the calculate function is defined' → search_files"""
        response = await run_agent_turn(
            eval_graph, recorder,
            "Find where the calculate function is defined",
        )
        assert_tool_called(recorder, "search_files")

    async def test_a04_write_file(self, eval_graph, recorder, eval_workspace):
        """TC-A04: 'Create hello.py with a hello world function' → write_file"""
        response = await run_agent_turn(
            eval_graph, recorder,
            "Create a new file called hello.py with a hello world function",
        )
        assert_tool_called(recorder, "write_file")
        # 检查文件是否实际被创建
        assert (eval_workspace / "hello.py").exists(), "hello.py should be created"

    async def test_a05_execute_command(self, eval_graph, recorder, eval_workspace):
        """TC-A05: 'Run the tests' → execute_command"""
        response = await run_agent_turn(eval_graph, recorder, "Run the tests using pytest")
        assert_tool_called(recorder, "execute_command")

    async def test_a06_no_tool_for_general_question(self, eval_graph, recorder, eval_workspace):
        """TC-A06: 'What is the difference between list and tuple?' → 无工具调用"""
        response = await run_agent_turn(
            eval_graph, recorder,
            "What is the difference between a list and a tuple in Python? Just explain briefly.",
        )
        assert_tool_not_called(recorder, "read_file")
        assert_tool_not_called(recorder, "write_file")
        assert_tool_not_called(recorder, "execute_command")
        assert_response_contains(response, ["list", "tuple"])

    async def test_a07_compare_two_files(self, eval_graph, recorder, eval_workspace):
        """TC-A07: 'Compare main.py and utils.py' → read_file x2"""
        response = await run_agent_turn(
            eval_graph, recorder,
            "Compare main.py and utils.py and tell me what each file does",
        )
        calls = recorder.find("read_file")
        assert len(calls) >= 2, f"Expected at least 2 read_file calls, got {len(calls)}"


# ====================================================================
# Category B: 参数传递
# ====================================================================

@pytest.mark.e2e
@pytest.mark.timeout(120)
class TestParameterPassing:
    """TC-B: Agent 是否传递了正确的参数。"""

    async def test_b01_read_with_offset(self, eval_graph, recorder, eval_workspace):
        """TC-B01: 'Show me lines 10-20 of main.py' → read_file 带有 offset/limit"""
        response = await run_agent_turn(
            eval_graph, recorder,
            "Show me lines 10 to 20 of main.py",
        )
        assert_tool_called(recorder, "read_file")

    async def test_b02_search_with_pattern(self, eval_graph, recorder, eval_workspace):
        """TC-B02: 'Search for TODO in all Python files' → search_files 带有 pattern"""
        response = await run_agent_turn(
            eval_graph, recorder,
            "Search for TODO comments in all Python files",
        )
        assert_tool_called(recorder, "search_files")
        # 检查 pattern 参数包含 TODO
        calls = recorder.find("search_files")
        has_todo_pattern = any(
            "todo" in str(c.args).lower() for c in calls
        )
        assert has_todo_pattern, f"Expected search pattern containing 'TODO', got: {[c.args for c in calls]}"

    async def test_b03_list_recursive(self, eval_graph, recorder, eval_workspace):
        """TC-B03: 'List all files recursively' → list_files 带有 recursive"""
        response = await run_agent_turn(
            eval_graph, recorder,
            "List all files in this project recursively, including subdirectories",
        )
        assert_tool_called(recorder, "list_files")


# ====================================================================
# Category C: 多步工具链
# ====================================================================

@pytest.mark.e2e
@pytest.mark.timeout(180)
class TestMultiStepChains:
    """TC-C: Agent 是否正确执行多步工具链。"""

    async def test_c01_search_then_read(self, eval_graph, recorder, eval_workspace):
        """TC-C01: 'Find the calculate function and show it' → search_files → read_file"""
        response = await run_agent_turn(
            eval_graph, recorder,
            "Find where the calculate function is defined and show me the code",
        )
        assert_tool_call_sequence(recorder, ["search_files", "read_file"])

    async def test_c02_read_then_write(self, eval_graph, recorder, eval_workspace):
        """TC-C02: 'Fix the bug in main.py' → read_file → write_file"""
        response = await run_agent_turn(
            eval_graph, recorder,
            "Fix the off-by-one bug in the greet function in main.py. "
            "The loop should include all names, not skip the last one.",
        )
        assert_tool_call_sequence(recorder, ["read_file", "write_file"])

    async def test_c03_search_fix_test(self, eval_graph, recorder, eval_workspace):
        """TC-C03: 'Find the error, fix it, then run tests' → search/read → write → execute"""
        response = await run_agent_turn(
            eval_graph, recorder,
            "Find the off-by-one bug in main.py, fix it, then run the tests to verify",
        )
        # 至少应该有 read 和 write
        assert_tool_called(recorder, "read_file")
        assert_tool_called(recorder, "write_file")


# ====================================================================
# Category D: 工具错误处理
# ====================================================================

@pytest.mark.e2e
@pytest.mark.timeout(120)
class TestToolErrorHandling:
    """TC-D: Agent 如何处理工具错误。"""

    async def test_d01_nonexistent_file(self, eval_graph, recorder, eval_workspace):
        """TC-D01: 'Read nonexistent.py' → agent 报告文件不存在"""
        response = await run_agent_turn(
            eval_graph, recorder,
            "Show me the contents of nonexistent_file.py",
        )
        assert_tool_called(recorder, "read_file")
        # Agent 应该报告文件不存在
        error_indicators = ["不存在", "not found", "error", "错误", "无法", "no such"]
        has_error = any(ind in response.lower() for ind in error_indicators)
        assert has_error, f"Agent should report file not found. Response: {response[:300]}"

    async def test_d02_command_failure(self, eval_graph, recorder, eval_workspace):
        """TC-D02: 'Run python invalid_script.py' → agent 报告错误"""
        response = await run_agent_turn(
            eval_graph, recorder,
            "Run the command: python invalid_script_that_does_not_exist.py",
        )
        assert_tool_called(recorder, "execute_command")
        # Agent 应该报告错误
        error_indicators = ["错误", "error", "失败", "failed", "不存在", "找不到"]
        has_error = any(ind in response.lower() for ind in error_indicators)
        assert has_error, f"Agent should report command failure. Response: {response[:300]}"
