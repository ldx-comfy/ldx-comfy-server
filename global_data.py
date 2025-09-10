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

# 身分組文件路徑
GROUPS_FILE = DATA_BASE_PATH / "groups.json"

# 如果身分組文件不存在，則創建一個空的文件
if not GROUPS_FILE.exists():
    initial_groups_data = {
        "groups": {},
        "system_permissions": {
            "user:create": "創建用戶",
            "user:delete": "删除用戶",
            "user:update": "修改用戶",
            "user:read": "查看用戶",
            "user:reset_password": "重置用戶密碼",
            "workflow:create": "创建工作流",
            "workflow:delete": "删除工作流",
            "workflow:update": "修改工作流",
            "workflow:read": "查看工作流",
            "workflow:execute": "執行工作流",
            "history:read": "查看歷史紀錄",
            "history:delete": "删除歷史紀錄",
            "group:create": "創建身分組",
            "group:delete": "删除身分組",
            "group:update": "修改身分組",
            "group:read": "查看身分組"
        }
    }
    with open(GROUPS_FILE, "w", encoding="utf-8") as f:
        json.dump(initial_groups_data, f, ensure_ascii=False, indent=2)

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