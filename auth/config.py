"""
Auth configuration loader and helpers.

- Loads JSON config from ENV AUTH_CONFIG_PATH or default 'auth.json' at repo root.
- Provides read-only accessors for users, codes, and JWT settings.
- JWT secret priority: ENV JWT_SECRET > config.jwt_secret > default 'change-me'
- JWT expires seconds default: 3600 (overridable via config.jwt_expires_seconds)
- Codes.expires_at accepts ISO-8601 formats with 'Z' or timezone offset; naive datetime is treated as local time.
- On missing/invalid config file: log WARNING, use empty users/codes and default JWT settings.
- RBAC extensions: groups_map/default_user_groups; users/codes may carry roles/groups
"""

from __future__ import annotations

import json
import logging
import os
import time as _time
import secrets
import string
import shutil
import hashlib
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
import global_data
logger = logging.getLogger(__name__)

_DEFAULT_SECRET = "change-me"
_DEFAULT_EXPIRES_SECONDS = 604800 # 7 days in seconds for temporary validity

_ENV_JWT_SECRET = "JWT_SECRET"
_ENV_ADMIN_CREDENTIALS_PATH = "AUTH_ADMIN_CREDENTIALS_PATH"
_ENV_PERSIST_ADMIN_TO_JSON = "AUTH_PERSIST_ADMIN_TO_JSON"

# _CONFIG 現在直接指向 global_data.AUTH_CONFIG，是整個應用程序的唯一認證配置源。
_CONFIG = global_data.AUTH_CONFIG


def _effective_config_path() -> str:
    """返回有效的配置路徑，優先 ENV AUTH_CONFIG_PATH，其次 global_data.AUTH_FILE。"""
    env_path = os.environ.get("AUTH_CONFIG_PATH")
    if env_path and str(env_path).strip():
        return str(env_path)
    return str(global_data.AUTH_FILE)


def generate_random_password(length: int = 16) -> str:
    """
    生成一個指定長度的隨機密碼，包含大小寫字母和數字。
    """
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(max(1, int(length))))


def hash_password(password: str) -> str:
    """
    使用 SHA256 和鹽值哈希密碼。
    返回哈希值的十六進制字符串。
    """
    if not password:
        return ""
    # 在生產環境中，應使用更強的鹽值和密碼哈希算法 (例如 bcrypt, scrypt)
    salted_password = password + "comfyui_auth_salt"
    return hashlib.sha256(salted_password.encode('utf-8')).hexdigest()


def verify_password(password: str, hashed_password: str) -> bool:
    """
    驗證密碼是否與給定的哈希值匹配。
    """
    if not password or not hashed_password:
        return False
    return hash_password(password) == hashed_password


def _expand_groups_to_roles(groups: List[str]) -> List[str]:
    """擴展身分組到角色 (目前簡化為不擴展，所有權限都在身分組中直接定義)。"""
    # 在新的模型中，直接從 group 的 permissions 獲取，不再使用 groups_map 進行角色映射
    # 因為現在權限已經是細粒度定義
    return [] # 由於簡化權限系統，roles 將從 groups 中的 permissions 內解析


def _get_admin_groups(user_groups: List[str]) -> List[str]:
    """
    根據用戶所屬的身分組，判斷哪些身分組應被視為 admin。
    如果身分組 (直接或間接) 包含 "admin:access" 或其他 admin-level 權限，
    或者其 level 屬性達到或超過 100，則該身分組被視為 admin。
    """
    admin_groups: List[str] = []
    
    # 從全局配置中獲取身分組數據
    groups_config = _CONFIG.get("groups", {})

    # 管理員級別權限模式，用於判斷身分組是否為管理員性質
    admin_permission_patterns = [
        "admin:", # 匹配所有 admin: 開頭的權限
    ]

    for group_id in user_groups:
        if not isinstance(group_id, str):
            continue

        group_data = groups_config.get(group_id, {})
        if isinstance(group_data, dict):
            permissions = group_data.get("permissions", [])
            has_admin_level_permissions = False

            for perm in permissions:
                if isinstance(perm, str):
                    for pattern in admin_permission_patterns:
                        if pattern.endswith(":") and perm.startswith(pattern):
                            has_admin_level_permissions = True
                            break
                        elif pattern.endswith(":*") and perm.startswith(pattern[:-1]):
                            has_admin_level_permissions = True
                            break
                        elif perm == pattern:
                            has_admin_level_permissions = True
                            break
                    if has_admin_level_permissions:
                        break
            
            if has_admin_level_permissions:
                admin_groups.append(group_id)
                continue

            # 兼容舊的 level >= 100 判斷
            level = group_data.get("level", 0)
            if level >= 100:
                admin_groups.append(group_id)

    return admin_groups


