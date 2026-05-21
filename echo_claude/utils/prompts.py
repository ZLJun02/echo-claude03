"""
提示词管理模块
提供中文友好的系统提示词和工具调用提示
"""

from typing import Dict


# 默认系统提示词（中文优先）
DEFAULT_SYSTEM_PROMPT_ZH = """你是一个智能编程助手，名为 Echo Claude。

你的核心能力：
1. 理解和生成各种编程语言的代码
2. 分析和解释代码功能、算法和设计
3. 调试问题并提供修复方案
4. 搜索、读取和分析项目文件
5. 执行系统命令（在安全沙箱内）

工作原则：
• 优先使用工具获取实际信息，不要猜测
• 提供的代码要简洁、高效、安全，遵循最佳实践
• 对中国用户友好，用中文交流（除非用户特别要求英文）
• 尊重用户隐私，不在回复中泄露敏感信息
• 明确说明操作风险，谨慎使用文件写入和Shell命令

输出格式：
• 使用 Markdown 格式
• 代码块明确指定语言
• 关键点高亮说明
• 保持回复简洁但有帮助
"""

DEFAULT_SYSTEM_PROMPT_EN = """You are an intelligent programming assistant named Echo Claude.

Your core abilities:
1. Understand and generate code in various programming languages
2. Analyze and explain code functionality, algorithms, and design
3. Debug issues and provide fixes
4. Search, read, and analyze project files
5. Execute system commands (in secure sandbox)

Working principles:
• Prefer using tools to get actual information, don't guess
• Provide concise, efficient, and secure code following best practices
• Be friendly to Chinese users, communicate in Chinese (unless English requested)
• Respect user privacy, never leak sensitive information
• Clearly state operational risks, be cautious with file writes and shell commands

Output format:
• Use Markdown formatting
• Specify language in code blocks
• Highlight key points
• Keep responses concise but helpful
"""

# 工具相关提示词
TOOL_PROMPTS = {
    "file_read": {
        "zh": "读取指定文件内容，可用于分析代码或查看配置",
        "en": "Read the content of a specified file to analyze code or view configuration"
    },
    "file_write": {
        "zh": "将内容写入文件。注意：此操作会修改文件，请谨慎使用",
        "en": "Write content to a file. Warning: This modifies files, use with caution"
    },
    "shell": {
        "zh": "在安全沙箱内执行Shell命令。仅限于白名单命令",
        "en": "Execute shell commands in a secure sandbox. Only whitelisted commands allowed"
    }
}

# 错误提示
ERROR_MESSAGES = {
    "file_not_found": {
        "zh": "文件不存在: {path}",
        "en": "File not found: {path}"
    },
    "permission_denied": {
        "zh": "无权限访问: {path}",
        "en": "Permission denied: {path}"
    },
    "unsafe_path": {
        "zh": "路径不在安全目录内: {path}",
        "en": "Path not in safe directories: {path}"
    },
    "command_not_allowed": {
        "zh": "命令不在白名单内: {cmd}",
        "en": "Command not whitelisted: {cmd}"
    },
    "dangerous_command": {
        "zh": "检测到危险命令: {cmd}",
        "en": "Dangerous command detected: {cmd}"
    },
    "tool_execution_failed": {
        "zh": "工具执行失败: {error}",
        "en": "Tool execution failed: {error}"
    }
}

# 会话相关提示
SESSION_PROMPTS = {
    "welcome": {
        "zh": "欢迎使用 Echo Claude！输入 `/help` 查看帮助，输入 `/quit` 退出。",
        "en": "Welcome to Echo Claude! Type `/help` for help, `/quit` to exit."
    },
    "session_saved": {
        "zh": "✅ 会话已保存: {name}",
        "en": "✅ Session saved: {name}"
    },
    "session_loaded": {
        "zh": "✅ 会话已加载: {name}",
        "en": "✅ Session loaded: {name}"
    },
    "session_deleted": {
        "zh": "✅ 会话已删除: {name}",
        "en": "✅ Session deleted: {name}"
    },
    "no_session": {
        "zh": "当前没有活跃会话",
        "en": "No active session"
    }
}

# 命令帮助
COMMAND_HELP = {
    "/help": {
        "zh": "显示此帮助信息",
        "en": "Show this help message"
    },
    "/quit": {
        "zh": "退出程序",
        "en": "Quit the program"
    },
    "/clear": {
        "zh": "清空当前会话",
        "en": "Clear current session"
    },
    "/save [name]": {
        "zh": "保存当前会话（可选指定名称）",
        "en": "Save current session (optional name)"
    },
    "/load [name]": {
        "zh": "加载会话（列出未指定名称）",
        "en": "Load session (list if no name)"
    },
    "/model [name]": {
        "zh": "显示或切换模型",
        "en": "Show or switch model"
    },
    "/tool [name]": {
        "zh": "显示工具列表或测试工具",
        "en": "List tools or test a tool"
    },
    "/system <prompt>": {
        "zh": "设置系统提示词",
        "en": "Set system prompt"
    }
}


# Registry of all prompt dictionaries for get_prompt lookup
_PROMPT_REGISTRY = {
    "ERROR_MESSAGES": ERROR_MESSAGES,
    "SESSION_PROMPTS": SESSION_PROMPTS,
    "COMMAND_HELP": COMMAND_HELP,
    "TOOL_PROMPTS": TOOL_PROMPTS,
}


def get_prompt(key: str, lang: str = "zh", **kwargs) -> str:
    """
    Get a prompt by key from the prompt registry.

    Args:
        key: Prompt key, supports dot paths like "ERROR_MESSAGES.file_not_found"
        lang: Language (zh/en)
        **kwargs: Formatting parameters

    Returns:
        Formatted prompt string, or empty string if key not found
    """
    keys = key.replace("'", "").replace('"', "").replace("[", ".").replace("]", "").split(".")
    obj = _PROMPT_REGISTRY
    try:
        for k in keys:
            if isinstance(obj, dict):
                obj = obj.get(k, {})
            else:
                return ""
        text = obj.get(lang, obj.get("zh", "")) if isinstance(obj, dict) else ""
    except Exception:
        return ""

    if kwargs and text:
        try:
            text = text.format(**kwargs)
        except KeyError:
            pass

    return text


def get_system_prompt(lang: str = "zh") -> str:
    """获取系统提示词"""
    return DEFAULT_SYSTEM_PROMPT_ZH if lang.startswith("zh") else DEFAULT_SYSTEM_PROMPT_EN


def error_message(key: str, lang: str = "zh", **kwargs) -> str:
    """获取错误消息"""
    prompt_dict = ERROR_MESSAGES.get(key, {})
    text = prompt_dict.get(lang, prompt_dict.get("zh", ""))
    if kwargs and text:
        try:
            text = text.format(**kwargs)
        except KeyError:
            pass
    return text


def session_message(key: str, lang: str = "zh", **kwargs) -> str:
    """获取会话消息"""
    prompt_dict = SESSION_PROMPTS.get(key, {})
    text = prompt_dict.get(lang, prompt_dict.get("zh", ""))
    if kwargs and text:
        try:
            text = text.format(**kwargs)
        except KeyError:
            pass
    return text


def command_help(lang: str = "zh") -> str:
    """获取命令帮助"""
    lines = ["可用命令："]
    for cmd, desc in COMMAND_HELP.items():
        lines.append(f"  {cmd:<15} {desc.get(lang, desc.get('zh', ''))}")
    return "\n".join(lines)