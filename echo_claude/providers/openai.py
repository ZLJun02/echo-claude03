# providers/openai.py
import json
import time
import logging
import httpx
from typing import List, Iterator
from .base import BaseProvider, Message, ChatResponse, StreamChunk, ToolCall, ToolFunction, Usage

logger = logging.getLogger("echo_claude.providers.openai")

# 需要重试的 HTTP 状态码
RETRYABLE_STATUSES = {429, 500, 502, 503, 504}


class ProviderError(Exception):
    """Provider 通用错误"""

    def __init__(self, message: str, status_code: int = None, retryable: bool = False):
        super().__init__(message)
        self.status_code = status_code
        self.retryable = retryable


class AuthenticationError(ProviderError):
    """认证错误 (401)"""
    pass


class RateLimitError(ProviderError):
    """限流错误 (429)"""
    pass


class OpenAIProvider(BaseProvider):
    """OpenAI 提供者（含错误处理和自动重试）"""

    def __init__(self, api_key: str, base_url: str = None, models: List[str] = None, timeout: int = 30, max_retries: int = 3, **kwargs):
        super().__init__(api_key=api_key, base_url=base_url, models=models, timeout=timeout, max_retries=max_retries, **kwargs)
        self._client = httpx.Client(timeout=self.timeout, follow_redirects=True)

    def _request_with_retry(
        self,
        method: str,
        url: str,
        headers: dict,
        payload: dict,
        stream: bool = False,
    ) -> httpx.Response:
        """带重试的 HTTP 请求"""
        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                client = self._client
                if stream:
                    # 流式请求不重试（已开始消费）
                    response = httpx.stream(
                        method, url, json=payload, headers=headers,
                        timeout=self.timeout
                    )
                    response.raise_for_status()
                    return response
                else:
                    response = client.post(url, json=payload, headers=headers)
                    status = response.status_code

                    if status == 401:
                        raise AuthenticationError(
                            "API Key 无效或已过期，请检查配置", status_code=401
                        )
                    if status == 429:
                        retry_after = response.headers.get("Retry-After", "5")
                        wait = int(retry_after) if retry_after.isdigit() else 5
                        logger.warning("触发限流，等待 %ds 后重试 (第 %d/%d 次)",
                                       wait, attempt + 1, self.max_retries)
                        if attempt < self.max_retries:
                            time.sleep(wait)
                            continue
                        raise RateLimitError("API 请求频率过高，请稍后重试", status_code=429, retryable=True)
                    if status in RETRYABLE_STATUSES:
                        if attempt < self.max_retries:
                            wait = 2 ** attempt  # 指数退避
                            logger.warning("服务端错误 %d，%ds 后重试 (第 %d/%d 次)",
                                           status, wait, attempt + 1, self.max_retries)
                            time.sleep(wait)
                            continue
                        raise ProviderError(
                            f"服务暂时不可用 (HTTP {status})", status_code=status, retryable=True
                        )

                    response.raise_for_status()
                    return response

            except (httpx.TimeoutException, httpx.ConnectError, httpx.RemoteProtocolError) as e:
                last_error = e
                if attempt < self.max_retries:
                    wait = 2 ** attempt
                    logger.warning("网络错误: %s，%ds 后重试 (第 %d/%d 次)",
                                   e, wait, attempt + 1, self.max_retries)
                    time.sleep(wait)
                    continue
                raise ProviderError(f"网络连接失败: {e}", retryable=True)

            except (AuthenticationError, RateLimitError, ProviderError):
                raise
            except httpx.HTTPStatusError as e:
                raise ProviderError(f"HTTP 错误: {e.response.status_code} - {e.response.text[:200]}",
                                    status_code=e.response.status_code)

        raise ProviderError(f"请求失败，已重试 {self.max_retries} 次: {last_error}", retryable=True)

    def chat(self, messages: List[Message], model: str, **kwargs) -> ChatResponse:
        if not self.validate_model(model):
            raise ValueError(f"Model '{model}' not in supported models: {self.models}")

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        if "max_tokens" not in kwargs:
            kwargs["max_tokens"] = 1024
        payload = {
            "model": model,
            "messages": [m.to_dict() for m in messages],
            "stream": False,
            **kwargs
        }

        logger.debug("发送请求: model=%s, messages=%d", model, len(messages))
        response = self._request_with_retry("POST", url, headers, payload, stream=False)
        data = response.json()

        if not data.get("choices"):
            raise ProviderError(f"No choices in response: {data}")
        choice = data["choices"][0]
        message_data = choice["message"]
        content = message_data.get("content", "") or ""
        tool_calls = []
        if "tool_calls" in message_data:
            for tc in message_data["tool_calls"]:
                func = tc["function"]
                tool_call = ToolCall(
                    id=tc["id"],
                    function=ToolFunction(
                        name=func["name"],
                        arguments=func["arguments"]
                    )
                )
                tool_calls.append(tool_call)

        usage_data = data.get("usage", {})
        usage = Usage(
            prompt_tokens=usage_data.get("prompt_tokens", 0),
            completion_tokens=usage_data.get("completion_tokens", 0),
            total_tokens=usage_data.get("total_tokens", 0),
        )
        return ChatResponse(content=content, tool_calls=tool_calls, usage=usage)

    def stream_chat(self, messages: List[Message], model: str, **kwargs) -> Iterator[StreamChunk]:
        if not self.validate_model(model):
            raise ValueError(f"Model '{model}' not in supported models: {self.models}")

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": model,
            "messages": [m.to_dict() for m in messages],
            "stream": True,
            **kwargs
        }

        try:
            with httpx.stream("POST", url, json=payload, headers=headers,
                              timeout=self.timeout) as response:
                if response.status_code == 401:
                    raise AuthenticationError("API Key 无效或已过期，请检查配置", status_code=401)
                response.raise_for_status()

                for line in response.iter_lines():
                    if not line.startswith("data: "):
                        continue
                    data_str = line[6:].strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        data = json.loads(data_str)
                        if not data.get("choices"):
                            logger.warning("No choices in response, skipping: %s", data)
                            continue
                        delta = data["choices"][0]["delta"]
                        content = delta.get("content") or ""
                        tool_calls = []
                        if "tool_calls" in delta:
                            for tc in delta["tool_calls"]:
                                func = tc.get("function", {})
                                tool_call = ToolCall(
                                    id=tc.get("id", ""),
                                    function=ToolFunction(
                                        name=func.get("name", ""),
                                        arguments=func.get("arguments", "")
                                    )
                                )
                                tool_calls.append(tool_call)
                        finish_reason = data["choices"][0].get("finish_reason")
                        yield StreamChunk(content=content, tool_calls=tool_calls, finish_reason=finish_reason)
                    except json.JSONDecodeError:
                        continue

        except httpx.TimeoutException:
            raise ProviderError("请求超时，请检查网络或增大超时时间", retryable=True)
        except httpx.ConnectError as e:
            raise ProviderError(f"无法连接到 API 服务器: {e}", retryable=True)