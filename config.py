"""
配置管理
"""

import os
import pathlib
import json
import shutil

# 注册路径
DATA_BASE_PATH = pathlib.Path(os.environ.get("DATA_BASE_PATH", "./data"))
COMFY_OUTPUT_DIR = DATA_BASE_PATH / "comfy_output"
UPLOAD_DIR = DATA_BASE_PATH / "uploads"
WORKFLOWS_DIR = DATA_BASE_PATH / "workflows"
COMFY_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
# 如无workflows目录，则copy ./wf_files到该目录
if not WORKFLOWS_DIR.exists():
    shutil.copytree("./wf_files", WORKFLOWS_DIR)


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
def check_config_type(example, current) -> bool:
    for key, value in example.items():
        if key not in current:
            return False
        elif isinstance(value, dict):
            if not isinstance(current[key], dict):
                return False
            else:
                if not check_config_type(value, current[key]):
                    return False
        else:
            if not isinstance(current[key], type(value)):
                return False
    return True

class ConfigManager:
    """配置管理器"""

    config_example = {
        "comfy_server_address": "YOUR_COMFYUI_SERVER_ADDRESS",
        "comfy_timeout": 0,
        'ws_timeout': 0,
        'http_timeout': 0,
        "cors": ["*"],
    }

    def __init__(self, config_path: pathlib.Path = CONFIG_FILE):
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
            # 检查配置项类型是否正确
            if not check_config_type(self.config_example, self.config):
                print("配置文件类型不匹配，已重置为默认配置")
                self.config = self.config_example.copy()
                self.save_config()
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


config_manager = ConfigManager()