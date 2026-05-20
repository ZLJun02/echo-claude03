"""
单元测试 - 工具系统
"""
import os
import json
import tempfile
import pytest
from pathlib import Path

# 把项目根目录加入路径
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from echo_claude.core.tools import (
    FileReadTool, FileWriteTool, ShellTool, ToolRegistry, ToolResult
)


class TestFileReadTool:
    """文件读取工具测试"""

    def test_read_text_file(self):
        tool = FileReadTool(safe_dirs=[str(Path.cwd())])
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write("line1\nline2\nline3\n")
            tmp_path = f.name
        try:
            result = tool.execute(path=tmp_path)
            assert result.success
            assert "line1" in result.output
            assert result.metadata["line_count"] == 3
        finally:
            os.unlink(tmp_path)

    def test_read_with_line_range(self):
        tool = FileReadTool(safe_dirs=[str(Path.cwd())])
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write("a\nb\nc\nd\ne\n")
            tmp_path = f.name
        try:
            result = tool.execute(path=tmp_path, start_line=2, end_line=4)
            assert result.success
            assert "b" in result.output
            assert "d" in result.output
            assert "e" not in result.output
        finally:
            os.unlink(tmp_path)

    def test_file_not_found(self):
        tool = FileReadTool(safe_dirs=[str(Path.cwd())])
        result = tool.execute(path="/nonexistent/file_12345.txt")
        assert not result.success
        assert "不存在" in result.error

    def test_path_not_in_safe_dir(self):
        tool = FileReadTool(safe_dirs=["/tmp/safe"])
        result = tool.execute(path="/etc/passwd")
        assert not result.success
        assert "安全目录" in result.error


class TestFileWriteTool:
    """文件写入工具测试"""

    def test_write_and_append(self):
        safe_dir = str(Path.cwd())
        tool = FileWriteTool(safe_dirs=[safe_dir])
        tmp_path = os.path.join(safe_dir, "_test_write.txt")
        try:
            result = tool.execute(path=tmp_path, content="hello")
            assert result.success
            assert "写入" in result.output

            result2 = tool.execute(path=tmp_path, content=" world", append=True)
            assert result2.success
            assert "追加" in result2.output

            with open(tmp_path, 'r') as f:
                content = f.read()
            assert "hello world" in content
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def test_disallowed_extension(self):
        tool = FileWriteTool(safe_dirs=[str(Path.cwd())])
        result = tool.execute(path="test.exe", content="bad")
        assert not result.success


class TestShellTool:
    """Shell 工具测试"""

    def test_safe_command(self):
        tool = ShellTool(working_dir=str(Path.cwd()))
        result = tool.execute(command="echo hello")
        assert result.success
        assert "hello" in result.output

    def test_dangerous_command_blocked(self):
        tool = ShellTool(working_dir=str(Path.cwd()))
        result = tool.execute(command="rm -rf /")
        assert not result.success
        assert "危险" in result.error

    def test_sudo_blocked(self):
        tool = ShellTool(working_dir=str(Path.cwd()))
        result = tool.execute(command="sudo ls")
        assert not result.success

    def test_ls_allowed(self):
        tool = ShellTool(working_dir=str(Path.cwd()))
        result = tool.execute(command="ls")
        assert result.success


class TestToolRegistry:
    """工具注册表测试"""

    def test_register_and_get(self):
        # Reset for test
        ToolRegistry._tools = {}
        ToolRegistry._initialized = False

        tool = FileReadTool(safe_dirs=[str(Path.cwd())])
        ToolRegistry.register(tool)
        assert ToolRegistry.get_tool("file_read") is not None

    def test_execute_nonexistent_tool(self):
        ToolRegistry._tools = {}
        with pytest.raises(ValueError, match="不存在"):
            ToolRegistry.execute("nonexistent_tool", {})

    def test_list_tools(self):
        ToolRegistry._tools = {}
        ToolRegistry.register(FileReadTool(safe_dirs=[str(Path.cwd())]))
        tools = ToolRegistry.list_tools()
        assert "file_read" in tools
        assert tools["file_read"]["enabled"] is True

    def test_get_definitions(self):
        ToolRegistry._tools = {}
        ToolRegistry.register(FileReadTool(safe_dirs=[str(Path.cwd())]))
        defs = ToolRegistry.get_definitions()
        assert len(defs) == 1
        assert defs[0].name == "file_read"