def resolve_effective_roles(subject: Dict[str, Any]) -> Tuple[List[str], List[str], List[str]]: # 修改返回類型
    """
    為用戶或授權碼記錄解析有效的 (角色, 身分組)。
    規則:
    - roles = 顯式角色 (如果有) ∪ 從身分組中解析出的角色 (例如，如果身分組具有 admin 權限，則獲得 "admin" 角色)
    - groups = 顯式身分組 (如果有)；如果角色和身分組都缺失，則回退到 default_user_groups
    - 動態 admin 角色分配: 具有 admin-level 權限的身分組自動獲得 admin 角色
    """
    logger.debug(f"resolve_effective_roles: 收到 subject={subject}")

    raw_roles = subject.get("roles")
    raw_groups = subject.get("groups")

    roles: List[str] = [r for r in raw_roles if isinstance(r, str)] if isinstance(raw_roles, list) else []
    groups: List[str] = [g for g in raw_groups if isinstance(g, str)] if isinstance(raw_groups, list) else []

    if not groups and not roles:
        dug = _CONFIG.get("default_user_groups")
        if isinstance(dug, list):
            groups = [g for g in dug if isinstance(g, str)]
    
    logger.debug(f"resolve_effective_roles: 初始 roles={roles}, groups={groups}")

    # Dynamic admin role assignment for high-level groups
    admin_groups = _get_admin_groups(groups)
    if admin_groups and "admin" not in roles: # 如果有 admin-level 的身分組，確保 "admin" 角色存在
        roles.append("admin")
    
    logger.debug(f"resolve_effective_roles: 處理 admin_groups 後 roles={roles}")

    # 因為目前 _expand_groups_to_roles 簡化為不返回角色，所以直接使用當前 roles
    merged_roles: List[str] = []
    seen = set()
    for r in roles: # 只處理顯式角色和動態添加的 "admin" 角色
        if r not in seen:
            seen.add(r)
            merged_roles.append(r)
    
    logger.debug(f"resolve_effective_roles: 合併後 merged_roles={merged_roles}")

    # 收集所有細粒度權限
    all_permissions = set()
    groups_config = _CONFIG.get("groups", {})
    for group_id in groups:
        group_data = groups_config.get(group_id, {})
        if isinstance(group_data, dict) and "permissions" in group_data:
            for perm in group_data["permissions"]:
                all_permissions.add(perm)
    
    # 動態添加 admin:access 權限，如果用戶最終具有 "admin" 角色
    # 注意: 這裡已經在 _get_admin_groups 中邏輯性地觸發了 "admin" 角色，
    # 而 "admin" 身分組的 permissions 中已經直接包含了 "admin:access"。
    # 這行應該是保證 admin 角色在 JWT 中也能直觀表達為一個權限。
    if "admin" in merged_roles:
        all_permissions.add("admin:access")
    
    logger.debug(f"resolve_effective_roles: 最終 all_permissions={list(all_permissions)}")

    return merged_roles, groups, list(all_permissions) # 返回包含 permissions 的三元組


def parse_expires_at(expires_at: str) -> Optional[int]:
    """
    將 ISO-8601 日期時間字符串解析為 epoch 秒數。
    - 接受 'Z' 後綴 (UTC) 和時區偏移。
    - 如果是 Naive (沒有時區信息)，則視為本地時間。
    返回 epoch 秒數，如果解析失敗則返回 None。
    """
    if not isinstance(expires_at, str) or not expires_at.strip():
        return None
    s = expires_at.strip()

    # 將尾隨的 'Z' 規範化為 '+00:00' 以便 fromisoformat 處理
    if s.lower().endswith("z"):
        s = s[:-1] + "+00:00"

    try:
        dt = datetime.fromisoformat(s)
    except Exception:
        return None

    if dt.tzinfo is None:
        # Naive datetime - 視為本地時間
        return int(_time.mktime(dt.timetuple()))
    else:
        return int(dt.timestamp())


def is_code_expired(expires_at: str) -> bool:
    """
    如果授權碼已過期或無效，則返回 True。
    """
    ts = parse_expires_at(expires_at)
    if ts is None:
        return True
    now = int(_time.time())
    return now >= ts


