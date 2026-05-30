"""
配置管理系统
支持 YAML 配置文件、环境变量、默认值
对中文友好，提供清晰的错误提示
"""

from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
import yaml
import os
import sys
import sys

# 尝试加载 .env 文件
try:
    from dotenv import load_dotenv
    _env_file = Path.home() / ".echo-claude" / ".env"
    if _env_file.exists():
        load_dotenv(_env_file)
    # 也加载工作目录的 .env
    _local_env = Path.cwd() / ".env"
    if _local_env.exists():
        load_dotenv(_local_env, override=False)
except ImportError:
    pass


def deep_update(base: Dict, updates: Dict) -> Dict:
    """深度合并两个字典，更新嵌套结构"""
    result = base.copy()
    for key, value in updates.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_update(result[key], value)
        else:
            result[key] = value
    return result




class ProviderConfig(BaseSettings):
    """模型提供者配置"""
    name: str
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    models: List[str] = []
    timeout: int = 30
    max_retries: int = 3

    model_config = SettingsConfigDict(extra="allow")






def _get_default_allowed_commands() -> List[str]:
    """根据操作系统返回合适的默认允许命令列表"""
    if sys.platform == "win32":
        # Windows 常用命令
        return [
            "dir", "type", "findstr", "echo", "copy", "move", "mkdir",
            "python", "python3", "py", "pytest", "pytest3",
            "git", "diff", "where", "path"
        ]
    else:
        # Unix/Linux 常用命令
        return [
            "ls", "grep", "find", "cat", "head", "tail", "wc",
            "python", "python3", "pytest", "pytest3",
            "git", "diff"
        ]

class ToolConfig(BaseSettings):
    """工具配置"""
    enabled: List[str] = ["file_read", "file_write", "shell"]
    safe_dirs: List[str] = ["./", "./tmp", ".."]
    allowed_commands: List[str] = Field(default_factory=_get_default_allowed_commands)
    max_shell_timeout: int = 30
    allow_shell: bool = True
    allow_file_write: bool = True

    @field_validator("safe_dirs")
    @classmethod
    def normalize_safe_dirs(cls, v: List[str]) -> List[str]:
        """规范化安全目录路径"""
        result = []
        for d in v:
            if d.startswith("~"):
                d = str(Path(d).expanduser())
            result.append(str(Path(d).resolve()))
        return result


class SessionConfig(BaseSettings):
    """会话配置"""
    auto_save: bool = True
    history_limit: int = 1000
    save_path: str = "~/.echo-claude/sessions"
    backup_count: int = 10
    default_session: Optional[str] = None


class LoggingConfig(BaseSettings):
    """日志配置"""
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file: Optional[str] = None


class DisplayConfig(BaseSettings):
    """显示配置"""
    theme: str = "default"
    show_tokens: bool = True
    show_tool_calls: bool = True
    syntax_highlighting: bool = True
    paging: bool = False


class AppConfig(BaseSettings):
    """主配置类"""
    # 默认配置
    default_provider: str = "openai"
    default_model: Optional[str] = None
    language: str = "zh-CN"

    # 子配置
    providers: Dict[str, ProviderConfig] = {}
    tool: ToolConfig = ToolConfig()
    session: SessionConfig = SessionConfig()
    logging: LoggingConfig = LoggingConfig()
    display: DisplayConfig = DisplayConfig()

    model_config = SettingsConfigDict(
        env_prefix="ECHO_CLAUDE_",
        extra="allow"
    )

    @classmethod
    def load_from_yaml(cls, config_path: Path) -> "AppConfig":
        """从 YAML 文件加载配置"""
        if not config_path.exists():
            return cls()

        with open(config_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f) or {}

        # 处理 ~ 路径
        if "session" in data and "save_path" in data["session"]:
            sp = data["session"]["save_path"]
            if sp.startswith("~"):
                data["session"]["save_path"] = str(Path(sp).expanduser())

        # 确保每个提供者配置包含 name 字段（将字典键作为 name）
        if "providers" in data and isinstance(data["providers"], dict):
            providers = {}
            for name, config_dict in data["providers"].items():
                if isinstance(config_dict, dict):
                    # 复制并添加 name 字段
                    config_dict = dict(config_dict)
                    config_dict["name"] = name
                    providers[name] = config_dict
                else:
                    providers[name] = config_dict
            data["providers"] = providers

        return cls(**data)

    def save_to_yaml(self, config_path: Path) -> None:
        """保存配置到 YAML 文件"""
        config_path.parent.mkdir(parents=True, exist_ok=True)

        data = self.model_dump(exclude_none=True)
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(data, f, allow_unicode=True, sort_keys=False, default_flow_style=False)

    def get_provider(self, name: str) -> Optional[ProviderConfig]:
        """获取指定提供者配置"""
        return self.providers.get(name)

    def get_active_provider(self) -> Optional[ProviderConfig]:
        """获取当前激活的提供者"""
        return self.get_provider(self.default_provider)


