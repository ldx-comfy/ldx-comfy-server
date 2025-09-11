#!/usr/bin/env python3
"""
調試腳本：驗證 auth/config.py 中的 _CONFIG 和 global_data.AUTH_CONFIG 的內容
"""

import sys
import os

# 添加當前目錄到 Python 路徑
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import global_data
    from auth import config as auth_config
    print("模塊導入成功")
except Exception as e:
    print(f"模塊導入失敗: {e}")
    sys.exit(1)

def debug_auth_config():
    try:
        print("=== 調試 auth/config.py 中的 _CONFIG 和 global_data.AUTH_CONFIG ===")
        
        # 檢查 global_data.AUTH_CONFIG
        print("\n1. global_data.AUTH_CONFIG:")
        print(f"   類型: {type(global_data.AUTH_CONFIG)}")
        print(f"   是否為空: {not global_data.AUTH_CONFIG}")
        if global_data.AUTH_CONFIG:
            print(f"   用戶數量: {len(global_data.AUTH_CONFIG.get('users', []))}")
            print(f"   組數量: {len(global_data.AUTH_CONFIG.get('groups', {}))}")
            if global_data.AUTH_CONFIG.get('users'):
                print("   用戶列表:")
                for user in global_data.AUTH_CONFIG['users']:
                    if isinstance(user, dict):
                        print(f"     - {user.get('username', 'N/A')} (組: {user.get('groups', [])})")
            if global_data.AUTH_CONFIG.get('groups'):
                print("   組列表:")
                for group_id, group_data in global_data.AUTH_CONFIG['groups'].items():
                    if isinstance(group_data, dict):
                        print(f"     - {group_id}: {len(group_data.get('permissions', []))} 個權限")
        else:
            print("   global_data.AUTH_CONFIG 為空")
        
        # 檢查 auth_config._CONFIG
        print("\n2. auth_config._CONFIG:")
        print(f"   類型: {type(auth_config._CONFIG)}")
        print(f"   是否為空: {not auth_config._CONFIG}")
        if auth_config._CONFIG:
            print(f"   用戶數量: {len(auth_config._CONFIG.get('users', []))}")
            print(f"   組數量: {len(auth_config._CONFIG.get('groups', {}))}")
            if auth_config._CONFIG.get('users'):
                print("   用戶列表:")
                for user in auth_config._CONFIG['users']:
                    if isinstance(user, dict):
                        print(f"     - {user.get('username', 'N/A')} (組: {user.get('groups', [])})")
            if auth_config._CONFIG.get('groups'):
                print("   組列表:")
                for group_id, group_data in auth_config._CONFIG['groups'].items():
                    if isinstance(group_data, dict):
                        print(f"     - {group_id}: {len(group_data.get('permissions', []))} 個權限")
        else:
            print("   auth_config._CONFIG 為空")
        
        # 檢查是否指向同一個對象
        print(f"\n3. 是否指向同一個對象: {auth_config._CONFIG is global_data.AUTH_CONFIG}")
        
        # 檢查特定用戶 (ldx) 的權限
        print("\n4. 用戶 'ldx' 的權限檢查:")
        if global_data.AUTH_CONFIG and global_data.AUTH_CONFIG.get('users'):
            ldx_user = None
            for user in global_data.AUTH_CONFIG['users']:
                if isinstance(user, dict) and user.get('username') == 'ldx':
                    ldx_user = user
                    break
            
            if ldx_user:
                print(f"   用戶 'ldx' 存在: {ldx_user}")
                groups = ldx_user.get('groups', [])
                print(f"   用戶 'ldx' 的組: {groups}")
                
                # 使用 auth_config.resolve_effective_roles 解析權限
                try:
                    effective_roles, effective_groups, resolved_permissions = auth_config.resolve_effective_roles(ldx_user)
                    print(f"   解析後的角色: {effective_roles}")
                    print(f"   解析後的組: {effective_groups}")
                    print(f"   解析後的權限數量: {len(resolved_permissions)}")
                    print(f"   解析後的權限: {resolved_permissions}")
                except Exception as e:
                    print(f"   解析權限時出錯: {e}")
                    import traceback
                    traceback.print_exc()
            else:
                print("   用戶 'ldx' 不存在")
        else:
            print("   global_data.AUTH_CONFIG 為空或沒有用戶")
            
    except Exception as e:
        print(f"調試過程中出現錯誤: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_auth_config()