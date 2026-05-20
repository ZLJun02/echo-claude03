# providers/anthropic.py
import json
import httpx
from typing import List, Iterator
from .base import BaseProvider, Message, ChatResponse, StreamChunk, Usage


class AnthropicProvider(BaseProvider):
    """Anthropic Claude 提供者 (基础实现，暂不支持工具调用)"""

    def chat(self, messages: List[Message], model: str, **kwargs) -> ChatResponse:
        if not self.validate_model(model):
            raise ValueError(f"Model '{model}' not in supported models: {self.models}")

        url = f"{self.base_url}/messages"
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }

        # 分离 system 消息
        system_prompt = None
        api_messages = []
        for msg in messages:
            if msg.role == "system":
                system_prompt = msg.content
            else:
                api_messages.append({"role": msg.role, "content": msg.content})

        payload: dict = {
            "model": model,
            "messages": api_messages,
            "stream": False,
            "max_tokens": kwargs.get("max_tokens", 4096),
        }
        if system_prompt:
            payload["system"] = system_prompt

        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

        content = ""
        if "content" in data and len(data["content"]) > 0:
            content = data["content"][0].get("text", "")

        usage_data = data.get("usage", {})
        usage = Usage(
            prompt_tokens=usage_data.get("input_tokens", 0),
            completion_tokens=usage_data.get("output_tokens", 0),
            total_tokens=usage_data.get("input_tokens", 0) + usage_data.get("output_tokens", 0),
        )
        return ChatResponse(content=content, usage=usage)

    def stream_chat(self, messages: List[Message], model: str, **kwargs) -> Iterator[StreamChunk]:
        if not self.validate_model(model):
            raise ValueError(f"Model '{model}' not in supported models: {self.models}")

        url = f"{self.base_url}/messages"
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        system_prompt = None
        api_messages = []
        for msg in messages:
            if msg.role == "system":
                system_prompt = msg.content
            else:
                api_messages.append({"role": msg.role, "content": msg.content})

        payload: dict = {
            "model": model,
            "messages": api_messages,
            "stream": True,
            "max_tokens": kwargs.get("max_tokens", 4096),
        }
        if system_prompt:
            payload["system"] = system_prompt

        with httpx.stream("POST", url, json=payload, headers=headers, timeout=self.timeout) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if not line.startswith("data: "):
                    continue
                data_str = line[6:].strip()
                try:
                    data = json.loads(data_str)
                    if data["type"] == "content_block_delta":
                        delta = data.get("delta", {})
                        content = delta.get("text", "")
                        yield StreamChunk(content=content)
                    elif data["type"] == "message_stop":
                        yield StreamChunk(finish_reason="stop")
                except json.JSONDecodeError:
                    continue