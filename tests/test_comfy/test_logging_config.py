import logging
import pytest

from logging_config import get_colorful_logger, ColorfulFormatter


def test_get_colorful_logger_returns_logger():
    logger = get_colorful_logger("test-logger")
    assert isinstance(logger, logging.Logger)
    assert logger.name == "test-logger"


def test_get_colorful_logger_no_duplicate_handlers():
    logger = get_colorful_logger("dup-logger")
    n = len(logger.handlers)
    logger2 = get_colorful_logger("dup-logger")
    assert logger2 is logger
    assert len(logger2.handlers) == n


def test_get_colorful_logger_fallback_streamhandler_formatting(monkeypatch, capsys):
    """
    当 rich 不可用时，应使用 StreamHandler + ColorfulFormatter，
    并输出包含分隔符与 ANSI 颜色码的日志。
    """
    import logging_config as lc
    monkeypatch.setattr(lc, "RICH_AVAILABLE", False, raising=False)

    logger = get_colorful_logger("lg-fallback-1")
    # 新名称 -> 不会复用旧 handler
    assert len(logger.handlers) == 1
    handler = logger.handlers[0]
    assert isinstance(handler, logging.StreamHandler)
    assert isinstance(handler.formatter, ColorfulFormatter)

    logger.info("hello-fallback")
    out = capsys.readouterr().out
    assert "hello-fallback" in out
    assert " | " in out  # 验证基本格式: 时间 | 等级 | 消息
    assert "\x1b[" in out  # 包含 ANSI 颜色序列


def test_logger_level_controls_output(monkeypatch, capsys):
    """
    验证日志级别过滤：当设置为 WARNING 时，INFO 不应输出，WARNING 应输出。
    """
    import logging_config as lc
    monkeypatch.setattr(lc, "RICH_AVAILABLE", False, raising=False)

    logger = get_colorful_logger("lg-level-1")

    # 设置更严格的级别到 logger 与其唯一的 handler
    logger.setLevel(logging.WARNING)
    for h in logger.handlers:
        h.setLevel(logging.WARNING)

    _ = capsys.readouterr()  # 清空缓冲
    logger.info("info-msg")
    logger.warning("warn-msg")
    captured = capsys.readouterr().out

    assert "info-msg" not in captured
    assert "warn-msg" in captured


def test_rich_branch_used_when_available(monkeypatch):
    """
    当 RICH_AVAILABLE=True 时，使用 RichHandler 路径。
    通过注入 FakeConsole/FakeRichHandler 模拟 rich 存在。
    """
    import logging_config as lc

    class FakeConsole:
        def __init__(self, *args, **kwargs):
            self.width = 80

    class FakeRichHandler(logging.Handler):
        def __init__(self, *args, **kwargs):
            super().__init__()

    # 注入假 rich 组件并开启 rich 分支
    monkeypatch.setattr(lc, "Console", FakeConsole, raising=False)
    monkeypatch.setattr(lc, "RichHandler", FakeRichHandler, raising=False)
    monkeypatch.setattr(lc, "RICH_AVAILABLE", True, raising=False)

    logger = get_colorful_logger("lg-rich-1")
    assert isinstance(logger, logging.Logger)
    assert len(logger.handlers) == 1
    handler = logger.handlers[0]
    assert isinstance(handler, FakeRichHandler)
    # rich 分支下 formatter 应为 '%(message)s'
    assert isinstance(handler.formatter, logging.Formatter)
    assert handler.formatter._fmt == "%(message)s"
