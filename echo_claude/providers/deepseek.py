# providers/deepseek.py
from typing import List
from .openai import OpenAIProvider


class DeepSeekProvider(OpenAIProvider):
    """DeepSeek 提供者 (兼容 OpenAI)"""

    def __init__(self, api_key: str = None, base_url: str = None, models: List[str] = None, **kwargs):
        # 默认 base_url 为 DeepSeek API
        if base_url is None:
            base_url = "https://api.deepseek.com/v1"
        super().__init__(api_key=api_key, base_url=base_url, models=models, **kwargs)