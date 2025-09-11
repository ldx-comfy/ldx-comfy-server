#!/usr/bin/env python3
"""
測試當前管理員邏輯
檢查修改是否生效
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from auth.config import _get_admin_groups

def test_current_logic():
    """測試當前邏輯"""
    print("🔍 測試當前管理員角色賦予邏輯...")

    # 模擬 test2 身分組
    test_groups = ["test2"]

    print(f"測試身分組: {test_groups}")

    try:
        admin_groups = _get_admin_groups(test_groups)
        print(f"獲得 admin 角色的身分組: {admin_groups}")

        if "test2" in admin_groups:
            print("✅ test2 身分組獲得了 admin 角色")
            return True
        else:
            print("❌ test2 身分組沒有獲得 admin 角色")
            return False

    except Exception as e:
        print(f"❌ 測試失敗: {e}")
        return False

if __name__ == "__main__":
    success = test_current_logic()
    print("\n" + "="*50)
    if success:
        print("✅ 邏輯修改已生效！")
    else:
        print("❌ 邏輯修改未生效，可能需要重啟服務器")
    sys.exit(0 if success else 1)