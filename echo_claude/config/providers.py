"""
预定义的模型提供者配置模板
包含国内外主流AI模型的基础配置
"""

from typing import Dict, List, Optional
from .settings import ProviderConfig


# 预定义提供者配置模板
PROVIDER_TEMPLATES: Dict[str, Dict] = {
    "openai": {
        "name": "openai",
        "base_url": "https://api.openai.com/v1",
        "models": [
            "gpt-4o",
            "gpt-4-turbo",
            "gpt-4",
            "gpt-3.5-turbo",
        ],
        "env_var": "OPENAI_API_KEY",
        "description": "OpenAI GPT-4 / GPT-3.5 系列",
    },
    "anthropic": {
        "name": "anthropic",
        "base_url": "https://api.anthropic.com/v1",
        "models": [
            "claude-3-opus-20240229",
            "claude-3-sonnet-20240229",
            "claude-3-haiku-20240307",
        ],
        "env_var": "ANTHROPIC_API_KEY",
        "description": "Anthropic Claude 系列",
    },
    "deepseek": {
        "name": "deepseek",
        "base_url": "https://api.deepseek.com/v1",
        "models": [
            "deepseek-chat",
            "deepseek-coder",
        ],
        "env_var": "DEEPSEEK_API_KEY",
        "description": "DeepSeek 智能对话与编程模型",
    },
    "baidu": {
        "name": "baidu",
        "base_url": "https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop",
        "models": [
            "ERNIE-4.0-8K",
            "ERNIE-3.5-8K",
            "ERNIE-Bot-turbo",
        ],
        "env_var": "BAIDU_API_KEY",
        "description": "百度文心一言",
    },
    "zhipu": {
        "name": "zhipu",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "models": [
            "glm-5v-turbo",          # 视觉多模态，支持图片
            "glm-4",
            "glm-3-turbo",
            "chatglm_turbo",
        ],
        "env_var": "ZHIPU_API_KEY",
        "description": "智谱 AI GLM 系列（含GLM-5V视觉模型）",
    },
    "moonshot": {
        "name": "moonshot",
        "base_url": "https://api.moonshot.cn/v1",
        "models": [
            "moonshot-v1-8k",
            "moonshot-v1-32k",
            "moonshot-v1-128k",
        ],
        "env_var": "MOONSHOT_API_KEY",
        "description": "Moonshot (Kimi) 大模型",
    },
    "local": {
        "name": "local",
        "base_url": "http://localhost:11434",
        "models": [
            "llama2",
            "codellama",
            "mistral",
            "neural-chat",
        ],
        "env_var": None,
        "description": "本地模型 (Ollama)",
    },
    "localai": {
        "name": "localai",
        "base_url": "http://localhost:8080/v1",
        "models": [],
        "env_var": None,
        "description": "LocalAI 兼容接口",
    },
    "lmstudio": {
        "name": "lmstudio",
        "base_url": "http://localhost:1234/v1",
        "models": [],
        "env_var": None,
        "description": "LM Studio 本地服务",
    },
}


def get_provider_template(name: str) -> Optional[ProviderConfig]:
    """获取预定义的提供者模板"""
    template = PROVIDER_TEMPLATES.get(name)
    if not template:
        return None

    return ProviderConfig(**{k: v for k, v in template.items()
                            if k not in ["env_var", "description"]})


def list_available_providers() -> List[Dict[str, str]]:
    """列出所有可用的提供者"""
    return [
        {
            "name": name,
            "description": data.get("description", ""),
            "models": data.get("models", []),
            "env_var": data.get("env_var"),
        }
        for name, data in PROVIDER_TEMPLATES.items()
    ]


def get_provider_by_env(env_var: str) -> Optional[str]:
    """通过环境变量名查找提供者"""
    for name, data in PROVIDER_TEMPLATES.items():
        if data.get("env_var") == env_var:
            return name
    return None