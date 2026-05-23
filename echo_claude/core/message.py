"""
核心消息模型
统一用于会话存储和API传输
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ToolFunction(BaseModel):
    """工具函数定义"""
    name: str
    arguments: str  # JSON 字符串

    def get_arguments(self) -> Dict[str, Any]:
        """解析参数为字典"""
        import json
        try:
            return json.loads(self.arguments) if self.arguments else {}
        except json.JSONDecodeError:
            return {"raw": self.arguments}


class ToolCall(BaseModel):
    """工具调用"""
    id: str
    function: ToolFunction

    def to_dict(self) -> Dict[str, Any]:
        """转换为API字典格式"""
        return {
            "id": self.id,
            "type": "function",
            "function": {
                "name": self.function.name,
                "arguments": self.function.arguments,
            }
        }


class Message(BaseModel):
    """统一消息类"""
    role: str
    content: str
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    metadata: Dict = Field(default_factory=dict)
    tool_calls: List[ToolCall] = Field(default_factory=list)
    tool_call_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为API字典格式（供Provider调用）"""
        data = {"role": self.role, "content": self.content}
        if self.tool_calls:
            data["tool_calls"] = [tc.to_dict() for tc in self.tool_calls]
        if self.tool_call_id:
            data["tool_call_id"] = self.tool_call_id
        return data


class Usage(BaseModel):
    """Token使用情况"""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ChatResponse(BaseModel):
    """聊天响应"""
    content: str
    tool_calls: List[ToolCall] = Field(default_factory=list)
    usage: Usage = Field(default_factory=Usage)


class StreamChunk(BaseModel):
    """流式块"""
    content: str = ""
    tool_calls: List[ToolCall] = Field(default_factory=list)
    finish_reason: Optional[str] = None
