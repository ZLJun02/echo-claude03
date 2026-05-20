# providers/zhipu.py
from typing import List
from .openai import OpenAIProvider


class ZhipuProvider(OpenAIProvider):
    """智谱 GLM 提供者 (OpenAI 兼容接口)"""

    def __init__(self, api_key: str = None, base_url: str = None, models: List[str] = None, **kwargs):
        # 默认 base_url 为智谱 API
        if base_url is None:
            base_url = "https://open.bigmodel.cn/api/paas/v4"
        super().__init__(api_key=api_key, base_url=base_url, models=models, **kwargs)