"""测试内置工具的核心逻辑和安全检查。"""

import os

import pytest

from ohmycode.tools.base import build_tool
from ohmycode.tools.builtins.echo import EchoDef
from ohmycode.tools.builtins.execute_command import ExecuteCommandDef
from ohmycode.tools.builtins.list_files import ListFilesDef
from ohmycode.tools.builtins.read_file import ReadFileDef
from ohmycode.tools.builtins.search_files import SearchFilesDef
from ohmycode.tools.builtins.write_file import WriteFileDef


# ===== Echo =====


class TestEchoTool:

    def test_echo_returns_input(self):
        tool = build_tool(EchoDef())
        assert tool.invoke({"text": "hello"}) == "hello"

    def test_echo_empty_string(self):
        tool = build_tool(EchoDef())
        assert tool.invoke({"text": ""}) == ""


# ===== ReadFile =====


class TestReadFileTool:

    def test_read_existing_file(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        f = tmp_path / "test.txt"
        f.write_text("line1\nline2\nline3\n")

        tool = build_tool(ReadFileDef())
        result = tool.invoke({"path": str(f)})
        assert "line1" in result
        assert "line2" in result
        assert "共 3 行" in result

    def test_read_with_offset_and_limit(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        f = tmp_path / "test.txt"
        f.write_text("\n".join(f"line{i}" for i in range(20)))

        tool = build_tool(ReadFileDef())
        result = tool.invoke({"path": str(f), "offset": 5, "limit": 3})
        assert "line5" in result
        assert "line7" in result
        assert "line8" not in result

    def test_read_nonexistent_file(self, tmp_path, monkeypatch):
        """读取不存在的文件应返回错误（路径在 CWD 内）。"""
        monkeypatch.chdir(tmp_path)
        tool = build_tool(ReadFileDef())
        result = tool.invoke({"path": "nonexistent_file.txt"})
        assert "不存在" in result

    def test_read_directory(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        tool = build_tool(ReadFileDef())
        result = tool.invoke({"path": "."})
        assert "目录" in result

    def test_path_traversal_denied(self):
        tool = build_tool(ReadFileDef())
        result = tool.invoke({"path": "../../../etc/passwd"})
        assert "权限被拒绝" in result or "超出工作目录" in result

    def test_binary_file_rejected(self):
        tool = build_tool(ReadFileDef())
        result = tool.invoke({"path": "image.png"})
        assert "二进制" in result


# ===== WriteFile =====


class TestWriteFileTool:

    def test_create_new_file(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        target = tmp_path / "new.txt"
        tool = build_tool(WriteFileDef())
        result = tool.invoke({"path": str(target), "content": "hello"})
        assert "成功创建" in result
        assert target.read_text() == "hello"

    def test_overwrite_existing_file(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        target = tmp_path / "existing.txt"
        target.write_text("old")
        tool = build_tool(WriteFileDef())
        result = tool.invoke({"path": str(target), "content": "new"})
        assert "覆盖" in result
        assert target.read_text() == "new"

    def test_append_mode(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        target = tmp_path / "append.txt"
        target.write_text("first\n")
        tool = build_tool(WriteFileDef())
        result = tool.invoke({"path": str(target), "content": "second\n", "append": True})
        assert "追加" in result
        assert target.read_text() == "first\nsecond\n"

    def test_create_dirs(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        target = tmp_path / "sub" / "dir" / "file.txt"
        tool = build_tool(WriteFileDef())
        result = tool.invoke({"path": str(target), "content": "deep", "create_dirs": True})
        assert "成功创建" in result
        assert target.read_text() == "deep"

    def test_path_traversal_denied(self):
        tool = build_tool(WriteFileDef())
        result = tool.invoke({"path": "/tmp/evil.txt", "content": "hack"})
        assert "权限被拒绝" in result or "超出工作目录" in result


# ===== ListFiles =====


class TestListFilesTool:

    def test_list_directory(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "file1.txt").write_text("a")
        (tmp_path / "file2.py").write_text("b")
        (tmp_path / "subdir").mkdir()

        tool = build_tool(ListFilesDef())
        result = tool.invoke({"directory": str(tmp_path)})
        assert "file1.txt" in result
        assert "file2.py" in result
        assert "subdir" in result

    def test_list_with_pattern(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "a.py").write_text("")
        (tmp_path / "b.txt").write_text("")

        tool = build_tool(ListFilesDef())
        result = tool.invoke({"directory": str(tmp_path), "pattern": "*.py"})
        assert "a.py" in result
        assert "b.txt" not in result

    def test_list_nonexistent_directory(self, tmp_path, monkeypatch):
        """列出不存在的目录应返回错误（路径在 CWD 内）。"""
        monkeypatch.chdir(tmp_path)
        tool = build_tool(ListFilesDef())
        result = tool.invoke({"directory": "nonexistent_dir"})
        assert "不存在" in result

    def test_path_traversal_denied(self):
        tool = build_tool(ListFilesDef())
        result = tool.invoke({"directory": "../../etc"})
        assert "权限被拒绝" in result or "超出工作目录" in result


# ===== ExecuteCommand =====


class TestExecuteCommandTool:

    def test_simple_command(self):
        tool = build_tool(ExecuteCommandDef())
        result = tool.invoke({"command": "echo hello"})
        assert "hello" in result

    def test_command_with_nonzero_exit(self):
        tool = build_tool(ExecuteCommandDef())
        result = tool.invoke({"command": "exit 1"})
        assert "退出码" in result

    def test_dangerous_command_denied(self):
        tool = build_tool(ExecuteCommandDef())
        result = tool.invoke({"command": "rm -rf /"})
        assert "权限被拒绝" in result

    def test_empty_command_rejected(self):
        tool = build_tool(ExecuteCommandDef())
        result = tool.invoke({"command": "  "})
        assert "输入验证失败" in result

    def test_timeout(self):
        tool = build_tool(ExecuteCommandDef())
        result = tool.invoke({"command": "sleep 60", "timeout": 1})
        assert "超时" in result

    def test_captures_stderr(self):
        tool = build_tool(ExecuteCommandDef())
        result = tool.invoke({"command": "echo error >&2"})
        assert "error" in result


# ===== SearchFiles =====


class TestSearchFilesTool:

    def test_search_finds_pattern(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "a.py").write_text("def hello():\n    pass\n")
        (tmp_path / "b.py").write_text("def world():\n    pass\n")

        tool = build_tool(SearchFilesDef())
        result = tool.invoke({"pattern": "hello", "directory": str(tmp_path)})
        assert "a.py" in result
        assert "1 个匹配" in result

    def test_search_no_match(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "a.py").write_text("nothing here")

        tool = build_tool(SearchFilesDef())
        result = tool.invoke({"pattern": "nonexistent_pattern", "directory": str(tmp_path)})
        assert "未找到" in result

    def test_search_with_file_pattern(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "a.py").write_text("target_string\n")
        (tmp_path / "b.txt").write_text("target_string\n")

        tool = build_tool(SearchFilesDef())
        result = tool.invoke({
            "pattern": "target_string",
            "directory": str(tmp_path),
            "file_pattern": "*.py",
        })
        assert "a.py" in result
        assert "b.txt" not in result

    def test_invalid_regex_rejected(self):
        tool = build_tool(SearchFilesDef())
        result = tool.invoke({"pattern": "[invalid"})
        assert "输入验证失败" in result or "正则" in result

    def test_path_traversal_denied(self):
        tool = build_tool(SearchFilesDef())
        result = tool.invoke({"pattern": "test", "directory": "../../etc"})
        assert "权限被拒绝" in result or "超出工作目录" in result