# 全局配置实例
_config: Optional[AppConfig] = None


def get_config() -> AppConfig:
    """获取全局配置实例（单例）"""
    global _config
    if _config is None:
        _config = load_config()
    return _config


def load_config(config_path: Optional[Path] = None) -> AppConfig:
    """加载配置"""
    if config_path is None:
        # 默认配置路径：~/.echo-claude/config.yaml
        config_dir = Path.home() / ".echo-claude"
        config_path = config_dir / "config.yaml"

    # 从文件加载
    config = AppConfig.load_from_yaml(config_path)

    # 环境变量覆盖（深度合并）
    env_overrides = get_env_overrides()
    merged_data = deep_update(config.model_dump(), env_overrides)
    config = AppConfig(**merged_data)

    return config


def get_env_overrides() -> Dict[str, Any]:
    """从环境变量获取覆盖配置"""
    overrides: Dict[str, Any] = {}

    # API Key 环境变量
    provider_keys = {
        "OPENAI_API_KEY": ("providers", "openai", "api_key"),
        "ANTHROPIC_API_KEY": ("providers", "anthropic", "api_key"),
        "DEEPSEEK_API_KEY": ("providers", "deepseek", "api_key"),
        "BAIDU_API_KEY": ("providers", "baidu", "api_key"),
        "ZHIPU_API_KEY": ("providers", "zhipu", "api_key"),
        "MOONSHOT_API_KEY": ("providers", "moonshot", "api_key"),
        "ECHO_CLAUDE_DEFAULT_PROVIDER": ("default_provider",),
    }

    for env_var, path in provider_keys.items():
        value = os.getenv(env_var)
        if not value:
            continue
        if len(path) == 3:
            # 嵌套 providers 结构
            providers_key, provider_name, field = path
            if providers_key not in overrides:
                overrides[providers_key] = {}
            if provider_name not in overrides[providers_key]:
                overrides[providers_key][provider_name] = {"name": provider_name}
            overrides[providers_key][provider_name][field] = value
        elif len(path) == 1:
            # 顶层配置
            overrides[path[0]] = value

    return overrides


def init_config(config_path: Path) -> AppConfig:
    """初始化配置文件（交互式或模板）"""
    config_dir = config_path.parent
    config_dir.mkdir(parents=True, exist_ok=True)

    # 创建默认配置
    default_config = AppConfig(
        default_provider="openai",
        providers={
            "openai": ProviderConfig(
                name="openai",
                api_key=os.getenv("OPENAI_API_KEY", ""),
                base_url="https://api.openai.com/v1",
                models=["gpt-4", "gpt-4-turbo", "gpt-3.5-turbo"]
            ),
            "anthropic": ProviderConfig(
                name="anthropic",
                api_key=os.getenv("ANTHROPIC_API_KEY", ""),
                models=["claude-3-opus", "claude-3-sonnet"]
            ),
            "deepseek": ProviderConfig(
                name="deepseek",
                api_key=os.getenv("DEEPSEEK_API_KEY", ""),
                base_url="https://api.deepseek.com/v1",
                models=["deepseek-chat", "deepseek-coder"]
            ),
            "local": ProviderConfig(
                name="local",
                base_url="http://localhost:11434",
                models=["llama2", "codellama", "mistral"]
            ),
        },
        session=SessionConfig(
            save_path=str(config_dir / "sessions")
        )
    )

    # 检查现有配置
    if config_path.exists():
        return AppConfig.load_from_yaml(config_path)

    default_config.save_to_yaml(config_path)
    return default_config