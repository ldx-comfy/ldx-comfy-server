"""
插件管理器
"""
import importlib
import pkgutil
import inspect
from typing import Dict, Any, List, Type, Optional
from .base import Plugin, NodeHandlerPlugin, WorkflowExecutorPlugin, plugin_registry


class PluginManager:
    """插件管理器"""

    def __init__(self):
        self._plugin_packages = [
            'comfy.plugins.node_handlers',
            'comfy.plugins.workflow_executors'
        ]

    def discover_and_register_plugins(self) -> None:
        """自动发现并注册插件"""
        for package_name in self._plugin_packages:
            self._load_plugins_from_package(package_name)

    def _load_plugins_from_package(self, package_name: str) -> None:
        """从包中加载插件"""
        try:
            package = importlib.import_module(package_name)
        except ImportError:
            print(f"无法导入包: {package_name}")
            return

        # 遍历包中的所有模块
        if hasattr(package, '__path__'):
            for _, module_name, _ in pkgutil.iter_modules(package.__path__, package_name + "."):
                try:
                    module = importlib.import_module(module_name)
                    self._register_plugins_from_module(module)
                except Exception as e:
                    print(f"加载模块 {module_name} 时出错: {e}")

        # 直接从当前模块注册插件
        self._register_plugins_from_module(package)

    def _register_plugins_from_module(self, module) -> None:
        """从模块中注册插件"""
        for name, obj in inspect.getmembers(module):
            if (inspect.isclass(obj) and
                issubclass(obj, Plugin) and
                obj != Plugin and
                obj != NodeHandlerPlugin and
                obj != WorkflowExecutorPlugin):

                try:
                    # 实例化插件
                    plugin_instance = obj()
                    # 注册插件
                    plugin_registry.register_plugin(plugin_instance)
                    print(f"已注册插件: {plugin_instance.metadata.name} ({plugin_instance.metadata.plugin_type})")
                except Exception as e:
                    print(f"注册插件 {name} 时出错: {e}")

    def initialize_plugins(self, config: Dict[str, Any]) -> None:
        """初始化所有已注册的插件"""
        for plugin in plugin_registry._plugins.values():
            try:
                plugin.initialize(config)
            except Exception as e:
                print(f"初始化插件 {plugin.metadata.name} 时出错: {e}")

    def cleanup_plugins(self) -> None:
        """清理所有插件"""
        for plugin in plugin_registry._plugins.values():
            try:
                plugin.cleanup()
            except Exception as e:
                print(f"清理插件 {plugin.metadata.name} 时出错: {e}")

    def get_node_handler(self, node_type: str) -> NodeHandlerPlugin:
        """获取适合处理指定节点类型的处理器"""
        handlers = plugin_registry.get_node_handlers_for_type(node_type)
        if not handlers:
            raise ValueError(f"未找到能处理节点类型 '{node_type}' 的处理器")
        return handlers[0]  # 返回第一个匹配的处理器

    def get_workflow_executor(self, name: Optional[str] = None) -> WorkflowExecutorPlugin:
        """获取工作流执行器"""
        if name:
            executor = plugin_registry.get_workflow_executor(name)
            if not executor:
                raise ValueError(f"未找到工作流执行器 '{name}'")
            return executor

        # 返回默认执行器
        executors = list(plugin_registry._workflow_executors.values())
        if not executors:
            raise ValueError("未找到任何工作流执行器")
        return executors[0]


# 全局插件管理器实例
plugin_manager = PluginManager()