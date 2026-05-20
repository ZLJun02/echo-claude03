"""
工具调用系统 - 最高优先级
提供文件操作、Shell命令等工具
包含严格的安全沙箱机制
"""

import os
import re
import subprocess
import shlex
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator
from abc import ABC, abstractmethod
import json


class ToolResult(BaseModel):
    """工具执行结果"""
    success: bool
    output: str = ""
    error: str = ""
    metadata: Dict = Field(default_factory=dict)


class ToolParameter(BaseModel):
    """工具参数定义"""
    name: str
    type: str
    description: str
    required: bool = True


class ToolDefinition(BaseModel):
    """工具定义（用于模型调用）"""
    name: str
    description: str
    parameters: List[ToolParameter] = []


class BaseTool(ABC):
    """工具抽象基类"""

    name: str = ""
    description: str = ""
    parameters: List[ToolParameter] = []

    @abstractmethod
    def execute(self, **kwargs) -> ToolResult:
        """执行工具"""
        pass

    def get_definition(self) -> ToolDefinition:
        """获取工具定义（用于模型调用）"""
        return ToolDefinition(
            name=self.name,
            description=self.description,
            parameters=self.parameters
        )


class FileReadTool(BaseTool):
    """文件读取工具"""
    name = "file_read"
    description = "读取文件内容，支持指定行范围"

    parameters = [
        ToolParameter(
            name="path",
            type="string",
            description="文件路径（相对或绝对路径）",
            required=True
        ),
        ToolParameter(
            name="start_line",
            type="integer",
            description="起始行号（从1开始，可选）",
            required=False
        ),
        ToolParameter(
            name="end_line",
            type="integer",
            description="结束行号（可选）",
            required=False
        ),
    ]

    def __init__(self, safe_dirs: List[str] = None):
        self.safe_dirs = [Path(d).resolve() for d in (safe_dirs or ["./", "./tmp"])]

    def _check_path_safe(self, path: Path) -> bool:
        """检查路径是否在安全目录内"""
        try:
            resolved = path.resolve()
            for safe_dir in self.safe_dirs:
                if resolved.is_relative_to(safe_dir):
                    return True
            if ".." in str(path) or path.is_absolute():
                return False
            return True
        except (ValueError, OSError):
            return False

    def execute(
        self,
        path: str,
        start_line: int = None,
        end_line: int = None
    ) -> ToolResult:
        """执行文件读取"""
        try:
            filepath = Path(path)
            if not self._check_path_safe(filepath):
                return ToolResult(
                    success=False,
                    error=f"路径 '{path}' 不在安全目录内"
                )

            if not filepath.exists():
                return ToolResult(
                    success=False,
                    error=f"文件不存在: {path}"
                )

            if not filepath.is_file():
                return ToolResult(
                    success=False,
                    error=f"路径不是文件: {path}"
                )

            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()

            if start_line is not None:
                start_idx = max(0, start_line - 1)
                lines = lines[start_idx:]
            if end_line is not None:
                end_idx = end_line - start_line if start_line else end_line
                lines = lines[:end_idx]

            content = ''.join(lines)

            if len(content) > 10240:
                content = content[:10240] + "\n... (文件过长，已截断)"

            return ToolResult(
                success=True,
                output=content,
                metadata={
                    "path": str(filepath),
                    "line_count": len(lines),
                    "size": filepath.stat().st_size,
                }
            )

        except UnicodeDecodeError:
            return ToolResult(
                success=False,
                error="文件编码错误：无法以UTF-8读取"
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"读取失败: {str(e)}"
            )


