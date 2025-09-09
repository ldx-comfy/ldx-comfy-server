"""
插件系统基类和接口定义
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from pydantic import BaseModel


class PluginMetadata(BaseModel):
    """插件元数据"""
    name: str
    version: str
    description: str
    author: str
    plugin_type: str


class Plugin(ABC):
    """插件基类"""

    @property
    @abstractmethod
    def metadata(self) -> PluginMetadata:
        """插件元数据"""
        pass

    @abstractmethod
    def initialize(self, config: Dict[str, Any]) -> None:
        """初始化插件"""
        pass

    @abstractmethod
    def cleanup(self) -> None:
        """清理插件资源"""
        pass


class NodeHandlerPlugin(Plugin):
    """节点处理器插件接口"""

    @abstractmethod
    def can_handle(self, node_type: str) -> bool:
        """判断是否能处理指定类型的节点"""
        pass

    @abstractmethod
    def handle_node(self, node_id: str, node_info: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """处理节点"""
        pass

    @abstractmethod
    def get_required_inputs(self) -> List[str]:
        """获取处理节点所需的输入参数"""
        pass


class WorkflowExecutorPlugin(Plugin):
    """工作流执行器插件接口"""

    @abstractmethod
    def execute_workflow(self, workflow_data: Dict[str, Any], inputs: Dict[str, Any]) -> Dict[str, Any]:
        """执行工作流"""
        pass

    @abstractmethod
    def get_execution_status(self, execution_id: str) -> Dict[str, Any]:
        """获取执行状态"""
        pass

    @abstractmethod
    def cancel_execution(self, execution_id: str) -> bool:
        """取消执行"""
        pass


class PluginRegistry:
    """插件注册器"""

    def __init__(self):
        self._node_handlers: Dict[str, NodeHandlerPlugin] = {}
        self._workflow_executors: Dict[str, WorkflowExecutorPlugin] = {}
        self._plugins: Dict[str, Plugin] = {}

    def register_plugin(self, plugin: Plugin) -> None:
        """注册插件"""
        plugin_name = plugin.metadata.name

        # 检查是否已经注册过相同名称的插件
        if plugin_name in self._plugins:
            from logging_config import get_colorful_logger
            logger = get_colorful_logger(__name__)
            logger.info(f"插件 '{plugin_name}' 已经注册，跳过重复注册")
            return

        self._plugins[plugin_name] = plugin

        if isinstance(plugin, NodeHandlerPlugin):
            # 注册节点处理器插件
            self._node_handlers[plugin_name] = plugin
        elif isinstance(plugin, WorkflowExecutorPlugin):
            # 注册工作流执行器插件
            self._workflow_executors[plugin_name] = plugin

    def get_node_handler(self, plugin_name: str) -> Optional[NodeHandlerPlugin]:
        """获取节点处理器插件"""
        return self._node_handlers.get(plugin_name)

    def get_workflow_executor(self, plugin_name: str) -> Optional[WorkflowExecutorPlugin]:
        """获取工作流执行器插件"""
        return self._workflow_executors.get(plugin_name)

    def get_node_handlers_for_type(self, node_type: str) -> List[NodeHandlerPlugin]:
        """获取能处理指定节点类型的处理器"""
        return [handler for handler in self._node_handlers.values() if handler.can_handle(node_type)]

    def list_plugins(self) -> Dict[str, PluginMetadata]:
        """列出所有已注册的插件"""
        return {name: plugin.metadata for name, plugin in self._plugins.items()}


# 全局插件注册器实例
plugin_registry = PluginRegistry()