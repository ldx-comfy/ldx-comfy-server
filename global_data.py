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
# 認證信息文件路徑 (包含用戶、身分組等配置)
AUTH_FILE = DATA_BASE_PATH / "auth.json"

# 身分組權限列表 (用於前端展示和後端權限定義參考)
# 這裡定義的權限會被加載到 auth.json 的初始 groups 設置中
SYSTEM_PERMISSIONS = {
    "admin:access": "訪問管理面板",
    "admin:users:read": "查看用戶信息",
    "admin:users:manage": "管理用戶 (增刪改查、重置密碼、修改身分組/角色/狀態)",
    "admin:groups:read": "查看身分組信息",
    "admin:groups:manage": "管理身分組 (增刪改)",
    "admin:workflows:read": "查看工作流列表",
    "admin:workflows:manage": "管理工作流 (上傳、删除)",
    "admin:history:read": "查看所有執行歷史",
    "admin:codes:read": "查看授權碼",
    "admin:codes:manage": "管理授權碼 (增刪)",
    "workflow:read:*": "讀取所有工作流 (通配符)",
    "workflow:execute:*": "執行所有工作流 (通配符)",
    "user:read:self": "查看自己的用戶信息",
    "user:update:self": "更新自己的用戶信息",
    "user:reset_password:self": "重置自己的密碼",
    "history:read:self": "查看自己的執行歷史"
}

# 確保 AUTH_FILE 存在且初始化
if not AUTH_FILE.exists():
    initial_auth_data = {
        "jwt_secret": "your-jwt-secret-here-change-in-production",
        "jwt_expires_seconds": 3600,
        "users": [],
        "codes": [],
        "groups": {
            "admin": {
                "name": "Admin Group",
                "description": "擁有所有管理面板權限",
                "permissions": list(SYSTEM_PERMISSIONS.keys()),
                "level": 100
            },
            "user": {
                "name": "User Group",
                "description": "普通用戶，具備基本操作權限",
                "permissions": [
                    "workflow:read:*",
                    "workflow:execute:*",
                    "user:read:self",
                    "user:update:self",
                    "user:reset_password:self",
                    "history:read:self"
                ],
                "level": 10
            }
        },
        "default_user_groups": ["user"]
    }
    with open(AUTH_FILE, "w", encoding="utf-8") as f:
        json.dump(initial_auth_data, f, ensure_ascii=False, indent=2)

# 新增一个用于从 AUTH_FILE 读取 groups 的全局变量
AUTH_CONFIG = {}
def load_auth_config():
    global AUTH_CONFIG
    if AUTH_FILE.exists():
        with open(AUTH_FILE, "r", encoding="utf-8") as f:
            AUTH_CONFIG = json.load(f)
load_auth_config() # 服務啟動時加載

# 修改 permissions.py 以使用 AUTH_CONFIG.get("groups", {})
# 而不是直接讀取文件，會更高效和統一

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