#!/usr/bin/env python3
"""
測試用戶創建功能
"""

import json
import requests
import global_data

# 服務器地址
BASE_URL = "http://localhost:1145"

def load_auth_config():
    """加載認證配置"""
    global_data.load_auth_config()
    return global_data.AUTH_CONFIG

def get_admin_token():
    """獲取管理員令牌"""
    # 首先加載配置以獲取admin用戶的密碼
    config = load_auth_config()
    admin_user = None
    for user in config.get("users", []):
        if isinstance(user, dict) and user.get("username") == "admin":
            admin_user = user
            break
    
    if not admin_user:
        print("❌ 未找到admin用戶")
        return None
    
    # 使用admin用戶登錄
    login_data = {
        "username": "admin",
        "password": "ldx123456"  # 這是預設密碼，根據實際情況修改
    }
    
    try:
        response = requests.post(f"{BASE_URL}/api/v1/auth/login", json=login_data)
        if response.status_code == 200:
            token_data = response.json()
            return token_data.get("access_token")
        else:
            print(f"❌ 登錄失敗: {response.status_code} {response.text}")
            return None
    except Exception as e:
        print(f"❌ 登錄請求失敗: {e}")
        return None

def test_create_user(token):
    """測試創建用戶"""
    if not token:
        print("❌ 無效的令牌")
        return False
    
    headers = {
        "Authorization": f"Bearer {token}"
    }
    
    # 準備用戶數據
    user_data = {
        "username": "testuser",
        "password": "testpassword123",
        "email": "testuser@example.com",
        "groups": ["user"]  # 指定身分組
    }
    
    try:
        response = requests.post(f"{BASE_URL}/api/v1/admin/users/", json=user_data, headers=headers)
        if response.status_code == 200:
            user_info = response.json()
            print(f"✅ 用戶創建成功: {user_info}")
            
            # 驗證用戶是否真的寫入到了auth.json中
            config = load_auth_config()
            users = config.get("users", [])
            created_user = None
            for user in users:
                if isinstance(user, dict) and user.get("username") == "testuser":
                    created_user = user
                    break
            
            if created_user:
                print(f"✅ 用戶已成功寫入auth.json: {created_user}")
                return True
            else:
                print("❌ 用戶未寫入auth.json")
                return False
        else:
            print(f"❌ 用戶創建失敗: {response.status_code} {response.text}")
            return False
    except Exception as e:
        print(f"❌ 創建用戶請求失敗: {e}")
        return False

def main():
    """主函數"""
    print("=== 測試用戶創建功能 ===")
    
    # 獲取管理員令牌
    token = get_admin_token()
    if not token:
        print("❌ 無法獲取管理員令牌")
        return
    
    # 測試創建用戶
    success = test_create_user(token)
    if success:
        print("✅ 用戶創建測試通過")
    else:
        print("❌ 用戶創建測試失敗")

if __name__ == "__main__":
    main()