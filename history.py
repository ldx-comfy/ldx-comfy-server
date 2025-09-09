"""
生成歷史管理模塊
"""
import json
import os
import time
import logging
from typing import Dict, Any, List

# 配置日誌
logger = logging.getLogger(__name__)

# 定義歷史記錄文件路徑
HISTORY_FILE = os.path.join(os.path.dirname(__file__), 'data', 'generation_history.json')

def _ensure_history_file_exists():
    """確保歷史記錄文件存在，如果不存在則創建一個空的文件。"""
    os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
    if not os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump([], f)

def save_generation_history(
    user_id: str,
    workflow_id: str,
    execution_id: str,
    input_params: Dict[str, Any],
    result: Dict[str, Any]
):
    """
    保存生成歷史記錄。

    Args:
        user_id: 用戶 ID。
        workflow_id: Workflow ID。
        execution_id: 執行 ID。
        input_params: 輸入參數。
        result: 生成結果。
    """
    try:
        _ensure_history_file_exists()
        
        # 構建歷史記錄
        history_record = {
            "user_id": user_id,
            "workflow_id": workflow_id,
            "execution_id": execution_id,
            "timestamp": int(time.time()),  # UTC+8 timestamp
            "input_params": input_params,
            "result": result
        }
        
        # 讀取現有歷史記錄
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            history = json.load(f)
        
        # 添加新記錄
        history.append(history_record)
        
        # 保存更新後的歷史記錄
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
            
        logger.info(f"生成歷史記錄已保存: user_id={user_id}, execution_id={execution_id}")
        
    except Exception as e:
        logger.error(f"保存生成歷史記錄失敗: {e}")
        raise

async def get_user_generation_history(user_id: str) -> List[Dict[str, Any]]:
    """
    獲取特定用戶的生成歷史記錄。

    Args:
        user_id: 用戶 ID。

    Returns:
        用戶的生成歷史記錄列表。
    """
    try:
        _ensure_history_file_exists()
        
        # 讀取歷史記錄
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            history = json.load(f)
        
        # 過濾出特定用戶的記錄
        user_history = [record for record in history if record.get("user_id") == user_id]
        
        # 按時間戳降序排列（最新的在前）
        user_history.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
        
        return user_history
        
    except Exception as e:
        logger.error(f"獲取用戶生成歷史記錄失敗: {e}")
        return []

def get_all_generation_history() -> List[Dict[str, Any]]:
    """
    獲取所有用戶的生成歷史記錄。

    Returns:
        所有用戶的生成歷史記錄列表。
    """
    try:
        _ensure_history_file_exists()
        
        # 讀取歷史記錄
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            history = json.load(f)
        
        # 按時間戳降序排列（最新的在前）
        history.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
        
        return history
        
    except Exception as e:
        logger.error(f"獲取所有用戶生成歷史記錄失敗: {e}")
        return []


def process_image_paths(history_records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    處理歷史記錄中的圖片路徑，確保它們不包含重複的前綴。
    
    Args:
        history_records: 歷史記錄列表。
        
    Returns:
        處理後的歷史記錄列表。
    """
    processed_records = []
    for record in history_records:
        # 創建記錄的深拷貝以避免修改原始數據
        processed_record = json.loads(json.dumps(record))
        
        # 處理圖片路徑
        if 'result' in processed_record and 'images' in processed_record['result']:
            images = processed_record['result']['images']
            if isinstance(images, list):
                for i, image_path in enumerate(images):
                    # 只處理非base64數據URL的文件路徑
                    if isinstance(image_path, str) and image_path.startswith('comfy_out_image/') and not image_path.startswith('data:'):
                        # 移除重複的前綴
                        images[i] = image_path[len('comfy_out_image/'):]
        
        processed_records.append(processed_record)
    
    return processed_records
