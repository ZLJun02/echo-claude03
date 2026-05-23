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
            return False
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
        # 默认排除可执行脚本扩展名以提高安全性
        # 可执行脚本（.sh, .bat, .cmd 等）需要显式配置许可
        self.allowed_extensions = allowed_extensions or [
            # 源代码
            ".txt", ".py", ".pyx", ".pyi",
            ".js", ".jsx", ".ts", ".tsx",
            ".java", ".kt", ".scala", ".groovy",
            ".c", ".cpp", ".h", ".hpp", ".cc", ".cxx",
            ".cs", ".vb", ".fs",
            ".go", ".rs", ".dart", ".swift",
            ".php", ".rb", ".pl", ".lua", ".r", ".m",
            ".sql", ".graphql",
            # 标记/模板
            ".html", ".htm", ".xhtml",
            ".css", ".scss", ".sass", ".less", ".styl",
            ".md", ".rst", ".tex", ".adoc",
            # 数据/配置
            ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf",
            ".csv", ".tsv", ".xml",
            # 其他文本
            ".log", ".gitignore", ".dockerignore",
            ".env", ".properties",
            # 构建文件
            ".make", ".mk", ".cmake",
            ".gradle", ".maven", ".pom",
            ".razor", ".cshtml",
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
        # 文件浏览
        "ls", "grep", "find", "cat", "head", "tail", "wc",
        # Python
        "python", "python3", "pytest", "pytest3",
        # Git
        "git", "diff",
        # 系统信息
        "echo", "pwd", "cd", "stat", "which",
        # 文件操作（安全的）
        "mkdir", "rm", "cp", "mv",  # rmdir/chmod/chown/chgrp 是危险命令，从白名单移除
        # 压缩解压
        "tar", "gzip", "gunzip", "zip", "unzip",
        # 文本处理
        "awk", "sed", "sort", "uniq", "tr", "xargs",
        # JSON/YAML处理
        "jq", "yq",
    ]

    DANGEROUS_COMMANDS = [
        # 系统管理
        "sudo", "su", "passwd", "shutdown", "reboot", "halt", "poweroff",
        # 危险文件操作
        r"rm\s+-[rf]+", "rm\s+--", "rmdir", "dd", "mkfs", "format", "fdisk",
        # 权限修改
        "chmod", "chown", "chgrp",
        #  fork 炸弹
        ":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:",
        # 写入设备文件
        r">\s*/dev/", r">\s*CON", r">?\s*NUL",
        # 网络相关（限制性）
        "wget", "curl", "nc", "netcat", "telnet", "ssh", "scp", "rsync",
        # 进程操作
        "kill", "killall", "pkill", "taskkill",
        # 服务管理
        "systemctl", "service", "init", "rc.d",
        # 包管理（可能安装恶意软件）
        "apt-get", "yum", "dnf", "pip", "npm", "gem", "composer",
        # Windows 特定危险命令
        "del", "rd", "copy con", "format", "diskpart",
        # 编码/混淆
        "base64", "decode", "xxd", "hexdump",
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
        if not command or not command.strip():
            return False, "空命令"

        cmd_str = command.strip()

        # 1. 检查敏感路径访问 (防止访问系统关键文件)
        sensitive_paths = [
            "/etc/passwd", "/etc/shadow", "/etc/sudoers",
            "/etc/ssh", "/root/", "C:\\Windows\\System32",
            "~/.ssh", "~/.aws", "~/.gnupg",
            "/proc/", "/sys/", "/dev/", "/var/log/",
        ]
        for sp in sensitive_paths:
            if sp in cmd_str:
                return False, f"命令包含敏感路径访问: {sp}"

        # 2. 检查危险命令/模式 - 使用 DANGEROUS_COMMANDS 和白名单
        for pattern_str in self.DANGEROUS_COMMANDS:
            try:
                # 将 pattern_str 作为正则表达式
                if re.search(pattern_str, cmd_str, re.IGNORECASE):
                    # 提取模式用于错误消息（简化）
                    display = pattern_str[:40] + "..." if len(pattern_str) > 40 else pattern_str
                    return False, f"命令包含危险操作: {display}"
            except re.error:
                # 正则无效，退回到简单子串检查
                if pattern_str.lower() in cmd_str.lower():
                    return False, f"命令包含危险操作: {pattern_str}"

        # 3. 分割命令段（管道、分号、&、换行）
        try:
            segments = re.split(r'[|;&\n]', cmd_str)
        except re.error:
            segments = [cmd_str]

        for segment in segments:
            segment = segment.strip()
            if not segment:
                continue

            # 提取主命令，移除重定向目标和参数
            main_cmd_part = segment

            # 移除输出重定向 (> , >>, 2> 等) 之后的部分
            main_cmd_part = re.split(r'\s*>\s*', main_cmd_part, maxsplit=1)[0]
            main_cmd_part = re.split(r'\s*>>\s*', main_cmd_part, maxsplit=1)[0]
            main_cmd_part = re.split(r'\s*2>\s*', main_cmd_part, maxsplit=1)[0]
            main_cmd_part = re.split(r'\s*&>\s*', main_cmd_part, maxsplit=1)[0]

            # 移除输入重定向
            main_cmd_part = re.split(r'\s*<\s*', main_cmd_part, maxsplit=1)[0]

            # 提取命令名称
            try:
                parts = shlex.split(main_cmd_part)
            except ValueError:
                parts = main_cmd_part.split()

            if not parts:
                continue

            main_cmd = parts[0].lower()
            cmd_base = re.sub(r'^.*[/\\]', '', main_cmd)

            # 4. 检查是否在白名单
            if cmd_base not in self.allowed_commands and main_cmd not in self.allowed_commands:
                return False, f"命令 '{cmd_base}' 不在安全白名单内"

            # 5. 特定命令的额外检查
            if cmd_base in ["rm", "del"]:
                args = ' '.join(parts[1:]).lower()
                if any(flag in args for flag in ['-r', '-rf', '-fr', '--recursive', '--force', '/s', '/q']):
                    return False, f"{cmd_base} 命令使用了危险的递归/强制删除选项"

            if cmd_base == "chmod" and any(arg in parts[1:] for arg in ['+x', '+w', '+s', 'u+s', 'g+s']):
                return False, "chmod 修改权限不被允许"

            # 6. 检查子shell、命令替换、后台执行
            if any(c in segment for c in ['(', ')', '`', '$(']):
                return False, "命令包含子shell或命令替换，不被允许"

            if segment.strip().endswith('&'):
                return False, "后台执行不被允许"

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
        """Initialize tool registry based on configuration"""
        if cls._initialized:
            return

        # 设置默认值
        safe_dirs = ["./", "./tmp"]
        allowed_commands = ShellTool.ALLOWED_COMMANDS
        enabled_tools = ["file_read", "file_write", "shell"]

        # 从配置中获取值（如果存在且有效）
        if config is not None and hasattr(config, 'tool') and config.tool is not None:
            tool_cfg = config.tool
            safe_dirs = getattr(tool_cfg, 'safe_dirs', safe_dirs)
            allowed_commands = getattr(tool_cfg, 'allowed_commands', allowed_commands)
            if hasattr(tool_cfg, 'enabled') and tool_cfg.enabled:
                enabled_tools = tool_cfg.enabled

        if "file_read" in enabled_tools:
            cls.register(FileReadTool(safe_dirs=safe_dirs))

        if "file_write" in enabled_tools:
            cls.register(FileWriteTool(safe_dirs=safe_dirs))

        if "shell" in enabled_tools:
            cls.register(ShellTool(
                allowed_commands=allowed_commands,
                working_dir=str(Path.cwd())
            ))

        cls._initialized = True


# 全局注册表实例
tool_registry = ToolRegistry()