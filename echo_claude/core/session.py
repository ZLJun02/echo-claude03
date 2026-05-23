"""
会话管理系统
支持会话的创建、保存、加载、持久化
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from pydantic import BaseModel, Field
from rich.console import Console

# 使用统一的消息模型（从core.message导入）
from echo_claude.core.message import Message


class Session(BaseModel):
    """会话"""
    name: str
    messages: List[Message] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    metadata: Dict = Field(default_factory=dict)

    def add_message(self, role: str, content: str, **kwargs) -> None:
        """添加消息"""
        msg = Message(role=role, content=content, metadata=kwargs)
        self.messages.append(msg)
        self.updated_at = datetime.now().isoformat()

    def get_history(self, limit: int = None) -> List[Dict]:
        """获取历史消息"""
        messages = self.messages[-limit:] if limit else self.messages
        return [{"role": m.role, "content": m.content} for m in messages]

    def clear(self) -> None:
        """清空会话"""
        self.messages.clear()
        self.updated_at = datetime.now().isoformat()

    def to_dict(self) -> Dict:
        """转换为字典"""
        return self.model_dump()

    @classmethod
    def from_dict(cls, data: Dict) -> "Session":
        """从字典创建会话"""
        return cls(**data)


class SessionManager:
    """会话管理器"""

    def __init__(self, save_path: Path):
        self.save_path = save_path.expanduser()
        self.save_path.mkdir(parents=True, exist_ok=True)
        self.current_session: Optional[Session] = None
        self._sessions_cache: Optional[List[Session]] = None

    def create_session(self, name: str = None) -> Session:
        """创建新会话"""
        if not name:
            name = datetime.now().strftime("session_%Y%m%d_%H%M%S")
        session = Session(name=name)
        self.current_session = session
        return session

    def save_current_session(self, name: str = None) -> bool:
        """保存当前会话"""
        if not self.current_session:
            console = Console()
            console.print("[yellow]没有当前会话可保存[/yellow]")
            return False

        if name:
            self.current_session.name = name

        filepath = self.save_path / f"{self.current_session.name}.json"
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.current_session.model_dump(), f, ensure_ascii=False, indent=2)

        self._sessions_cache = None
        return True

    def load_session(self, name: str) -> Optional[Session]:
        """加载会话"""
        filepath = self.save_path / f"{name}.json"
        if not filepath.exists():
            return None

        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)

        session = Session.from_dict(data)
        self.current_session = session
        return session

    def delete_session(self, name: str) -> bool:
        """删除会话"""
        filepath = self.save_path / f"{name}.json"
        if filepath.exists():
            filepath.unlink()
            self._sessions_cache = None
            return True
        return False

    def list_sessions(self) -> List[Session]:
        """列出所有会话"""
        if self._sessions_cache is not None:
            return self._sessions_cache

        sessions = []
        for filepath in self.save_path.glob("*.json"):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    session = Session.from_dict(data)
                    sessions.append(session)
            except Exception:
                continue

        # 按更新时间排序
        sessions.sort(key=lambda s: s.updated_at, reverse=True)
        self._sessions_cache = sessions
        return sessions

    def get_or_create(self, name: str = None) -> Session:
        """获取或创建会话"""
        if self.current_session is None:
            self.create_session(name)
        return self.current_session