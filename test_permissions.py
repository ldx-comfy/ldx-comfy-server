#!/usr/bin/env python3
"""
測試權限功能
"""

import json
import requests
import global_data

# 服務器地址
BASE_URL = "http://localhost:8000"

def load_auth_config():
    """加載認證配置"""
    global_data.load_auth_config()
    return global_data.AUTH_CONFIG

def get_user_token(username, password):
    """獲取用戶令牌"""
    login_data = {
        "username": username,
        "password": password
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

def test_admin_permissions(token):
    """測試管理員權限"""
    if not token:
        print("❌ 無效的令牌")
        return False
    
    headers = {
        "Authorization": f"Bearer {token}"
    }
    
    try:
        # 測試管理員專屬端點
        response = requests.get(f"{BASE_URL}/api/v1/auth/admin/ping", headers=headers)
        if response.status_code == 200:
            print("✅ 管理員權限測試通過")
            return True
        else:
            print(f"❌ 管理員權限測試失敗: {response.status_code} {response.text}")
            return False
    except Exception as e:
        print(f"❌ 管理員權限測試請求失敗: {e}")
        return False

def test_user_permissions(token):
    """測試普通用戶權限"""
    if not token:
        print("❌ 無效的令牌")
        return False
    
    headers = {
        "Authorization": f"Bearer {token}"
    }
    
    try:
        # 測試普通用戶端點
        response = requests.get(f"{BASE_URL}/api/v1/auth/me", headers=headers)
        if response.status_code == 200:
            print("✅ 普通用戶權限測試通過")
            return True
        else:
            print(f"❌ 普通用戶權限測試失敗: {response.status_code} {response.text}")
            return False
    except Exception as e:
        print(f"❌ 普通用戶權限測試請求失敗: {e}")
        return False

def test_insufficient_permissions(token):
    """測試權限不足的情況"""
    if not token:
        print("❌ 無效的令牌")
        return False
    
    headers = {
        "Authorization": f"Bearer {token}"
    }
    
    try:
        # 測試管理員專屬端點（普通用戶應該無權限）
        response = requests.get(f"{BASE_URL}/api/v1/auth/admin/ping", headers=headers)
        if response.status_code == 403:
            print("✅ 權限不足測試通過（正確返回403）")
            return True
        else:
            print(f"❌ 權限不足測試失敗: 應該返回403但返回了 {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 權限不足測試請求失敗: {e}")
        return False

def main():
    """主函數"""
    print("=== 測試權限功能 ===")
    
    # 加載配置
    config = load_auth_config()
    
    # 獲取admin令牌
    admin_token = get_user_token("admin", "ldx123456")  # 根據實際密碼修改
    
    # 測試admin權限
    if admin_token:
        test_admin_permissions(admin_token)
    
    # 創建測試用戶（如果還不存在）
    # 這裡假設測試用戶已經存在，實際情況可能需要先創建
    
    # 獲取測試用戶令牌
    test_token = get_user_token("test", "testpassword123")  # 根據實際密碼修改
    
    # 測試普通用戶權限
    if test_token:
        test_user_permissions(test_token)
        test_insufficient_permissions(test_token)

if __name__ == "__main__":
    main()