#!/usr/bin/env python3
"""
測試腳本：手動生成一個 JWT token，看看它是否包含正確的權限
"""

import sys
import os

# 添加當前目錄到 Python 路徑
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import global_data
    from auth import config as auth_config
    from routers.auth import _issue_token
    print("模塊導入成功")
except Exception as e:
    print(f"模塊導入失敗: {e}")
    sys.exit(1)

def generate_test_token():
    try:
        print("=== 手動生成 JWT token ===")
        
        # 獲取用戶 'ldx' 的信息
        if global_data.AUTH_CONFIG and global_data.AUTH_CONFIG.get('users'):
            ldx_user = None
            for user in global_data.AUTH_CONFIG['users']:
                if isinstance(user, dict) and user.get('username') == 'ldx':
                    ldx_user = user
                    break
            
            if ldx_user:
                print(f"用戶 'ldx' 存在: {ldx_user}")
                groups = ldx_user.get('groups', [])
                print(f"用戶 'ldx' 的組: {groups}")
                
                # 使用 _issue_token 生成 JWT token
                try:
                    token_response = _issue_token(
                        subject="ldx", 
                        login_mode="password", 
                        roles=ldx_user.get("roles", []), 
                        groups=ldx_user.get("groups", [])
                    )
                    print(f"生成的 JWT token: {token_response.access_token}")
                    print(f"Token 類型: {token_response.token_type}")
                    print(f"過期時間: {token_response.expires_in}")
                    
                    # 解析 JWT token 並檢查權限
                    secret = auth_config.get_jwt_secret()
                    from auth import jwt as jwt_lib
                    payload = jwt_lib.decode(token_response.access_token, secret)
                    print(f"解析後的 payload: {payload}")
                    print(f"Payload 中的權限: {payload.get('permissions', [])}")
                    
                except Exception as e:
                    print(f"生成 JWT token 時出錯: {e}")
                    import traceback
                    traceback.print_exc()
            else:
                print("用戶 'ldx' 不存在")
        else:
            print("global_data.AUTH_CONFIG 為空或沒有用戶")
            
    except Exception as e:
        print(f"測試過程中出現錯誤: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    generate_test_token()