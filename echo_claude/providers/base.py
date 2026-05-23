# providers/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Iterator
import json

# 使用统一的消息模型（定义在 echo_claude.core.message）
from ..core.message import (
    ToolFunction,
    ToolCall,
    Message,
    Usage,
    ChatResponse,
    StreamChunk,
)



class BaseProvider(ABC):
    """提供者基类"""

    def __init__(
        self,
        name: str = None,
        api_key: str = None,
        base_url: str = None,
        models: List[str] = None,
        timeout: int = 30,
        max_retries: int = 3,
        **kwargs
    ):
        self.name = name
        self.api_key = api_key
        self.base_url = base_url.rstrip('/') if base_url else None
        self.models = models or []
        self.timeout = timeout
        self.max_retries = max_retries

    @abstractmethod
    def chat(self, messages: List[Message], model: str, **kwargs) -> ChatResponse:
        """非流式对话"""
        pass

    @abstractmethod
    def stream_chat(self, messages: List[Message], model: str, **kwargs) -> Iterator[StreamChunk]:
        """流式对话"""
        pass

    def validate_model(self, model: str) -> bool:
        """验证模型是否支持"""
        if not self.models:
            return True
        return model in self.models