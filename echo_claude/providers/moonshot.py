# providers/moonshot.py
from typing import List
from .openai import OpenAIProvider


class MoonshotProvider(OpenAIProvider):
    """Moonshot (Kimi) 提供者 (OpenAI 兼容接口)"""

    def __init__(
        self,
        api_key: str = None,
        base_url: str = None,
        models: List[str] = None,
        **kwargs,
    ):
        if base_url is None:
            base_url = "https://api.moonshot.cn/v1"
        super().__init__(api_key=api_key, base_url=base_url, models=models, **kwargs)