def _persist_admin_credentials_file(username: str, password: str, out_path: str) -> None:
    """
    將管理員憑據以 JSON 格式寫入 out_path，並設置文件權限為 0600。盡力而為。
    """
    try:
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
    except Exception:
        # 如果目錄名為空或無法創建，則忽略
        pass
    data = {"username": username, "password": password}
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=True, indent=2) # 確保 ASCII，因為這是配置文件
        f.write("\n")
    try:
        os.chmod(out_path, 0o600)
    except Exception:
        # 在非 POSIX 文件系統上忽略 chmod 失敗
        pass


def _maybe_persist_admin_to_json(cfg_path: str, admin_user: Dict[str, Any]) -> None:
    """
    如果 cfg_path 存在且可寫，將管理員用戶添加到 users[] 中並原子地持久化。
    首先創建 .bak 備份。盡力而為；將錯誤記錄為警告。
    """
    if not cfg_path:
        return
    if not os.path.isfile(cfg_path) or not os.access(cfg_path, os.W_OK):
        return
    try:
        with open(cfg_path, "r", encoding="utf-8") as f:
            orig = json.load(f)
        if not isinstance(orig, dict):
            return
        users = orig.get("users")
        if isinstance(users, list):
            if any(isinstance(u, dict) and u.get("username") == "admin" for u in users):
                return
        else:
            users = []
        users.append(admin_user)
        orig["users"] = users
        # 備份
        bak = cfg_path + ".bak"
        try:
            shutil.copy2(cfg_path, bak)
        except Exception as e:
            logger.warning("Failed to create backup %s: %s", bak, e)
        # 通過臨時文件進行原子寫入，然後替換
        tmp = cfg_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(orig, f, ensure_ascii=True, indent=2)
            f.write("\n")
        os.replace(tmp, cfg_path)
    except Exception as e:
        logger.warning("Persist admin to auth.json failed: %s", e)


def _init_config() -> None:
    """
    初始化配置：以 global_data.AUTH_CONFIG 為單一來源，不再在此處創建/持久化默認 auth.json。
    僅做環境變量覆蓋與結構/類型規整。
    """
    global _CONFIG
    # 將 _CONFIG 指向最新的全局配置（若不可用則為空字典）
    _CONFIG = global_data.AUTH_CONFIG if isinstance(global_data.AUTH_CONFIG, dict) else {}

    # 環境變量覆蓋
    _CONFIG["jwt_secret"] = os.environ.get(_ENV_JWT_SECRET) or _CONFIG.get("jwt_secret", _DEFAULT_SECRET) or _DEFAULT_SECRET
    try:
        _CONFIG["jwt_expires_seconds"] = int(_CONFIG.get("jwt_expires_seconds", _DEFAULT_EXPIRES_SECONDS))
    except Exception:
        logger.warning("Invalid jwt_expires_seconds in config; using default %d", _DEFAULT_EXPIRES_SECONDS)
        _CONFIG["jwt_expires_seconds"] = _DEFAULT_EXPIRES_SECONDS

    # 類型規整
    if not isinstance(_CONFIG.get("users"), list):
        _CONFIG["users"] = []
    if not isinstance(_CONFIG.get("codes"), list):
        _CONFIG["codes"] = []
    if not isinstance(_CONFIG.get("groups"), dict):
        _CONFIG["groups"] = {}
    if not isinstance(_CONFIG.get("default_user_groups"), list):
        _CONFIG["default_user_groups"] = []

    logger.debug(
        "Auth config loaded from global_data. users=%d, codes=%d, groups=%d",
        len(_CONFIG["users"]),
        len(_CONFIG["codes"]),
        len(_CONFIG["groups"]),
    )


def get_users() -> List[Dict[str, Any]]:
    """返回已配置用戶列表的副本。"""
    # 直接從 global_data.AUTH_CONFIG 獲取最新的用戶列表
    users = global_data.AUTH_CONFIG.get("users", [])
    return list(users) if isinstance(users, list) else []


def get_codes() -> List[Dict[str, Any]]:
    """返回已配置授權碼列表的副本。"""
    return list(_CONFIG.get("codes", []))


def find_user(username: str) -> Optional[Dict[str, Any]]:
    """通過用戶名查找用戶。"""
    if not username:
        return None
    # 直接從 global_data.AUTH_CONFIG 獲取最新的用戶列表
    users = global_data.AUTH_CONFIG.get("users", [])
    if not isinstance(users, list):
        users = []
    for u in users:
        if isinstance(u, dict) and u.get("username") == username:
            return u
    return None


