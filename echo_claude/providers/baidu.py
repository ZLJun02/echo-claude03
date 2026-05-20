# providers/baidu.py
from typing import List
from .openai import OpenAIProvider


class BaiduProvider(OpenAIProvider):
    """百度文心一言提供者 (OpenAI 兼容接口)"""

    def __init__(
        self,
        api_key: str = None,
        base_url: str = None,
        models: List[str] = None,
        **kwargs,
    ):
        if base_url is None:
            base_url = "https://qianfan.baidubce.com/v2"
        super().__init__(api_key=api_key, base_url=base_url, models=models, **kwargs)