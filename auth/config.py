"""
Auth configuration loader and helpers.

- Loads JSON config from ENV AUTH_CONFIG_PATH or default 'auth.json' at repo root.
- Provides read-only accessors for users, codes, and JWT settings.
- JWT secret priority: ENV JWT_SECRET > config.jwt_secret > default 'change-me'
- JWT expires seconds default: 3600 (overridable via config.jwt_expires_seconds)
- Codes.expires_at accepts ISO-8601 formats with 'Z' or timezone offset; naive datetime is treated as local time.
- On missing/invalid config file: log WARNING, use empty users/codes and default JWT settings.
- RBAC extensions: groups_map/default_user_groups; users/codes may carry roles/groups
- Default admin injection: if no 'admin' user exists, inject an in-memory admin with random password
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
_DEFAULT_EXPIRES_SECONDS = 3600

_ENV_CONFIG_PATH = "AUTH_CONFIG_PATH"
_ENV_JWT_SECRET = "JWT_SECRET"
_ENV_ADMIN_CREDENTIALS_PATH = "AUTH_ADMIN_CREDENTIALS_PATH"
_ENV_PERSIST_ADMIN_TO_JSON = "AUTH_PERSIST_ADMIN_TO_JSON"

# Global configuration cache
_CONFIG: Dict[str, Any] = {}



def _effective_config_path() -> str:
    """Return the effective config path from env or default 'auth.json'."""
    return str(global_data.DATA_BASE_PATH / "auth.json")


def _load_json_file(path: str) -> Optional[Dict[str, Any]]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            logger.warning("Auth config root must be an object, got %s", type(data).__name__)
            return None
        return data
    except FileNotFoundError:
        logger.warning("Auth config not found at %s", os.path.abspath(path))
    except json.JSONDecodeError as e:
        logger.warning("Auth config JSON parse error at %s: %s", os.path.abspath(path), e)
    except Exception as e:
        logger.warning("Auth config load error at %s: %s", os.path.abspath(path), e)
    return None


def generate_random_password(length: int = 16) -> str:
    """
    Generate a cryptographically secure random password with given length
    containing [a-zA-Z0-9].
    """
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(max(1, int(length))))


def hash_password(password: str) -> str:
    """
    Hash a password using SHA256 with salt.
    Returns the hex digest of the hash.
    """
    if not password:
        return ""
    # Add a simple salt (in production, use a proper salt)
    salted_password = password + "comfyui_auth_salt"
    return hashlib.sha256(salted_password.encode('utf-8')).hexdigest()


def verify_password(password: str, hashed_password: str) -> bool:
    """
    Verify a password against its hash.
    """
    if not password or not hashed_password:
        return False
    return hash_password(password) == hashed_password


def _expand_groups_to_roles(groups: List[str]) -> List[str]:
    """Expand groups to roles using groups_map in effective config."""
    roles: List[str] = []
    data = _load_json_file(_effective_config_path())
    gm = data.get("groups_map") if data else {}
    if not isinstance(gm, dict):
        return roles
    for g in groups or []:
        if not isinstance(g, str):
            continue
        mapped = gm.get(g)
        if isinstance(mapped, list):
            for r in mapped:
                if isinstance(r, str):
                    roles.append(r)
    # dedupe while preserving order
    seen = set()
    out: List[str] = []
    for r in roles:
        if r not in seen:
            seen.add(r)
            out.append(r)
    return out


def resolve_effective_roles(subject: Dict[str, Any]) -> Tuple[List[str], List[str]]:
    """
    Resolve effective (roles, groups) for a user or a code record.

    Rules:
    - roles = explicit roles (if any) ∪ roles expanded from groups via groups_map
    - groups = explicit groups (if any); if both roles and groups are absent, fall back to default_user_groups
    """
    # explicit
    raw_roles = subject.get("roles")
    raw_groups = subject.get("groups")

    roles: List[str] = [r for r in raw_roles if isinstance(r, str)] if isinstance(raw_roles, list) else []
    groups: List[str] = [g for g in raw_groups if isinstance(g, str)] if isinstance(raw_groups, list) else []

    # fallback groups only when both explicit roles and groups are absent
    if not groups and not roles:
        dug = _CONFIG.get("default_user_groups")
        if isinstance(dug, list):
            groups = [g for g in dug if isinstance(g, str)]

    # expand groups to roles and merge
    expanded = _expand_groups_to_roles(groups)
    # merge and dedupe while preserving order (explicit roles first)
    seen = set()
    merged: List[str] = []
    for r in roles + expanded:
        if r not in seen:
            seen.add(r)
            merged.append(r)

    return merged, groups


def parse_expires_at(expires_at: str) -> Optional[int]:
    """
    Parse ISO-8601 datetime string to epoch seconds.
    - Accepts 'Z' suffix (UTC) and timezone offsets.
    - If naive (no tzinfo), treat as local time.
    Returns epoch seconds or None if parse fails.
    """
    if not isinstance(expires_at, str) or not expires_at.strip():
        return None
    s = expires_at.strip()

    # Normalize trailing 'Z' to '+00:00' for fromisoformat
    if s.endswith("Z") or s.endswith("z"):
        s = s[:-1] + "+00:00"

    try:
        dt = datetime.fromisoformat(s)
    except Exception:
        return None

    if dt.tzinfo is None:
        # Naive datetime - treat as local time
        return int(_time.mktime(dt.timetuple()))
    else:
        return int(dt.timestamp())


def is_code_expired(expires_at: str) -> bool:
    """
    Return True if the code is expired or invalid.
    """
    ts = parse_expires_at(expires_at)
    if ts is None:
        return True
    now = int(_time.time())
    return now >= ts


def _persist_admin_credentials_file(username: str, password: str, out_path: str) -> None:
    """
    Write admin credentials to out_path in JSON format and chmod 0600. Best-effort.
    """
    try:
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
    except Exception:
        # If dirname is empty or not creatable, ignore
        pass
    data = {"username": username, "password": password}
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    try:
        os.chmod(out_path, 0o600)
    except Exception:
        # Ignore chmod failures on non-POSIX filesystems
        pass


def _maybe_persist_admin_to_json(cfg_path: str, admin_user: Dict[str, Any]) -> None:
    """
    If cfg_path exists and is writable, append the admin user to users[] and atomically persist.
    Create a .bak backup first. Best-effort; swallow errors as warnings.
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
        # Backup
        bak = cfg_path + ".bak"
        try:
            shutil.copy2(cfg_path, bak)
        except Exception as e:
            logger.warning("Failed to create backup %s: %s", bak, e)
        # Atomic write via temp then replace
        tmp = cfg_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(orig, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(tmp, cfg_path)
    except Exception as e:
        logger.warning("Persist admin to auth.json failed: %s", e)


def _init_config() -> None:
    path = _effective_config_path()
    logger.info("Attempting to load auth config from: %s", path)
    data = _load_json_file(path)
    logger.info("Auth config loaded from %s: %s", path, data)
    if data is None:
        logger.warning("Auth config not found, creating default auth.json file")
        # Generate random password for admin
        admin_password = generate_random_password(16)
        
        # Create default configuration with only admin user
        default_config = {
            "jwt_secret": "your-jwt-secret-here-change-in-production",
            "jwt_expires_seconds": 3600,
            "users": [
                {
                    "username": "admin",
                    "password_hash": hash_password(admin_password),
                    "roles": ["admin"],
                    "email": "admin@example.com",
                    "status": "active",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "last_login": datetime.now(timezone.utc).isoformat(),
                    "generation_count": 0
                }
            ],
            "codes": [],
            "groups_map": {
                "admin": ["admin", "user"],
                "user": ["user"]
            },
            "default_user_groups": ["user"]
        }

        # Write default config to file
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(default_config, f, ensure_ascii=False, indent=2)
                f.write("\n")
            logger.info("Created default auth.json file at %s", path)
            logger.warning("Generated admin user with random password: %s", admin_password)
            data = default_config
        except Exception as e:
            logger.error("Failed to create default auth.json file: %s", e)
            logger.warning("Using default auth config: empty users/codes, default JWT settings")
            data = {}

    # Merge with defaults
    try:
        _CONFIG["jwt_secret"] = data.get("jwt_secret", _DEFAULT_SECRET) or _DEFAULT_SECRET
        _CONFIG["jwt_expires_seconds"] = int(data.get("jwt_expires_seconds", _DEFAULT_EXPIRES_SECONDS))
    except Exception:
        logger.warning("Invalid jwt_expires_seconds in config; using default %d", _DEFAULT_EXPIRES_SECONDS)
        _CONFIG["jwt_expires_seconds"] = _DEFAULT_EXPIRES_SECONDS

    users = data.get("users")
    codes = data.get("codes")
    _CONFIG["users"] = users if isinstance(users, list) else []
    _CONFIG["codes"] = codes if isinstance(codes, list) else []
    logger.info("Effective users list: %s", _CONFIG.get("users", []))

    if not isinstance(_CONFIG["users"], list):
        _CONFIG["users"] = []
    if not isinstance(_CONFIG["codes"], list):
        _CONFIG["codes"] = []

    # RBAC: groups_map and default_user_groups
    gm = data.get("groups_map")
    _CONFIG["groups_map"] = gm if isinstance(gm, dict) else {}

    dug = data.get("default_user_groups")
    if isinstance(dug, list):
        _CONFIG["default_user_groups"] = [g for g in dug if isinstance(g, str)]
    else:
        _CONFIG["default_user_groups"] = []

    # Default admin injection if not present
    has_admin = any(isinstance(u, dict) and u.get("username") == "admin" for u in _CONFIG["users"])
    if not has_admin:
        admin_pw = generate_random_password(16)
        admin_user: Dict[str, Any] = {"username": "admin", "password_hash": hash_password(admin_pw)}
        # Prefer groups=["admin"] if groups_map.admin exists; otherwise roles=["admin"]
        if isinstance(_CONFIG.get("groups_map"), dict) and "admin" in _CONFIG["groups_map"]:
            admin_user["groups"] = ["admin"]
        else:
            admin_user["roles"] = ["admin"]

        # Inject in-memory only by default
        _CONFIG["users"].append(admin_user)

        # WARNING log with password disclosure and guidance
        logger.warning(
            "No 'admin' user found in auth config; generated default admin with random password.\n"
            "Username: admin\nPassword: %s\n"
            "This admin exists only in memory by default. Persist it to auth.json or provide environment variables. "
            "Rotate this initial password as soon as possible.",
            admin_pw,
        )

        # Optional persistence strategies
        cred_path = os.environ.get(_ENV_ADMIN_CREDENTIALS_PATH)
        if cred_path:
            try:
                _persist_admin_credentials_file("admin", admin_pw, cred_path)
                logger.warning("Admin initial credentials written to %s with mode 0600", cred_path)
            except Exception as e:
                logger.warning("Failed to write admin credentials to %s: %s", cred_path, e)

        persist_flag = os.environ.get(_ENV_PERSIST_ADMIN_TO_JSON, "").lower() == "true"
        if persist_flag:
            try:
                _maybe_persist_admin_to_json(path, admin_user)
                logger.warning("Attempted to persist 'admin' user into auth.json if writable")
            except Exception as e:
                logger.warning("Failed to persist 'admin' user to auth.json: %s", e)




def get_users() -> List[Dict[str, Any]]:
    """Return a copy of configured users list."""
    data = _load_json_file(_effective_config_path())
    if data is None:
        return []
    users = data.get("users")
    return list(users) if isinstance(users, list) else []


def get_codes() -> List[Dict[str, Any]]:
    """Return a copy of configured codes list."""
    data = _load_json_file(_effective_config_path())
    if data is None:
        return []
    codes = data.get("codes")
    return list(codes) if isinstance(codes, list) else []


def find_user(username: str) -> Optional[Dict[str, Any]]:
    """Find a user by username."""
    if not username:
        return None
    users = get_users()
    for u in users:
        if isinstance(u, dict) and u.get("username") == username:
            return u
    return None


def get_jwt_secret() -> str:
    """Get JWT secret with priority: ENV JWT_SECRET > config > default."""
    env_secret = os.environ.get(_ENV_JWT_SECRET)
    if env_secret:
        return env_secret
    data = _load_json_file(_effective_config_path())
    if data is None:
        return _DEFAULT_SECRET
    cfg_secret = data.get("jwt_secret")
    return cfg_secret or _DEFAULT_SECRET


def get_jwt_expires_seconds() -> int:
    """Get JWT expiration in seconds (default 3600)."""
    data = _load_json_file(_effective_config_path())
    if data is None:
        return _DEFAULT_EXPIRES_SECONDS
    try:
        return int(data.get("jwt_expires_seconds", _DEFAULT_EXPIRES_SECONDS))
    except Exception:
        return _DEFAULT_EXPIRES_SECONDS


def get_effective_config_snapshot() -> Dict[str, Any]:
    """
    Return a shallow copy of the effective config (for diagnostics or tests).
    """
    return {
        "jwt_secret": _CONFIG.get("jwt_secret"),
        "jwt_expires_seconds": _CONFIG.get("jwt_expires_seconds"),
        "users": list(_CONFIG.get("users", [])),
        "codes": list(_CONFIG.get("codes", [])),
        "groups_map": dict(_CONFIG.get("groups_map", {})) if isinstance(_CONFIG.get("groups_map"), dict) else {},
        "default_user_groups": list(_CONFIG.get("default_user_groups", [])),
        "config_path": _effective_config_path(),
        "jwt_secret_from_env": bool(os.environ.get(_ENV_JWT_SECRET)),
    }


def check_user_permission(user_groups: List[str], required_permission: str) -> bool:
    """
    檢查用戶是否具有指定權限，支持通配符權限檢查。
    - user_groups: 用戶的身分組列表
    - required_permission: 需要的權限
    """
    # 讀取身分組配置
    groups_file = str(global_data.GROUPS_FILE)
    try:
        with open(groups_file, "r", encoding="utf-8") as f:
            groups_config = json.load(f)
    except:
        groups_config = {"groups": {}}
    
    # 收集用戶所有權限
    user_permissions = set()
    
    # 從身分組獲取權限
    for group_id in user_groups:
        group_data = groups_config.get("groups", {}).get(group_id, {})
        if isinstance(group_data, dict) and "permissions" in group_data:
            for perm in group_data["permissions"]:
                user_permissions.add(perm)
    
    # 檢查權限
    def _check_permission(req_perm: str) -> bool:
        # 直接匹配
        if req_perm in user_permissions:
            return True
        
        # 通配符匹配 (例如: user:*)
        if req_perm.endswith(":*"):
            prefix = req_perm[:-2]  # 移除 ":*"
            for perm in user_permissions:
                if perm.startswith(prefix + ":"):
                    return True
        
        return False
    
    return _check_permission(required_permission)


def _save_auth_config(config: Dict[str, Any]) -> None:
    """保存认证配置"""
    path = _effective_config_path()
    try:
        # 创建备份
        if os.path.exists(path):
            backup_path = path + ".bak"
            import shutil
            shutil.copy2(path, backup_path)

        # 保存新配置
        with open(path, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"保存认证配置失败: {e}")
        raise Exception(f"保存认证配置失败: {str(e)}")