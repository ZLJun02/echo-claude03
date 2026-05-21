# providers/anthropic.py
import json
import time
import httpx
from typing import List, Iterator
from .base import BaseProvider, Message, ChatResponse, StreamChunk, Usage


class AnthropicProvider(BaseProvider):
    """Anthropic Claude 提供者 (基础实现，暂不支持工具调用)"""

    def _build_payload(self, messages: List[Message], model: str, stream: bool, **kwargs) -> dict:
        """Build request payload for Anthropic API"""
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
            "stream": stream,
            "max_tokens": kwargs.get("max_tokens", 4096),
        }
        if system_prompt:
            payload["system"] = system_prompt
        return payload

    def chat(self, messages: List[Message], model: str, **kwargs) -> ChatResponse:
        if not self.validate_model(model):
            raise ValueError(f"Model '{model}' not in supported models: {self.models}")

        url = f"{self.base_url}/messages"
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        payload = self._build_payload(messages, model, False, **kwargs)

        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    response = client.post(url, json=payload, headers=headers)
                
                status = response.status_code
                if status == 401:
                    raise RuntimeError(f"API Key 无效 (HTTP 401)")
                if status == 429:
                    retry_after = response.headers.get("Retry-After", "5")
                    wait = int(retry_after) if retry_after.isdigit() else 5
                    if attempt < self.max_retries:
                        time.sleep(wait)
                        continue
                    raise RuntimeError("API 请求频率过高")
                if status >= 500:
                    if attempt < self.max_retries:
                        time.sleep(2 ** attempt)
                        continue
                    raise RuntimeError(f"服务端错误 (HTTP {status})")
                
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

            except (httpx.TimeoutException, httpx.ConnectError) as e:
                last_error = e
                if attempt < self.max_retries:
                    time.sleep(2 ** attempt)
                    continue
                raise RuntimeError(f"网络连接失败: {e}")

        raise RuntimeError(f"请求失败，已重试 {self.max_retries} 次: {last_error}")

    def stream_chat(self, messages: List[Message], model: str, **kwargs) -> Iterator[StreamChunk]:
        if not self.validate_model(model):
            raise ValueError(f"Model '{model}' not in supported models: {self.models}")

        url = f"{self.base_url}/messages"
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        payload = self._build_payload(messages, model, True, **kwargs)

        try:
            with httpx.stream("POST", url, json=payload, headers=headers, timeout=self.timeout) as response:
                if response.status_code == 401:
                    raise RuntimeError(f"API Key 无效 (HTTP 401)")
                response.raise_for_status()
                for line in response.iter_lines():
                    if not line.startswith("data: "):
                        continue
                    data_str = line[6:].strip()
                    try:
                        data = json.loads(data_str)
                        if data["type"] == "content_block_delta":
                            delta = data.get("delta", {})
                            text_content = delta.get("text", "")
                            yield StreamChunk(content=text_content)
                        elif data["type"] == "message_stop":
                            yield StreamChunk(finish_reason="stop")
                    except json.JSONDecodeError:
                        continue
        except httpx.TimeoutException:
            raise RuntimeError("请求超时")
        except httpx.ConnectError as e:
            raise RuntimeError(f"无法连接到 API 服务器: {e}")