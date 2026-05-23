# -*- coding: utf-8 -*-
"""
AI Agent 核心模块
整合 Provider、工具调用、会话管理
"""

from typing import Any, Dict, List, Optional, Union, Iterator

from .session import Session
from ..providers.base import BaseProvider, Message as ProviderMessage, ToolCall
from ..config.settings import AppConfig
from .tools import ToolRegistry
from ..utils.logger import get_logger


class Agent:
    """AI Agent 核心类"""

    def __init__(
        self,
        provider: BaseProvider,
        model: str,
        session: Optional[Session] = None,
        config: Optional[AppConfig] = None,
        system_prompt: str = None,
    ):
        self.provider = provider
        self.model = model
        self.session = session
        self.config = config
        self.system_prompt = system_prompt or self._get_default_system_prompt()
        self.logger = get_logger("echo_claude.agent")
        self._total_tokens = {"prompt": 0, "completion": 0}

        # 初始化工具注册表
        if config:
            ToolRegistry.initialize(config)

    def _get_default_system_prompt(self) -> str:
        """获取默认系统提示词（中文友好）"""
        return """你是一个智能编程助手，名为 Echo Claude。

你的能力：
1. 理解和生成代码
2. 分析和解释代码
3. 调试问题并提供修复方案
4. 搜索和读取文件
5. 执行系统命令（安全沙箱内）

原则：
- 优先使用工具获取信息，而非猜测
- 生成的代码要简洁、高效、安全
- 对中国用户友好，支持中文交流
- 遵守安全规范，不执行危险操作

请用中文回复，除非用户特别要求英文。"""

    def chat(
        self,
        user_input: str,
        stream: bool = True,
        max_iterations: int = 5,
    ) -> Union[str, Iterator[str]]:
        """
        对话主入口

        Args:
            user_input: 用户输入
            stream: 是否流式输出
            max_iterations: 最大工具调用迭代次数

        Returns:
            响应文本或流式迭代器
        """
        if self.session:
            self.session.add_message("user", user_input)

        messages = self._build_messages()

        if stream:
            return self._stream_conversation(messages, max_iterations)
        else:
            final_content = self._run_conversation(messages, max_iterations)
            if self.session:
                self.session.add_message("assistant", final_content)
            return final_content

    def _build_messages(self) -> List[ProviderMessage]:
        """构建发送给Provider的消息列表"""
        messages: List[ProviderMessage] = []

        # 系统提示
        if self.system_prompt:
            messages.append(ProviderMessage(
                role="system",
                content=self.system_prompt
            ))

        # 会话历史（限制数量避免token溢出）
        if self.session:
            max_history = self.config.session.history_limit if self.config else 50
            for msg in self.session.get_history(limit=max_history):
                messages.append(ProviderMessage(
                    role=msg["role"],
                    content=msg["content"]
                ))

        return messages

    def _run_conversation(self, messages: List[ProviderMessage], max_iterations: int) -> str:
        """运行对话循环，处理工具调用（非流式）"""
        current_messages = messages.copy()

        for iteration in range(max_iterations):
            response = self.provider.chat(current_messages, self.model)

            # 记录 token 使用
            if response.usage:
                self._total_tokens["prompt"] += response.usage.prompt_tokens
                self._total_tokens["completion"] += response.usage.completion_tokens

            if response.tool_calls:
                current_messages.append(ProviderMessage(
                    role="assistant",
                    content=response.content or "",
                    tool_calls=response.tool_calls
                ))

                tool_results = self._execute_tool_calls(response.tool_calls)
                for result in tool_results:
                    current_messages.append(ProviderMessage(
                        role="tool",
                        content=result["content"],
                        tool_call_id=result["call_id"]
                    ))
                continue
            else:
                return response.content or ""

        raise RuntimeError(f"工具调用超过最大迭代次数 {max_iterations}")

    def _stream_conversation(
        self, messages: List[ProviderMessage], max_iterations: int
    ) -> Iterator[str]:
        """流式对话（支持工具调用）"""
        current_messages = messages.copy()
        accumulated = ""

        for iteration in range(max_iterations):
            # 使用流式 API
            buffered_tool_calls: Dict[int, Dict] = {}
            content = ""

            for chunk in self.provider.stream_chat(current_messages, self.model):
                if chunk.content:
                    content += chunk.content
                    yield chunk.content
                    accumulated += chunk.content

                # 收集流式工具调用
                if chunk.tool_calls:
                    for tc in chunk.tool_calls:
                        idx = tc.id or "0"
                        if idx not in buffered_tool_calls:
                            buffered_tool_calls[idx] = {
                                "id": tc.id or f"call_{idx}",
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            }
                        else:
                            buffered_tool_calls[idx]["arguments"] += tc.function.arguments

                if chunk.finish_reason == "stop":
                    break

            # 检查是否有工具调用需要执行
            if buffered_tool_calls:
                tool_calls = [
                    ToolCall(
                        id=v["id"],
                        function=type("ToolFunction", (), {
                            "name": v["name"],
                            "arguments": v["arguments"],
                            "get_arguments": lambda s=v["arguments"]: (
                                __import__("json").loads(s) if s else {}
                            ),
                        })(),
                    )
                    for v in buffered_tool_calls.values()
                ]

                current_messages.append(ProviderMessage(
                    role="assistant",
                    content=content or accumulated,
                    tool_calls=tool_calls,
                ))

                for tc in tool_calls:
                    try:
                        result = ToolRegistry.execute(
                            tc.function.name, tc.function.arguments
                        )
                        current_messages.append(ProviderMessage(
                            role="tool",
                            content=str(result),
                            tool_call_id=tc.id,
                        ))
                    except Exception as e:
                        current_messages.append(ProviderMessage(
                            role="tool",
                            content=f"工具执行错误: {e}",
                            tool_call_id=tc.id,
                        ))
                # 银行改：继续下一轮迭代，accumulated保留当前轮的内容
                continue
            else:
                # 无工具调用，对话结束
                if self.session and accumulated:
                    self.session.add_message("assistant", accumulated)
                break

        # 循环结束后，如果有session且仍有未保存的内容，保存它
        # （通常是因为达到max_iterations限制）
        if self.session and accumulated and not buffered_tool_calls:
            self.session.add_message("assistant", accumulated)

    def _execute_tool_calls(self, tool_calls: List[ToolCall]) -> List[Dict]:
        """执行工具调用"""
        results = []
        for tool_call in tool_calls:
            try:
                result = ToolRegistry.execute(tool_call.function.name, tool_call.function.arguments)
                results.append({
                    "call_id": tool_call.id,
                    "content": str(result)
                })
            except Exception as e:
                self.logger.error("工具执行失败: %s - %s", tool_call.function.name, e)
                results.append({
                    "call_id": tool_call.id,
                    "content": f"工具执行错误: {str(e)}"
                })
        return results

    def reset(self) -> None:
        """重置会话（清空历史）"""
        if self.session:
            self.session.clear()
        self._total_tokens = {"prompt": 0, "completion": 0}

    def get_token_usage(self) -> Dict[str, int]:
        """获取Token使用统计"""
        return {
            "prompt_tokens": self._total_tokens["prompt"],
            "completion_tokens": self._total_tokens["completion"],
            "total_tokens": self._total_tokens["prompt"] + self._total_tokens["completion"],
        }