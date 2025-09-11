#!/usr/bin/env python3
"""
測試執行工作流權限的腳本
"""

import json
import requests
import time

# 伺服器地址
BASE_URL = "http://localhost:1145"

# 測試用的管理員憑證
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"  # 需要根據實際情況修改

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

def test_execute_workflow_without_auth():
    """測試未經身份驗證執行工作流"""
    print("測試未經身份驗證執行工作流...")
    
    # 準備執行數據
    nodes_data = [
        {
            "node_id": "1",
            "class_type": "Text",
            "value": "test prompt"
        }
    ]
    
    # 創建表單數據
    files = {
        'nodes': (None, json.dumps(nodes_data))
    }
    
    response = requests.post(f"{BASE_URL}/api/v1/forms/workflows/test/execute", files=files)
    if response.status_code == 401:
        print("✓ 未經身份驗證執行工作流被正確拒絕 (401)")
        return True
    else:
        print(f"✗ 未經身份驗證執行工作流未被拒絕，返回狀態碼: {response.status_code}")
        print(f"  響應內容: {response.text}")
        return False

def test_execute_workflow_with_auth(token):
    """測試經身份驗證後執行工作流"""
    print("測試經身份驗證後執行工作流...")
    
    headers = {
        "Authorization": f"Bearer {token}"
    }
    
    # 準備執行數據
    nodes_data = [
        {
            "node_id": "1",
            "class_type": "Text",
            "value": "test prompt"
        }
    ]
    
    # 創建表單數據
    files = {
        'nodes': (None, json.dumps(nodes_data))
    }
    
    response = requests.post(f"{BASE_URL}/api/v1/forms/workflows/test/execute", files=files, headers=headers)
    if response.status_code == 200:
        result = response.json()
        print(f"✓ 經身份驗證後成功執行工作流，執行ID: {result.get('execution_id')}")
        return True
    elif response.status_code == 403:
        print("✓ 經身份驗證後執行工作流被權限拒絕 (403)")
        return True
    else:
        print(f"✗ 經身份驗證後執行工作流失敗，返回狀態碼: {response.status_code}")
        print(f"  響應內容: {response.text}")
        return False

def main():
    """主測試函數"""
    print("開始測試執行工作流權限功能...")
    
    # 1. 測試未經身份驗證執行工作流
    print("\n1. 測試未經身份驗證執行工作流")
    test1_passed = test_execute_workflow_without_auth()
    
    # 2. 管理員登錄
    print("\n2. 管理員登錄")
    token = login_admin()
    if not token:
        print("管理員登錄失敗，無法進行後續測試")
        return
    
    # 3. 測試經身份驗證後執行工作流
    print("\n3. 測試經身份驗證後執行工作流")
    test2_passed = test_execute_workflow_with_auth(token)
    
    # 總結
    print("\n" + "="*50)
    print("測試結果總結:")
    print(f"  未經身份驗證執行工作流: {'通過' if test1_passed else '失敗'}")
    print(f"  經身份驗證後執行工作流: {'通過' if test2_passed else '失敗'}")
    
    if test1_passed and test2_passed:
        print("\n🎉 所有測試通過！權限檢查正常！")
    else:
        print("\n❌ 部分測試失敗，請檢查權限實現。")

if __name__ == "__main__":
    main()