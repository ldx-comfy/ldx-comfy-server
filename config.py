"""
配置管理
"""

import os
import pathlib
import json

# 注册路径
DATA_BASE_PATH = pathlib.Path(os.environ.get("DATA_BASE_PATH", "./data"))
COMFY_OUTPUT_DIR = DATA_BASE_PATH / "comfy_output"
UPLOAD_DIR = DATA_BASE_PATH / "uploads"
WORKFLOWS_DIR = DATA_BASE_PATH / "workflows"
COMFY_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
WORKFLOWS_DIR.mkdir(parents=True, exist_ok=True)


CONFIG_FILE = DATA_BASE_PATH / "config.json"


def check_config(example, current):
    for key, value in example.items():
        if key not in current:
            current[key] = value
        elif isinstance(value, dict):
            if not isinstance(current[key], dict):
                current[key] = value
            else:
                check_config(value, current[key])


class ConfigManager:
    """配置管理器"""

    config_example = {
        "comfy_server_address": "YOUR_COMFYUI_SERVER_ADDRESS",
        "comfy_timeout": 0,
        'ws_timeout': 0,
        'http_timeout': 0,
    }

    def __init__(self, config_path: pathlib.Path):
        self.config_path = config_path
        self.config = {}
        self.load_config()

    def load_config(self):
        """加载配置"""
        if self.config_path.exists():
            with open(self.config_path, "r", encoding="utf-8") as f:
                self.config = json.load(f)
            # 检查配置项是否完整
            check_config(self.config_example, self.config)
            self.save_config()  # 保存更新后的配置
        else:
            # 初始化配置文件
            self.config = self.config_example.copy()
            self.save_config()

    def save_config(self):
        """保存配置"""
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(self.config, f, indent=4)

    def get(self, key: str, default=None):
        """获取配置项"""
        return self.config.get(key, default)

    def set(self, key: str, value):
        """设置配置项"""
        self.config[key] = value
        self.save_config()
