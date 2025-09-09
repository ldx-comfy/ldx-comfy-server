"""
彩色日志配置模块
提供统一的彩色日志配置
"""
import logging
import sys
from typing import Optional

try:
    from rich.console import Console
    from rich.logging import RichHandler
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False


class ColorfulFormatter(logging.Formatter):
    """彩色日志格式化器"""

    # ANSI颜色代码
    COLORS = {
        'DEBUG': '\033[36m',      # 青色
        'INFO': '\033[32m',       # 绿色
        'WARNING': '\033[33m',    # 黄色
        'ERROR': '\033[31m',      # 红色
        'CRITICAL': '\033[35m',   # 紫色
    }
    TIME_COLOR = '\033[34m'      # 蓝色（时间）
    RESET = '\033[0m'           # 重置颜色

    def format(self, record):
        # 获取原始格式化消息
        message = super().format(record)

        # 为时间着色
        if self._fmt and '%(asctime)s' in self._fmt:
            # 提取时间部分并着色
            time_str = self.formatTime(record, self.datefmt)
            message = message.replace(time_str, f"{self.TIME_COLOR}{time_str}{self.RESET}")

        # 为日志级别着色
        level_name = record.levelname
        if level_name in self.COLORS:
            colored_level = f"{self.COLORS[level_name]}{level_name}{self.RESET}"
            message = message.replace(level_name, colored_level)

        return message


def setup_colorful_logging(level: int = logging.INFO, name: Optional[str] = None) -> logging.Logger:
    """
    设置彩色日志配置

    Args:
        level: 日志级别
        name: 日志器名称

    Returns:
        配置好的日志器
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # 避免重复添加处理器
    if logger.handlers:
        return logger

    if RICH_AVAILABLE:
        # 使用Rich库（推荐）
        console = Console()
        handler = RichHandler(
            console=console,
            show_time=True,
            show_level=True,
            show_path=False,
            enable_link_path=False,
            markup=True,
            rich_tracebacks=True,
            tracebacks_width=console.width,
            tracebacks_show_locals=False,
        )
        handler.setLevel(level)

        # 设置格式 - 移除重复的时间和级别，因为RichHandler已经处理了
        formatter = logging.Formatter(
            '%(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)

    else:
        # 使用ANSI颜色
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(level)

        # 使用彩色格式化器
        formatter = ColorfulFormatter(
            '%(asctime)s | %(levelname)s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)

    logger.addHandler(handler)
    return logger


def get_colorful_logger(name: Optional[str] = None) -> logging.Logger:
    """
    获取彩色日志器

    Args:
        name: 日志器名称

    Returns:
        彩色日志器
    """
    return setup_colorful_logging(name=name)