def get_jwt_secret() -> str:
    """獲取 JWT 密鑰，優先級：ENV JWT_SECRET > config > 默認。"""
    env_secret = os.environ.get(_ENV_JWT_SECRET)
    if env_secret:
        return env_secret
    return _CONFIG.get("jwt_secret", _DEFAULT_SECRET) or _DEFAULT_SECRET


def get_jwt_expires_seconds() -> int:
    """獲取 JWT 到期時間 (秒，默認為 3600)。"""
    return _CONFIG.get("jwt_expires_seconds", _DEFAULT_EXPIRES_SECONDS)


def get_effective_config_snapshot() -> Dict[str, Any]:
    """
    返回有效配置的淺拷貝 (用於診斷或測試)。
    """
    # 創建一個新的字典來避免直接修改 _CONFIG
    snapshot = {k: v for k, v in _CONFIG.items() if k not in ["users", "codes"]} # 避免過多敏感數據
    snapshot["users"] = [{"username": u["username"], "id": u.get("id")} for u in _CONFIG.get("users", []) if isinstance(u, dict)] # 僅返回部分用戶信息
    snapshot["codes"] = [{"code": c["code"], "expires_at": c.get("expires_at")} for c in _CONFIG.get("codes", []) if isinstance(c, dict)] # 僅返回部分授權碼信息
    snapshot["config_path"] = _effective_config_path()
    snapshot["jwt_secret_from_env"] = bool(os.environ.get(_ENV_JWT_SECRET))
    return snapshot


def check_user_permission(user_groups: List[str], required_permission: str) -> bool:
    """
    檢查用戶是否具有指定權限，支持通配符權限檢查。
    - user_groups: 用戶的身分組列表
    - required_permission: 需要的權限
    """
    # 從全局配置中獲取身分組數據
    groups_config = _CONFIG.get("groups", {})
    
    # 收集用戶所有權限
    user_permissions = set()
    
    # 從身分組獲取權限
    for group_id in user_groups:
        group_data = groups_config.get(group_id, {})
        if isinstance(group_data, dict) and "permissions" in group_data:
            for perm in group_data["permissions"]:
                user_permissions.add(perm)
    
    # 檢查權限
    def _check_permission(req_perm: str) -> bool:
        if req_perm in user_permissions:
            return True
        
        if req_perm.endswith(":*"):
            prefix = req_perm[:-2]
            for perm in user_permissions:
                if perm.startswith(prefix + ":") and len(perm) > len(prefix) + 1:
                    return True
        
        return False
    
    return _check_permission(required_permission)


def _save_auth_config(config: Dict[str, Any]) -> None:
    """保存認證配置"""
    global _CONFIG
    path = _effective_config_path()
    try:
        # 創建備份
        if os.path.exists(path):
            backup_path = path + ".bak"
            import shutil
            shutil.copy2(path, backup_path)
            logger.debug(f"_save_auth_config: 創建備份文件: {backup_path}")

        # 讀取現有配置
        existing_config = {}
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    existing_config = json.load(f)
            except Exception as e:
                logger.warning(f"_save_auth_config: 讀取現有配置失敗: {e}")

        # 合併配置：保留現有配置中重要的字段（如 users, codes），除非新配置明確提供了這些字段
        merged_config = existing_config.copy()
        merged_config.update(config)

        # 特別處理 users 和 codes 字段
        if "users" not in config and "users" in existing_config:
            merged_config["users"] = existing_config["users"]
        if "codes" not in config and "codes" in existing_config:
            merged_config["codes"] = existing_config["codes"]

        with open(path, "w", encoding="utf-8") as f:
            json.dump(merged_config, f, ensure_ascii=True, indent=2)
            f.write("\n")
        logger.info(f"_save_auth_config: 認證配置已保存到 {path}")
        
        # 更新 global_data 中的 AUTH_CONFIG，保持一致性，並同步本模塊快照
        global_data.load_auth_config()
        _CONFIG = global_data.AUTH_CONFIG
        logger.info(f"_save_auth_config: global_data.AUTH_CONFIG 已重新加載並同步到 auth.config._CONFIG")
        
    except Exception as e:
        logger.error(f"保存認證配置失敗: {e}")
        raise Exception(f"保存認證配置失敗: {str(e)}")


# 在模塊加載時自動初始化配置
_init_config()