class FileWriteTool(BaseTool):
    """文件写入工具"""
    name = "file_write"
    description = "写入文件内容（慎用）"

    parameters = [
        ToolParameter(
            name="path",
            type="string",
            description="文件路径",
            required=True
        ),
        ToolParameter(
            name="content",
            type="string",
            description="要写入的内容",
            required=True
        ),
        ToolParameter(
            name="append",
            type="boolean",
            description="是否追加（默认覆盖）",
            required=False
        ),
    ]

    def __init__(self, safe_dirs: List[str] = None, allowed_extensions: List[str] = None):
        self.safe_dirs = [Path(d).resolve() for d in (safe_dirs or ["./", "./tmp"])]
        self.allowed_extensions = allowed_extensions or [
            ".txt", ".py", ".js", ".ts", ".html", ".css",
            ".json", ".yaml", ".yml", ".md", ".sh", ".bat"
        ]

    def _check_path_safe(self, path: Path) -> bool:
        """检查路径安全"""
        try:
            resolved = path.resolve()
            for safe_dir in self.safe_dirs:
                if resolved.is_relative_to(safe_dir):
                    break
            else:
                return False

            if self.allowed_extensions and path.suffix not in self.allowed_extensions:
                return False

            sensitive_patterns = ["passwd", "shadow", ".key", ".pem", " credential"]
            if any(p in str(path) for p in sensitive_patterns):
                return False

            return True
        except (ValueError, OSError):
            return False

    def execute(
        self,
        path: str,
        content: str,
        append: bool = False
    ) -> ToolResult:
        """执行文件写入"""
        try:
            filepath = Path(path)

            if not self._check_path_safe(filepath):
                return ToolResult(
                    success=False,
                    error=f"路径 '{path}' 不在安全目录内或扩展名不被允许"
                )

            filepath.parent.mkdir(parents=True, exist_ok=True)

            mode = 'a' if append else 'w'
            with open(filepath, mode, encoding='utf-8') as f:
                f.write(content)

            return ToolResult(
                success=True,
                output=f"已{'追加' if append else '写入'} {len(content)} 字符到 {path}",
                metadata={
                    "path": str(filepath),
                    "size": len(content),
                    "appended": append,
                }
            )

        except Exception as e:
            return ToolResult(
                success=False,
                error=f"写入失败: {str(e)}"
            )


class ShellTool(BaseTool):
    """Shell命令执行工具"""
    name = "shell"
    description = "在安全沙箱内执行Shell命令"

    parameters = [
        ToolParameter(
            name="command",
            type="string",
            description="要执行的命令",
            required=True
        ),
        ToolParameter(
            name="timeout",
            type="integer",
            description="超时时间（秒，默认30）",
            required=False
        ),
    ]

    ALLOWED_COMMANDS = [
        "ls", "grep", "find", "cat", "head", "tail", "wc",
        "python", "python3", "pytest", "pytest3",
        "git", "diff", "echo", "pwd", "cd",
        "mkdir", "rmdir", "rm", "cp", "mv",
        "chmod", "chown", "stat", "which",
        "tar", "gzip", "gunzip", "zip", "unzip",
        "awk", "sed", "sort", "uniq", "tr",
        "xargs", "pipe", "jq", "yq",
    ]

    DANGEROUS_COMMANDS = [
        "sudo", "su", "passwd", "shutdown", "reboot",
        "rm -rf", "dd", ":(){ :|:& };:", "mkfs",
        "del", "format", "fdisk", "> /dev/",
    ]

    def __init__(
        self,
        allowed_commands: List[str] = None,
        max_timeout: int = 30,
        working_dir: str = None,
    ):
        self.allowed_commands = allowed_commands or self.ALLOWED_COMMANDS
        self.max_timeout = min(max_timeout, 120)
        self.working_dir = Path(working_dir).resolve() if working_dir else Path.cwd()

    def _check_command_safe(self, command: str) -> tuple[bool, str]:
        """检查命令是否安全"""
        cmd_lower = command.lower().strip()

        if not cmd_lower:
            return False, "空命令"

        # 1. 危险模式检测（大小写不敏感，含空格变体）
        dangerous_patterns = [
            (r"\bsudo\b", "sudo"),
            (r"\bsu\b", "su"),
            (r"\bpasswd\b", "passwd"),
            (r"\bshutdown\b", "shutdown"),
            (r"\breboot\b", "reboot"),
            (r"\brm\s+-rf\b", "rm -rf"),
            (r"\bdd\b", "dd"),
            (r"\bmkfs\b", "mkfs"),
            (r"\bformat\b", "format"),
            (r"\bfdisk\b", "fdisk"),
            (r">\s*/dev/", "写入块设备"),
            (r"\bdel\b", "del"),
            (r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:", "fork 炸弹"),
        ]
        for pattern, name in dangerous_patterns:
            if re.search(pattern, cmd_lower):
                return False, f"命令包含危险操作: {name}"

        # 2. 管道和重定向中所有命令都要检查
        try:
            # 分割管道
            segments = re.split(r'[|;&]', command)
            for segment in segments:
                segment = segment.strip()
                if not segment:
                    continue
                parts = shlex.split(segment)
                if not parts:
                    continue
                main_cmd = parts[0].lower()
                # 允许路径形式的命令
                cmd_base = main_cmd.split('/')[-1].split('\\')[-1]
                if cmd_base not in self.allowed_commands and main_cmd not in self.allowed_commands:
                    return False, f"命令 '{cmd_base}' 不在白名单内"

        except ValueError as e:
            return False, f"命令解析失败: {str(e)}"

        return True, ""

    def execute(
        self,
        command: str,
        timeout: int = None
    ) -> ToolResult:
        """执行Shell命令"""
        try:
            is_safe, reason = self._check_command_safe(command)
            if not is_safe:
                return ToolResult(
                    success=False,
                    error=f"安全检查失败: {reason}"
                )

            timeout = min(timeout or 30, self.max_timeout)

            result = subprocess.run(
                command,
                shell=True,
                cwd=self.working_dir,
                capture_output=True,
                text=True,
                timeout=timeout,
            )

            output = result.stdout
            if result.stderr:
                output += f"\n[stderr]\n{result.stderr}"

            if len(output) > 51200:
                output = output[:51200] + "\n... (输出过长，已截断)"

            return ToolResult(
                success=result.returncode == 0,
                output=output or "(无输出)",
                error=f"退出码: {result.returncode}" if result.returncode != 0 else "",
                metadata={
                    "command": command,
                    "return_code": result.returncode,
                    "execution_time": timeout,
                }
            )

        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False,
                error=f"命令执行超时 ({timeout}秒)"
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"执行失败: {str(e)}"
            )


