"""桩工具测试。"""

from ohmycode.tools.stubs.echo import echo
from ohmycode.tools.stubs.list_files import list_files
from ohmycode.tools.stubs.read_file import read_file
from ohmycode.tools.stubs import StubToolProvider


class TestEchoTool:

    def test_echo_returns_input(self):
        """echo 工具应原样返回输入。"""
        result = echo.invoke({"text": "hello"})
        assert result == "hello"

    def test_echo_empty_string(self):
        """echo 工具应能处理空字符串。"""
        result = echo.invoke({"text": ""})
        assert result == ""


class TestReadFileTool:

    def test_read_nonexistent_file(self):
        """读取不存在的文件应返回错误信息。"""
        result = read_file.invoke({"path": "/nonexistent/file.txt"})
        assert "不存在" in result or "错误" in result


class TestListFilesTool:

    def test_list_nonexistent_directory(self):
        """列出不存在的目录应返回错误信息。"""
        result = list_files.invoke({"directory": "/nonexistent/dir"})
        assert "不存在" in result or "错误" in result


class TestStubToolProvider:

    def test_returns_all_tools(self):
        """默认返回所有桩工具。"""
        provider = StubToolProvider()
        tools = provider.tools()
        names = [t.name for t in tools]
        assert "echo" in names
        assert "read_file" in names
        assert "list_files" in names

    def test_filters_enabled_tools(self):
        """只返回 enabled 列表中的工具。"""
        provider = StubToolProvider(enabled=["echo"])
        tools = provider.tools()
        assert len(tools) == 1
        assert tools[0].name == "echo"

    def test_ignores_unknown_enabled(self):
        """enabled 中不存在的工具名应被忽略。"""
        provider = StubToolProvider(enabled=["echo", "nonexistent"])
        tools = provider.tools()
        assert len(tools) == 1
        assert tools[0].name == "echo"
