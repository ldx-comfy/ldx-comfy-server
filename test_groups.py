#!/usr/bin/env python3
"""
身分組功能測試腳本
"""

import json
import requests
import time

# 伺服器地址
BASE_URL = "http://localhost:1145"

# 測試用的管理員憑證
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin_password"  # 需要根據實際情況修改

def login_admin():
    """管理員登錄獲取JWT令牌"""
    login_data = {
        "username": ADMIN_USERNAME,
        "password": ADMIN_PASSWORD
    }
    
    response = requests.post(f"{BASE_URL}/api/v1/auth/login", json=login_data)
    if response.status_code == 200:
        token_data = response.json()
        return token_data["access_token"]
    else:
        print(f"管理員登錄失敗: {response.status_code} {response.text}")
        return None

def test_create_group(token):
    """測試創建身分組"""
    headers = {
        "Authorization": f"Bearer {token}"
    }
    
    group_data = {
        "id": "test_group",
        "name": "測試身分組",
        "description": "用於測試的身分組",
        "permissions": ["user:create", "user:read"],
        "level": 50
    }
    
    response = requests.post(f"{BASE_URL}/api/v1/admin/groups", json=group_data, headers=headers)
    if response.status_code == 200:
        group_info = response.json()
        print(f"身分組創建成功: {group_info}")
        return group_info
    else:
        print(f"身分組創建失敗: {response.status_code} {response.text}")
        return None

def test_get_all_groups(token):
    """測試獲取所有身分組"""
    headers = {
        "Authorization": f"Bearer {token}"
    }
    
    response = requests.get(f"{BASE_URL}/api/v1/admin/groups", headers=headers)
    if response.status_code == 200:
        groups = response.json()
        print(f"獲取到 {len(groups)} 個身分組")
        for group in groups:
            print(f"  - {group['name']} ({group['id']})")
        return groups
    else:
        print(f"獲取身分組列表失敗: {response.status_code} {response.text}")
        return None

def test_get_group(token, group_id):
    """測試獲取指定身分組"""
    headers = {
        "Authorization": f"Bearer {token}"
    }
    
    response = requests.get(f"{BASE_URL}/api/v1/admin/groups/{group_id}", headers=headers)
    if response.status_code == 200:
        group_info = response.json()
        print(f"獲取身分組信息成功: {group_info}")
        return group_info
    else:
        print(f"獲取身分組信息失敗: {response.status_code} {response.text}")
        return None

def test_update_group(token, group_id):
    """測試更新身分組"""
    headers = {
        "Authorization": f"Bearer {token}"
    }
    
    update_data = {
        "name": "更新後的測試身分組",
        "description": "更新後的描述",
        "permissions": ["user:create", "user:read", "user:update"],
        "level": 60
    }
    
    response = requests.put(f"{BASE_URL}/api/v1/admin/groups/{group_id}", json=update_data, headers=headers)
    if response.status_code == 200:
        group_info = response.json()
        print(f"身分組更新成功: {group_info}")
        return group_info
    else:
        print(f"身分組更新失敗: {response.status_code} {response.text}")
        return None

def test_delete_group(token, group_id):
    """測試刪除身分組"""
    headers = {
        "Authorization": f"Bearer {token}"
    }
    
    response = requests.delete(f"{BASE_URL}/api/v1/admin/groups/{group_id}", headers=headers)
    if response.status_code == 200:
        result = response.json()
        print(f"身分組刪除成功: {result}")
        return True
    else:
        print(f"身分組刪除失敗: {response.status_code} {response.text}")
        return False

def test_get_system_permissions(token):
    """測試獲取系統權限列表"""
    headers = {
        "Authorization": f"Bearer {token}"
    }
    
    response = requests.get(f"{BASE_URL}/api/v1/admin/groups/permissions/list", headers=headers)
    if response.status_code == 200:
        permissions = response.json()
        print(f"獲取到 {len(permissions)} 個系統權限")
        for perm in permissions[:5]:  # 只顯示前5個
            print(f"  - {perm['name']} ({perm['id']})")
        return permissions
    else:
        print(f"獲取系統權限列表失敗: {response.status_code} {response.text}")
        return None

def main():
    """主測試函數"""
    print("開始測試身分組功能...")
    
    # 1. 管理員登錄
    print("\n1. 管理員登錄")
    token = login_admin()
    if not token:
        return
    
    # 2. 獲取系統權限列表
    print("\n2. 獲取系統權限列表")
    permissions = test_get_system_permissions(token)
    if not permissions:
        return
    
    # 3. 創建身分組
    print("\n3. 創建身分組")
    group = test_create_group(token)
    if not group:
        return
    group_id = group["id"]
    
    # 等待一段時間確保創建完成
    time.sleep(1)
    
    # 4. 獲取所有身分組
    print("\n4. 獲取所有身分組")
    groups = test_get_all_groups(token)
    if not groups:
        return
    
    # 5. 獲取指定身分組
    print("\n5. 獲取指定身分組")
    test_get_group(token, group_id)
    
    # 6. 更新身分組
    print("\n6. 更新身分組")
    test_update_group(token, group_id)
    
    # 等待一段時間確保更新完成
    time.sleep(1)
    
    # 7. 刪除身分組
    print("\n7. 刪除身分組")
    test_delete_group(token, group_id)
    
    print("\n身分組功能測試完成!")

if __name__ == "__main__":
    main()