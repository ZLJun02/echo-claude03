# providers/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Iterator
import json


@dataclass
class ToolFunction:
    """工具函数定义"""
    name: str
    arguments: str  # JSON 字符串

    def get_arguments(self) -> Dict[str, Any]:
        """解析参数为字典"""
        try:
            return json.loads(self.arguments) if self.arguments else {}
        except json.JSONDecodeError:
            return {"raw": self.arguments}


@dataclass
class ToolCall:
    """工具调用"""
    id: str
    function: ToolFunction


@dataclass
class Message:
    """聊天消息"""
    role: str
    content: str
    tool_calls: List[ToolCall] = field(default_factory=list)
    tool_call_id: Optional[str] = None  # 用于 tool 角色的消息

    def to_dict(self) -> Dict[str, Any]:
        """转换为 API 字典格式"""
        data: Dict[str, Any] = {"role": self.role, "content": self.content}
        if self.tool_calls:
            data["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments
                    }
                }
                for tc in self.tool_calls
            ]
        if self.tool_call_id:
            data["tool_call_id"] = self.tool_call_id
        return data


@dataclass
class Usage:
    """Token 使用情况"""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass
class ChatResponse:
    """聊天响应"""
    content: str
    tool_calls: List[ToolCall] = field(default_factory=list)
    usage: Usage = field(default_factory=Usage)


@dataclass
class StreamChunk:
    """流式块"""
    content: str = ""
    tool_calls: List[ToolCall] = field(default_factory=list)
    finish_reason: Optional[str] = None


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