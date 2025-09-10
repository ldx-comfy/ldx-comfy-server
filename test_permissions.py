"""
權限系統測試腳本
用於測試簡化後的權限系統是否正常工作
"""

import json
import requests
import time

# 服務器地址
BASE_URL = "http://localhost:800"

def test_permissions():
    """測試權限系統"""
    print("開始測試權限系統...")
    
    # 1. 獲取管理員令牌
    print("\n1. 獲取管理員令牌...")
    admin_login_data = {
        "username": "admin",
        "password": "admin123"  # 這應該是實際的管理員密碼
    }
    
    try:
        response = requests.post(f"{BASE_URL}/api/v1/auth/login", json=admin_login_data)
        if response.status_code == 200:
            admin_token = response.json()["access_token"]
            print(f"管理員令牌獲取成功: {admin_token[:20]}...")
        else:
            print(f"管理員令牌獲取失敗: {response.status_code} {response.text}")
            return
    except Exception as e:
        print(f"管理員令牌獲取失敗: {e}")
        return
    
    # 2. 獲取所有身分組
    print("\n2. 獲取所有身分組...")
    headers = {"Authorization": f"Bearer {admin_token}"}
    try:
        response = requests.get(f"{BASE_URL}/api/v1/admin/groups", headers=headers)
        if response.status_code == 200:
            groups = response.json()
            print(f"身分組獲取成功，共 {len(groups)} 個身分組")
            for group in groups:
                print(f"  - {group['name']} ({group['id']}): {len(group['permissions'])} 個權限")
        else:
            print(f"身分組獲取失敗: {response.status_code} {response.text}")
    except Exception as e:
        print(f"身分組獲取失敗: {e}")
    
    # 3. 獲取系統權限列表
    print("\n3. 獲取系統權限列表...")
    try:
        response = requests.get(f"{BASE_URL}/api/v1/admin/groups/permissions/list", headers=headers)
        if response.status_code == 200:
            permissions = response.json()
            print(f"系統權限列表獲取成功，共 {len(permissions)} 個權限")
            # 顯示前10個權限
            for perm in permissions[:10]:
                print(f"  - {perm['name']} ({perm['id']})")
            if len(permissions) > 10:
                print(f"  ... 還有 {len(permissions) - 10} 個權限")
        else:
            print(f"系統權限列表獲取失敗: {response.status_code} {response.text}")
    except Exception as e:
        print(f"系統權限列表獲取失敗: {e}")
    
    # 4. 獲取當前用戶權限
    print("\n4. 獲取當前用戶權限...")
    try:
        response = requests.get(f"{BASE_URL}/api/v1/admin/groups/my/permissions", headers=headers)
        if response.status_code == 200:
            my_permissions = response.json()
            print(f"當前用戶權限獲取成功，共 {len(my_permissions)} 個權限")
            # 顯示所有權限
            for perm in my_permissions:
                print(f"  - {perm['name']} ({perm['id']})")
        else:
            print(f"當前用戶權限獲取失敗: {response.status_code} {response.text}")
    except Exception as e:
        print(f"當前用戶權限獲取失敗: {e}")
    
    print("\n權限系統測試完成!")

if __name__ == "__main__":
    test_permissions()