class ToolRegistry:
    """工具注册和管理器"""

    _tools: Dict[str, BaseTool] = {}
    _initialized: bool = False

    @classmethod
    def register(cls, tool: BaseTool) -> None:
        """注册工具"""
        cls._tools[tool.name] = tool

    @classmethod
    def get_tool(cls, name: str) -> Optional[BaseTool]:
        """获取工具实例"""
        return cls._tools.get(name)

    @classmethod
    def list_tools(cls) -> Dict[str, Dict]:
        """列出所有工具"""
        return {
            name: {
                "name": tool.name,
                "description": tool.description,
                "parameters": [p.model_dump() for p in tool.parameters],
                "enabled": True,
            }
            for name, tool in cls._tools.items()
        }

    @classmethod
    def execute(cls, tool_name: str, arguments: Dict) -> Any:
        """执行工具"""
        tool = cls.get_tool(tool_name)
        if not tool:
            raise ValueError(f"工具不存在: {tool_name}")

        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except json.JSONDecodeError:
                arguments = {"args": arguments}

        result = tool.execute(**arguments)
        return result.output if result.success else f"错误: {result.error}"

    @classmethod
    def get_definitions(cls) -> List[ToolDefinition]:
        """获取所有工具定义（用于模型调用）"""
        return [tool.get_definition() for tool in cls._tools.values()]

    @classmethod
    def initialize(cls, config) -> None:
        """初始化工具注册表（根据配置）"""
        if cls._initialized:
            return

        from ..config.settings import AppConfig

        if isinstance(config, AppConfig):
            cfg = config
        else:
            cfg = config if hasattr(config, 'tool') else None

        if cfg and hasattr(cfg, 'tool'):
            tool_cfg = cfg.tool
            safe_dirs = tool_cfg.safe_dirs
            allowed_commands = tool_cfg.allowed_commands
        else:
            safe_dirs = ["./", "./tmp"]
            allowed_commands = ShellTool.ALLOWED_COMMANDS

        if "file_read" in (tool_cfg.enabled if cfg and hasattr(cfg, 'tool') else ["file_read"]):
            cls.register(FileReadTool(safe_dirs=safe_dirs))

        if "file_write" in (tool_cfg.enabled if cfg and hasattr(cfg, 'tool') else ["file_write"]):
            cls.register(FileWriteTool(safe_dirs=safe_dirs))

        if "shell" in (tool_cfg.enabled if cfg and hasattr(cfg, 'tool') else ["shell"]):
            cls.register(ShellTool(
                allowed_commands=allowed_commands,
                working_dir=str(Path.cwd())
            ))

        cls._initialized = True


# 全局注册表实例
tool_registry = ToolRegistry()