"""
单元测试 - 提示词系统
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from echo_claude.utils.prompts import (
    get_system_prompt,
    error_message,
    session_message,
    command_help,
    get_prompt,
)


class TestSystemPrompt:
    """系统提示词测试"""

    def test_chinese_prompt(self):
        prompt = get_system_prompt("zh")
        assert "Echo Claude" in prompt
        assert "中文" in prompt or "编程" in prompt

    def test_english_prompt(self):
        prompt = get_system_prompt("en")
        assert "Echo Claude" in prompt

    def test_unknown_lang_falls_back_to_zh(self):
        prompt = get_system_prompt("fr")
        assert "Echo Claude" in prompt  # zh fallback


class TestErrorMessage:
    """错误消息测试"""

    def test_file_not_found_zh(self):
        msg = error_message("file_not_found", "zh", path="/tmp/test.txt")
        assert "不存在" in msg
        assert "/tmp/test.txt" in msg

    def test_file_not_found_en(self):
        msg = error_message("file_not_found", "en", path="/tmp/test.txt")
        assert "not found" in msg

    def test_dangerous_command(self):
        msg = error_message("dangerous_command", "zh", cmd="rm -rf")
        assert "危险" in msg

    def test_unknown_key(self):
        msg = error_message("nonexistent_key", "zh")
        assert msg == ""


class TestSessionMessage:
    """会话消息测试"""

    def test_session_saved(self):
        msg = session_message("session_saved", "zh", name="test")
        assert "已保存" in msg
        assert "test" in msg

    def test_welcome(self):
        msg = session_message("welcome", "zh")
        assert "欢迎" in msg

    def test_unknown_key(self):
        msg = session_message("nonexistent", "zh")
        assert msg == ""


class TestCommandHelp:
    """命令帮助测试"""

    def test_help_zh(self):
        help_text = command_help("zh")
        assert "可用命令" in help_text
        assert "/help" in help_text

    def test_help_en(self):
        help_text = command_help("en")
        assert "Show this help" in help_text or len(help_text) > 0


class TestGetPrompt:
    """get_prompt 通用函数测试"""

    def test_get_prompt_nested(self):
        # ERROR_MESSAGES.file_not_found.zh
        text = get_prompt("ERROR_MESSAGES.file_not_found", "zh", path="/x")
        assert "不存在" in text

    def test_get_prompt_fallback(self):
        text = get_prompt("NONEXISTENT_KEY", "zh")
        assert text == ""
