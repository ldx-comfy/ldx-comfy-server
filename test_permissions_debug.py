#!/usr/bin/env python3
"""
權限驗證調試腳本
測試各種API端點的權限檢查
"""

import requests
import json
import time

BASE_URL = "http://127.0.0.1:1145"

def test_endpoint(name, method, url, headers=None, data=None):
    """測試端點"""
    print(f"\n=== 測試 {name} ===")
    print(f"請求: {method} {url}")

    try:
        if method == "GET":
            response = requests.get(url, headers=headers)
        elif method == "POST":
            response = requests.post(url, headers=headers, json=data)
        elif method == "DELETE":
            response = requests.delete(url, headers=headers)
        else:
            print(f"不支持的HTTP方法: {method}")
            return

        print(f"響應狀態碼: {response.status_code}")
        print(f"響應內容: {response.text[:200]}...")

        if response.status_code == 401:
            print("✅ 正確拒絕 - 未授權")
        elif response.status_code == 403:
            print("✅ 正確拒絕 - 權限不足")
        elif response.status_code == 200:
            print("✅ 允許訪問")
        else:
            print(f"⚠️ 意外狀態碼: {response.status_code}")

    except Exception as e:
        print(f"❌ 請求失敗: {e}")

def main():
    """主測試函數"""
    print("開始權限驗證調試測試...")

    # 測試未經身份驗證的請求
    print("\n" + "="*60)
    print("階段1: 測試未經身份驗證的請求")
    print("="*60)

    # 測試管理員端點
    test_endpoint("管理員用戶列表", "GET", f"{BASE_URL}/api/v1/admin/users/")
    test_endpoint("管理員身分組列表", "GET", f"{BASE_URL}/api/v1/admin/groups/")
    test_endpoint("管理員權限列表", "GET", f"{BASE_URL}/api/v1/admin/groups/permissions/list")

    # 測試表單端點
    test_endpoint("工作流列表", "GET", f"{BASE_URL}/api/v1/forms/workflows")
    test_endpoint("用戶工作流列表", "GET", f"{BASE_URL}/api/v1/forms/user/workflows")
    test_endpoint("用戶歷史記錄", "GET", f"{BASE_URL}/api/v1/forms/user/history")
    test_endpoint("工作流表單模式", "GET", f"{BASE_URL}/api/v1/forms/workflows/test/form-schema")

    # 測試執行狀態端點（這個應該不需要身份驗證）
    test_endpoint("執行狀態", "GET", f"{BASE_URL}/api/v1/forms/executions/test-execution/status")

    # 測試取消執行端點（這個應該不需要身份驗證）
    test_endpoint("取消執行", "DELETE", f"{BASE_URL}/api/v1/forms/executions/test-execution")

    print("\n" + "="*60)
    print("階段2: 測試經身份驗證的請求")
    print("="*60)

    # 登錄獲取token
    login_data = {"username": "admin", "password": "admin123"}
    try:
        login_response = requests.post(f"{BASE_URL}/api/v1/auth/login", json=login_data)
        if login_response.status_code == 200:
            token_data = login_response.json()
            token = token_data.get("access_token")
            headers = {"Authorization": f"Bearer {token}"}
            print("✅ 管理員登錄成功")

            # 使用token測試同樣的端點
            test_endpoint("管理員用戶列表 (已授權)", "GET", f"{BASE_URL}/api/v1/admin/users/", headers=headers)
            test_endpoint("用戶歷史記錄 (已授權)", "GET", f"{BASE_URL}/api/v1/forms/user/history", headers=headers)
        else:
            print(f"❌ 登錄失敗: {login_response.status_code} {login_response.text}")
    except Exception as e:
        print(f"❌ 登錄請求失敗: {e}")

    print("\n" + "="*60)
    print("測試完成")
    print("="*60)

if __name__ == "__main__":
    main()