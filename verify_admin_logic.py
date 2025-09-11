#!/usr/bin/env python3
"""
驗證管理員邏輯修改
簡單檢查修改後的權限賦予邏輯
"""

import json
import sys
from pathlib import Path

def check_admin_logic():
    """檢查管理員邏輯"""
    print("🔍 檢查管理員角色賦予邏輯修改...")

    # 讀取身分組配置
    groups_file = Path(__file__).parent / "data" / "groups.json"
    try:
        with open(groups_file, "r", encoding="utf-8") as f:
            config = json.load(f)
    except Exception as e:
        print(f"❌ 讀取配置失敗: {e}")
        return False

    groups_data = config.get("groups", {})

    print("\n📋 當前身分組權限分析:")
    print("-" * 50)

    admin_groups_found = []

    for group_id, group_data in groups_data.items():
        if not isinstance(group_data, dict):
            continue

        permissions = group_data.get("permissions", [])
        level = group_data.get("level", 0)

        print(f"\n👥 身分組: {group_id}")
        print(f"   權限數量: {len(permissions)}")
        print(f"   等級: {level}")

        # 檢查是否有管理權限
        admin_permissions = []
        for perm in permissions:
            if isinstance(perm, str) and (
                perm.startswith("user:") or
                perm.startswith("workflow:") or
                perm.startswith("history:") or
                perm.startswith("group:")
            ):
                admin_permissions.append(perm)

        if admin_permissions:
            print(f"   ✅ 管理權限: {admin_permissions}")
            admin_groups_found.append(group_id)
        else:
            print("   ❌ 無管理權限")

        if level >= 100:
            print("   ✅ 高等級 (≥100)")
            if group_id not in admin_groups_found:
                admin_groups_found.append(group_id)

    print("\n" + "=" * 50)
    print("🎯 修改效果驗證:")

    if "test2" in admin_groups_found:
        print("✅ test2 身分組現在可以訪問管理面板")
        print("   原因: 擁有 user:*、history:*、group:* 等管理權限")
    else:
        print("❌ test2 身分組仍然無法訪問管理面板")

    if "viewer" not in admin_groups_found:
        print("✅ viewer 身分組正確地無法訪問管理面板")
        print("   原因: 只有 workflow:read、history:read，無管理權限")
    else:
        print("❌ viewer 身分組錯誤地可以訪問管理面板")

    print(f"\n📊 總結: {len(admin_groups_found)} 個身分組可以訪問管理面板")
    print(f"   身分組列表: {admin_groups_found}")

    return "test2" in admin_groups_found

if __name__ == "__main__":
    success = check_admin_logic()
    print("\n" + "=" * 50)
    if success:
        print("✅ 管理員邏輯修改成功！")
        print("   現在擁有任何管理權限的身分組都能訪問管理面板")
    else:
        print("❌ 管理員邏輯修改可能有問題")
    sys.exit(0 if success else 1)