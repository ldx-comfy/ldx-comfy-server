#!/usr/bin/env python3
"""
測試管理員角色賦予邏輯
驗證修改後的權限系統是否正常工作
"""

import json
import sys
from pathlib import Path

# 添加當前目錄到路徑，以便導入模組
sys.path.insert(0, str(Path(__file__).parent))

from auth.config import _get_admin_groups

def test_admin_role_assignment():
    """測試管理員角色賦予邏輯"""
    print("🧪 測試管理員角色賦予邏輯...")
    print()

    # 模擬不同的身分組配置
    test_cases = [
        {
            "name": "admin 身分組（擁有所有權限）",
            "groups": ["admin"],
            "expected_admin": True,
            "description": "應該獲得 admin 角色"
        },
        {
            "name": "test 身分組（level = 100）",
            "groups": ["test"],
            "expected_admin": True,
            "description": "應該獲得 admin 角色"
        },
        {
            "name": "test2 身分組（擁有部分管理權限）",
            "groups": ["test2"],
            "expected_admin": True,
            "description": "現在應該獲得 admin 角色（修改後的邏輯）"
        },
        {
            "name": "editor 身分組（只有工作流權限）",
            "groups": ["editor"],
            "expected_admin": True,
            "description": "應該獲得 admin 角色"
        },
        {
            "name": "viewer 身分組（只有查看權限）",
            "groups": ["viewer"],
            "expected_admin": False,
            "description": "不應該獲得 admin 角色"
        },
        {
            "name": "混合身分組（admin + viewer）",
            "groups": ["admin", "viewer"],
            "expected_admin": True,
            "description": "應該獲得 admin 角色"
        },
        {
            "name": "空身分組",
            "groups": [],
            "expected_admin": False,
            "description": "不應該獲得 admin 角色"
        }
    ]

    print("📋 測試案例:")
    for i, case in enumerate(test_cases, 1):
        print(f"   {i}. {case['name']}: {case['description']}")
    print()

    all_passed = True

    for case in test_cases:
        print(f"🔍 測試: {case['name']}")

        try:
            admin_groups = _get_admin_groups(case['groups'])
            has_admin_role = len(admin_groups) > 0

            if has_admin_role == case['expected_admin']:
                print(f"   ✅ 通過 - 預期: {case['expected_admin']}, 實際: {has_admin_role}")
                if admin_groups:
                    print(f"      獲得 admin 角色的身分組: {admin_groups}")
            else:
                print(f"   ❌ 失敗 - 預期: {case['expected_admin']}, 實際: {has_admin_role}")
                if admin_groups:
                    print(f"      獲得 admin 角色的身分組: {admin_groups}")
                all_passed = False

        except Exception as e:
            print(f"   ❌ 錯誤: {e}")
            all_passed = False

        print()

    print("📊 測試總結:")
    if all_passed:
        print("✅ 所有測試通過！管理員角色賦予邏輯工作正常。")
        print()
        print("🎯 修改效果:")
        print("   - 擁有任何管理權限的身分組都能訪問管理面板")
        print("   - 移除了對完整權限集合的要求")
        print("   - 保持了 level >= 100 的向後兼容性")
    else:
        print("❌ 部分測試失敗，需要檢查邏輯。")

    return all_passed

if __name__ == "__main__":
    success = test_admin_role_assignment()
    sys.exit(0 if success else 1)