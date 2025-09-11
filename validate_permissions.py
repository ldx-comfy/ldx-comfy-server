#!/usr/bin/env python3
"""
權限驗證腳本
檢查所有身分組的權限是否有效
"""

import json
import sys
from pathlib import Path

def load_groups_config():
    """加載身分組配置"""
    groups_file = Path(__file__).parent / "data" / "groups.json"
    try:
        with open(groups_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ 加載身分組配置失敗: {e}")
        sys.exit(1)

def is_valid_permission(permission: str, system_permissions: dict) -> bool:
    """驗證權限是否有效，支持通配符權限"""
    # 直接匹配
    if permission in system_permissions:
        return True

    # 通配符匹配 (例如: user:*)
    if permission.endswith(":*"):
        prefix = permission[:-2]  # 移除 ":*"
        for perm_id in system_permissions.keys():
            if perm_id.startswith(prefix + ":"):
                return True

    return False

def validate_all_permissions():
    """驗證所有身分組的權限"""
    config = load_groups_config()
    system_permissions = config.get("system_permissions", {})
    groups_config = config.get("groups", {})

    print("🔍 開始驗證身分組權限...")
    print(f"📋 系統權限總數: {len(system_permissions)}")
    print(f"👥 身分組總數: {len(groups_config)}")
    print()

    all_valid = True
    total_permissions_checked = 0

    for group_id, group_data in groups_config.items():
        if not isinstance(group_data, dict):
            print(f"⚠️  身分組 {group_id} 數據格式錯誤")
            continue

        permissions = group_data.get("permissions", [])
        total_permissions_checked += len(permissions)

        print(f"🔍 檢查身分組: {group_id} ({group_data.get('name', group_id)})")
        print(f"   權限數量: {len(permissions)}")

        invalid_permissions = []
        redundant_permissions = []

        # 檢查每個權限
        for perm in permissions:
            if not is_valid_permission(perm, system_permissions):
                invalid_permissions.append(perm)
            else:
                # 檢查是否有冗餘權限（同時有通配符和具體權限）
                if not perm.endswith(":*"):
                    wildcard_perm = perm.rsplit(":", 1)[0] + ":*"
                    if wildcard_perm in permissions:
                        redundant_permissions.append((wildcard_perm, perm))

        if invalid_permissions:
            print(f"   ❌ 無效權限: {invalid_permissions}")
            all_valid = False
        else:
            print("   ✅ 所有權限有效")

        if redundant_permissions:
            print(f"   ⚠️  冗餘權限: {redundant_permissions}")

        print()

    print("📊 驗證總結:")
    print(f"   總權限數量: {total_permissions_checked}")
    print(f"   身分組數量: {len(groups_config)}")

    if all_valid:
        print("✅ 所有身分組權限驗證通過！")
        return True
    else:
        print("❌ 發現無效權限，需要修復！")
        return False

if __name__ == "__main__":
    success = validate_all_permissions()
    sys.exit(0 if success else 1)