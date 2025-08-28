#!/usr/bin/env python3
"""
插件系统测试脚本
"""
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from comfy.plugins import plugin_manager, plugin_registry

def test_plugin_discovery():
    """测试插件发现"""
    print("=== 测试插件发现 ===")
    print(f"发现的插件数量: {len(plugin_registry._plugins)}")

    for name, plugin in plugin_registry._plugins.items():
        print(f"- {name}: {plugin.metadata.description} (v{plugin.metadata.version})")

    print()

def test_node_handlers():
    """测试节点处理器"""
    print("=== 测试节点处理器 ===")

    test_node_types = ["LoadImageOutput", "Text", "Switch any [Crystools]", "UnknownNode"]

    for node_type in test_node_types:
        try:
            handler = plugin_manager.get_node_handler(node_type)
            print(f"✓ {node_type} -> {handler.metadata.name}")
        except ValueError as e:
            print(f"✗ {node_type} -> {e}")

    print()

def test_workflow_executors():
    """测试工作流执行器"""
    print("=== 测试工作流执行器 ===")

    try:
        executor = plugin_manager.get_workflow_executor()
        print(f"✓ 默认执行器: {executor.metadata.name}")
    except ValueError as e:
        print(f"✗ 获取执行器失败: {e}")

    print()

def test_plugin_initialization():
    """测试插件初始化"""
    print("=== 测试插件初始化 ===")

    config = {
        'server_address': '106.52.220.169:6889',
        'output_dir': 'comfy_out_image'
    }

    try:
        plugin_manager.initialize_plugins(config)
        print("✓ 插件初始化成功")
    except Exception as e:
        print(f"✗ 插件初始化失败: {e}")

    print()

def main():
    """主测试函数"""
    print("开始插件系统测试...\n")

    # 发现插件
    plugin_manager.discover_and_register_plugins()

    # 运行各项测试
    test_plugin_discovery()
    test_node_handlers()
    test_workflow_executors()
    test_plugin_initialization()

    # 清理插件
    plugin_manager.cleanup_plugins()

    print("插件系统测试完成!")

if __name__ == "__main__":
    main()