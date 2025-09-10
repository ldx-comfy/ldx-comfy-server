#!/usr/bin/env python3
"""
調試腳本：檢查用戶登錄後獲得的 JWT token 中的角色信息
"""

import json
import requests
import time
import sys
from pathlib import Path

# 添加項目路徑以便導入模塊
sys.path.insert(0, str(Path(__file__).parent))

from auth import jwt as jwt_lib
from auth.config import get_jwt_secret

# 服務器地址
BASE_URL = "http://localhost:8000"

def test_user_login(username, password):
    """測試用戶登錄並檢查JWT token中的角色信息"""
    print(f"測試用戶 '{username}' 登錄...")
    
    # 登錄請求
    login_data = {
        "username": username,
        "password": password
    }
    
    try:
        response = requests.post(f"{BASE_URL}/api/v1/auth/login", json=login_data)
        if response.status_code == 200:
            token = response.json()["access_token"]
            print(f"登錄成功，獲得 JWT token: {token[:50]}...")
            
            # 解碼 JWT token
            secret = get_jwt_secret()
            claims = jwt_lib.decode(token, secret)
            print(f"JWT claims:")
            print(json.dumps(claims, indent=2, ensure_ascii=False))
            
            # 檢查角色和組
            roles = claims.get("roles", [])
            groups = claims.get("groups", [])
            print(f"用戶角色: {roles}")
            print(f"用戶組: {groups}")
            
            # 檢查是否具有 admin 角色
            if "admin" in roles:
                print("✓ 用戶具有 admin 角色")
            else:
                print("✗ 用戶不具有 admin 角色")
                
            return token, claims
        else:
            print(f"登錄失敗: {response.status_code} {response.text}")
            return None, None
    except Exception as e:
        print(f"登錄請求失敗: {e}")
        return None, None

def test_admin_endpoint(token):
    """測試訪問管理員端點"""
    print("\n測試訪問管理員端點 /api/v1/auth/admin/ping...")
    
    headers = {"Authorization": f"Bearer {token}"}
    try:
        response = requests.get(f"{BASE_URL}/api/v1/auth/admin/ping", headers=headers)
        if response.status_code == 200:
            print("✓ 成功訪問管理員端點")
            print(f"響應: {response.json()}")
        else:
            print(f"✗ 訪問管理員端點失敗: {response.status_code} {response.text}")
    except Exception as e:
        print(f"訪問管理員端點失敗: {e}")

def main():
    print("開始調試權限問題...")
    
    # 測試不同的用戶
    test_users = [
        ("admin", "admin123"),  # 需要替換為實際密碼
        ("ldx", "ldx_password"),  # 需要替換為實際密碼
        ("test", "test_password")  # 需要替換為實際密碼
    ]
    
    for username, password in test_users:
        print("\n" + "="*50)
        token, claims = test_user_login(username, password)
        if token and claims:
            test_admin_endpoint(token)
        print("="*50)

if __name__ == "__main__":
    main()