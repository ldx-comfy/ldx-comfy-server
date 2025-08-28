#!/usr/bin/env python3
"""
插件系统测试脚本
"""
import sys
import os
from comfy.logging_config import get_colorful_logger

# 配置彩色日志
logger = get_colorful_logger(__name__)

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from comfy.plugins import plugin_manager, plugin_registry

def test_plugin_discovery():
    """测试插件发现"""
    logger.info("=== 测试插件发现 ===")
    logger.info(f"发现的插件数量: {len(plugin_registry._plugins)}")

    for name, plugin in plugin_registry._plugins.items():
        logger.info(f"- {name}: {plugin.metadata.description} (v{plugin.metadata.version})")

    logger.info("")

def test_node_handlers():
    """测试节点处理器"""
    logger.info("=== 测试节点处理器 ===")

    test_node_types = ["LoadImageOutput", "Text", "Switch any [Crystools]", "UnknownNode"]

    for node_type in test_node_types:
        try:
            handler = plugin_manager.get_node_handler(node_type)
            logger.info(f"✓ {node_type} -> {handler.metadata.name}")
        except ValueError as e:
            logger.error(f"✗ {node_type} -> {e}")

    logger.info("")

def test_workflow_executors():
    """测试工作流执行器"""
    logger.info("=== 测试工作流执行器 ===")

    try:
        executor = plugin_manager.get_workflow_executor()
        logger.info(f"✓ 默认执行器: {executor.metadata.name}")
    except ValueError as e:
        logger.error(f"✗ 获取执行器失败: {e}")

    logger.info("")

def test_plugin_initialization():
    """测试插件初始化"""
    logger.info("=== 测试插件初始化 ===")

    config = {
        'server_address': '106.52.220.169:6889',
        'output_dir': 'comfy_out_image'
    }

    try:
        plugin_manager.initialize_plugins(config)
        logger.info("✓ 插件初始化成功")
    except Exception as e:
        logger.error(f"✗ 插件初始化失败: {e}")

    logger.info("")

def main():
    """主测试函数"""
    logger.info("开始插件系统测试...\n")

    # 发现插件
    plugin_manager.discover_and_register_plugins()

    # 运行各项测试
    test_plugin_discovery()
    test_node_handlers()
    test_workflow_executors()
    test_plugin_initialization()

    # 清理插件
    plugin_manager.cleanup_plugins()

    logger.info("插件系统测试完成!")

if __name__ == "__main__":
    main()