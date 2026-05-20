# providers/local.py
from typing import List
from .openai import OpenAIProvider


class LocalProvider(OpenAIProvider):
    """本地模型提供者 (Ollama, LocalAI, LM Studio)"""

    def __init__(self, api_key: str = None, base_url: str = None, models: List[str] = None, **kwargs):
        # 默认 base_url 为本地常见地址
        if base_url is None:
            base_url = "http://localhost:11434"
        # 本地模型通常不需要 api_key，但传一个默认值
        super().__init__(api_key=api_key or "ollama", base_url=base_url, models=models, **kwargs)