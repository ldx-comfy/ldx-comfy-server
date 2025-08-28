# 插件系统初始化文件
from .base import (
    Plugin,
    PluginMetadata,
    NodeHandlerPlugin,
    WorkflowExecutorPlugin,
    PluginRegistry,
    plugin_registry
)
from .manager import PluginManager, plugin_manager
from .node_handlers import ImageInputHandler, TextInputHandler, SwitchInputHandler
from .workflow_executors import ComfyUIWorkflowExecutor

__all__ = [
    # 基类和接口
    'Plugin',
    'PluginMetadata',
    'NodeHandlerPlugin',
    'WorkflowExecutorPlugin',
    'PluginRegistry',
    'plugin_registry',

    # 管理器
    'PluginManager',
    'plugin_manager',

    # 具体实现
    'ImageInputHandler',
    'TextInputHandler',
    'SwitchInputHandler',
    'ComfyUIWorkflowExecutor'
]