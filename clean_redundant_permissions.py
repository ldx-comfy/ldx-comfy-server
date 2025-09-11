#!/usr/bin/env python3
"""
清理冗餘權限腳本
移除同時存在通配符權限和具體權限的情況
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

def save_groups_config(config):
    """保存身分組配置"""
    groups_file = Path(__file__).parent / "data" / "groups.json"
    try:
        with open(groups_file, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        print(f"✅ 配置已保存到 {groups_file}")
    except Exception as e:
        print(f"❌ 保存配置失敗: {e}")
        sys.exit(1)

def find_redundant_permissions(permissions):
    """查找冗餘權限"""
    redundant = []
    cleaned_permissions = set(permissions)

    for perm in permissions:
        if not perm.endswith(":*"):
            # 檢查是否有對應的通配符權限
            wildcard_perm = perm.rsplit(":", 1)[0] + ":*"
            if wildcard_perm in permissions:
                redundant.append((wildcard_perm, perm))
                cleaned_permissions.discard(perm)  # 移除具體權限，保留通配符

    return list(cleaned_permissions), redundant

def clean_redundant_permissions():
    """清理所有身分組的冗餘權限"""
    config = load_groups_config()
    groups_config = config.get("groups", {})

    print("🧹 開始清理冗餘權限...")
    print()

    total_cleaned = 0
    groups_modified = []

    for group_id, group_data in groups_config.items():
        if not isinstance(group_data, dict):
            continue

        permissions = group_data.get("permissions", [])
        if not permissions:
            continue

        cleaned_permissions, redundant = find_redundant_permissions(permissions)

        if redundant:
            print(f"🔧 清理身分組: {group_id} ({group_data.get('name', group_id)})")
            print(f"   原始權限數量: {len(permissions)}")
            print(f"   清理後權限數量: {len(cleaned_permissions)}")
            print(f"   移除的冗餘權限: {redundant}")
            print()

            # 更新權限列表
            group_data["permissions"] = cleaned_permissions
            groups_modified.append(group_id)
            total_cleaned += len(redundant)

    if groups_modified:
        print("💾 保存修改...")
        save_groups_config(config)
        print()
        print("📊 清理總結:")
        print(f"   修改的身分組: {len(groups_modified)}")
        print(f"   移除的冗餘權限: {total_cleaned}")
        print("✅ 冗餘權限清理完成！")
    else:
        print("✅ 沒有發現冗餘權限，無需清理。")

    return len(groups_modified) > 0

if __name__ == "__main__":
    modified = clean_redundant_permissions()
    sys.exit(0 if not modified else 1)  # 如果有修改，返回1表示需要注意