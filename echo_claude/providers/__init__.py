"""
模型提供者模块
提供统一的AI模型接口
"""

from .base import BaseProvider, Message as ProviderMessage, ToolCall, ToolFunction
from .openai import OpenAIProvider, ProviderError, AuthenticationError, RateLimitError
from .anthropic import AnthropicProvider
from .deepseek import DeepSeekProvider
from .baidu import BaiduProvider
from .zhipu import ZhipuProvider
from .moonshot import MoonshotProvider
from .local import LocalProvider

# 提供者映射
_PROVIDER_MAP = {
    "openai": OpenAIProvider,
    "anthropic": AnthropicProvider,
    "deepseek": DeepSeekProvider,
    "baidu": BaiduProvider,
    "zhipu": ZhipuProvider,
    "moonshot": MoonshotProvider,
    "local": LocalProvider,
    "localai": LocalProvider,  # 别名
    "lmstudio": LocalProvider,  # 别名
    "ollama": LocalProvider,  # 别名
    "nvidia": OpenAIProvider,  # NVIDIA NIM (OpenAI 兼容)
}

def get_provider_class(name: str) -> type[BaseProvider]:
    """根据名称获取提供者类"""
    return _PROVIDER_MAP.get(name)

def list_providers() -> list[str]:
    """列出所有支持的提供者"""
    return list(_PROVIDER_MAP.keys())

__all__ = [
    "BaseProvider", "Message", "ToolCall", "ToolFunction",
    "OpenAIProvider", "AnthropicProvider", "DeepSeekProvider",
    "BaiduProvider", "ZhipuProvider", "MoonshotProvider", "LocalProvider",
    "ProviderError", "AuthenticationError", "RateLimitError",
    "get_provider_class", "list_providers",
]