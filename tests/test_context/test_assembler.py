"""上下文装配器测试。"""

from ohmycode.context.assembler import assemble_system_prompt, collect_context_snippets
from ohmycode.context.parts import ContextSnippet, SystemPromptPart
from ohmycode.context.providers.identity import IdentityContextProvider


class FakeProvider:
    """用于测试的假 ContextProvider。"""

    def __init__(self, parts, snippets=None):
        self._parts = parts
        self._snippets = snippets or []

    def system_prompt_parts(self):
        return self._parts

    def context_snippets(self):
        return self._snippets


class TestAssembleSystemPrompt:

    def test_single_provider(self):
        """单个 provider 的段落应正确拼接。"""
        provider = FakeProvider([
            SystemPromptPart(name="a", content="Hello", priority=10),
        ])
        result = assemble_system_prompt([provider])
        assert result == "Hello"

    def test_multiple_providers_sorted_by_priority(self):
        """多个 provider 的段落应按 priority 排序。"""
        providers = [
            FakeProvider([SystemPromptPart(name="b", content="Second", priority=50)]),
            FakeProvider([SystemPromptPart(name="a", content="First", priority=10)]),
        ]
        result = assemble_system_prompt(providers)
        assert result == "First\n\nSecond"

    def test_deduplication_by_name(self):
        """同名段落应去重（后注册的覆盖先注册的）。"""
        providers = [
            FakeProvider([SystemPromptPart(name="x", content="Old", priority=10)]),
            FakeProvider([SystemPromptPart(name="x", content="New", priority=20)]),
        ]
        result = assemble_system_prompt(providers)
        assert result == "New"

    def test_empty_providers(self):
        """空 provider 列表应返回空字符串。"""
        result = assemble_system_prompt([])
        assert result == ""


class TestCollectContextSnippets:

    def test_collects_snippets(self):
        """应正确收集上下文片段。"""
        providers = [
            FakeProvider(
                [],
                [ContextSnippet(name="s1", content="data1")],
            ),
        ]
        result = collect_context_snippets(providers)
        assert result == {"s1": "data1"}


class TestIdentityContextProvider:

    def test_provides_identity_parts(self):
        """IdentityContextProvider 应提供多个身份与行为规范段落。"""
        provider = IdentityContextProvider()
        parts = provider.system_prompt_parts()
        assert len(parts) == 4
        names = [p.name for p in parts]
        assert names == ["intro", "system", "doing_tasks", "executing_actions"]
        priorities = [p.priority for p in parts]
        assert priorities == [10, 20, 30, 40]
        assert "ohmycode" in parts[0].content

    def test_no_context_snippets(self):
        """IdentityContextProvider 不应提供上下文片段。"""
        provider = IdentityContextProvider()
        assert provider.context_snippets() == []
