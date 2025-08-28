"""
插件配置文件
"""
from typing import Dict, Any

# 插件系统配置
PLUGIN_CONFIG = {
    # ComfyUI服务器配置
    'server_address': '106.52.220.169:6889',
    'client_id': None,  # 将在运行时生成

    # 输出配置
    'output_dir': 'comfy_out_image',

    # 插件特定配置
    'node_handlers': {
        'image_input_handler': {
            'upload_timeout': 30,
            'max_file_size': 10 * 1024 * 1024  # 10MB
        },
        'text_input_handler': {
            'max_length': 1000
        },
        'switch_input_handler': {
            'default_value': False
        }
    },

    'workflow_executors': {
        'comfyui_workflow_executor': {
            'websocket_timeout': 300,
            'max_retries': 3,
            'retry_delay': 1.0
        }
    }
}

# 插件加载配置
ENABLED_PLUGINS = [
    'comfy.plugins.node_handlers.ImageInputHandler',
    'comfy.plugins.node_handlers.TextInputHandler',
    'comfy.plugins.node_handlers.SwitchInputHandler',
    'comfy.plugins.workflow_executors.ComfyUIWorkflowExecutor'
]

# 插件依赖配置
PLUGIN_DEPENDENCIES = {
    'comfy.plugins.workflow_executors.ComfyUIWorkflowExecutor': [
        'comfy.plugins.node_handlers.ImageInputHandler',
        'comfy.plugins.node_handlers.TextInputHandler',
        'comfy.plugins.node_handlers.SwitchInputHandler'
    ]
}