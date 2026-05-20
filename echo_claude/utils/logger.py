"""
日志模块
提供统一的日志配置和获取接口
"""

import logging
import sys
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.logging import RichHandler


def get_logger(
    name: str,
    level: str = "INFO",
    log_file: Optional[str] = None,
    use_rich: bool = True,
) -> logging.Logger:
    """
    获取配置好的日志器

    Args:
        name: 日志器名称
        level: 日志级别
        log_file: 日志文件路径（可选）
        use_rich: 是否使用Rich美化控制台输出

    Returns:
        配置好的 Logger 实例
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # 避免重复添加处理器
    if logger.handlers:
        return logger

    if use_rich and sys.stderr.isatty():
        # 使用 Rich 处理器
        console = Console(stderr=True)
        rich_handler = RichHandler(
            console=console,
            show_time=True,
            show_path=False,
            markup=True,
        )
        rich_handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(rich_handler)
    else:
        # 普通处理器
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    # 文件处理器
    if log_file:
        log_path = Path(log_file).expanduser()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_path, encoding='utf-8')
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))
        logger.addHandler(file_handler)

    return logger