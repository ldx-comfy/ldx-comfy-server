"""
配置管理
"""

import os
import pathlib
import json
import shutil
import secrets
import string
import hashlib
from datetime import datetime, timezone

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
AUTH_CONFIG_PATH = os.environ.get("AUTH_CONFIG_PATH")
AUTH_FILE = pathlib.Path(AUTH_CONFIG_PATH) if AUTH_CONFIG_PATH and str(AUTH_CONFIG_PATH).strip() else DATA_BASE_PATH / "auth.json"

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
    "admin:settings:manage": "管理系統設置",
    "workflow:read:*": "讀取所有工作流 (通配符)",
    "workflow:execute:*": "執行所有工作流 (通配符)",
    "user:read:self": "查看自己的用戶信息",
    "user:update:self": "更新自己的用戶信息",
    "user:reset_password:self": "重置自己的密碼",
    "history:read:self": "查看自己的執行歷史"
}

# 生成隨機密碼（大小寫字母+數字）
def _generate_random_password(length: int = 16) -> str:
    alphabet = string.ascii_letters + string.digits
    try:
        n = max(1, int(length))
    except Exception:
        n = 16
    return "".join(secrets.choice(alphabet) for _ in range(n))

# 與 auth.config.hash_password 保持一致的哈希函數（避免循環導入）
def _hash_password(password: str) -> str:
    if not password:
        return ""
    salted_password = password + "comfyui_auth_salt"
    return hashlib.sha256(salted_password.encode("utf-8")).hexdigest()

# 確保 AUTH_FILE 存在且初始化
if not AUTH_FILE.exists():
    admin_pw_env = os.environ.get("DEFAULT_ADMIN_PASSWORD")
    admin_pw = admin_pw_env if admin_pw_env and str(admin_pw_env).strip() else _generate_random_password(16)

    admin_user = {
        "username": "admin",
        "password_hash": _hash_password(admin_pw),
        "groups": ["admin"],
        "status": "active",
        "email": "admin@example.com",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "last_login": datetime.now(timezone.utc).isoformat(),
        "generation_count": 0
    }

    initial_auth_data = {
        "jwt_secret": "your-jwt-secret-here-change-in-production",
        "jwt_expires_seconds": 3600,
        "users": [admin_user],
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
    AUTH_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(AUTH_FILE, "w", encoding="utf-8") as f:
        json.dump(initial_auth_data, f, ensure_ascii=False, indent=2)
    print(f"系統初始化時生成的默認 admin 用戶密碼: {admin_pw}")

# 新增一个用于从 AUTH_FILE 读取 groups 的全局变量
AUTH_CONFIG = {}
def load_auth_config():
    global AUTH_CONFIG
    if AUTH_FILE.exists():
        with open(AUTH_FILE, "r", encoding="utf-8") as f:
            AUTH_CONFIG = json.load(f)
load_auth_config() # 服務啟動時加載

# 確保默認 admin 存在（若無）
def ensure_default_admin():
    try:
        cfg = AUTH_CONFIG if isinstance(AUTH_CONFIG, dict) else {}
        users = cfg.get("users", [])
        if not isinstance(users, list):
            users = []
        has_admin = any(isinstance(u, dict) and u.get("username") == "admin" for u in users)
        if not has_admin:
            admin_pw_env = os.environ.get("DEFAULT_ADMIN_PASSWORD")
            admin_pw = admin_pw_env if admin_pw_env and str(admin_pw_env).strip() else _generate_random_password(16)
            admin_user = {
                "username": "admin",
                "password_hash": _hash_password(admin_pw),
                "groups": ["admin"],
                "status": "active",
                "email": "admin@example.com",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "last_login": datetime.now(timezone.utc).isoformat(),
                "generation_count": 0
            }
            users.append(admin_user)
            cfg["users"] = users
            AUTH_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(AUTH_FILE, "w", encoding="utf-8") as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
            print(f"系統初始化時生成的默認 admin 用戶密碼: {admin_pw}")
            load_auth_config()
    except Exception as e:
        print(f"警告: 自動注入默認 admin 失敗: {e}")

ensure_default_admin()

def update_admin_group_permissions():
    """更新admin組的權限，確保包含所有SYSTEM_PERMISSIONS"""
    try:
        # 重新加載配置以獲取最新狀態
        load_auth_config()
        cfg = AUTH_CONFIG if isinstance(AUTH_CONFIG, dict) else {}
        
        # 獲取當前的組配置
        groups = cfg.get("groups", {})
        if not isinstance(groups, dict):
            groups = {}
        
        # 獲取admin組配置
        admin_group = groups.get("admin", {})
        if not isinstance(admin_group, dict):
            admin_group = {}
        
        # 獲取當前的權限列表
        current_permissions = admin_group.get("permissions", [])
        if not isinstance(current_permissions, list):
            current_permissions = []
        
        # 獲取系統定義的所有權限
        system_permissions = list(SYSTEM_PERMISSIONS.keys())
        
        # 檢查是否有缺失的權限
        missing_permissions = [perm for perm in system_permissions if perm not in current_permissions]
        
        # 如果有缺失的權限，則更新
        if missing_permissions:
            print(f"發現 {len(missing_permissions)} 個缺失的權限，正在更新admin組...")
            # 合併當前權限和缺失的權限
            updated_permissions = list(set(current_permissions + missing_permissions))
            admin_group["permissions"] = updated_permissions
            groups["admin"] = admin_group
            cfg["groups"] = groups
            
            # 保存更新後的配置
            AUTH_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(AUTH_FILE, "w", encoding="utf-8") as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
            print("admin組權限更新完成")
            # 重新加載配置
            load_auth_config()
        else:
            print("admin組權限已是最新的，無需更新")
    except Exception as e:
        print(f"警告: 更新admin組權限失敗: {e}")

update_admin_group_permissions()

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
    
    def get_comfy_server_address(self):
        """獲取ComfyUI服務器地址"""
        return self.config.get("comfy_server_address", "YOUR_COMFYUI_SERVER_ADDRESS")
    
    def set_comfy_server_address(self, address):
        """設置ComfyUI服務器地址"""
        self.config["comfy_server_address"] = address
        self.save_config()

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