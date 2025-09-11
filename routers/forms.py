"""
表单式API路由
"""
from typing import Dict, Any, List, Optional
import json
import logging
import os
import uuid
import base64
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from pydantic import BaseModel, Field
from comfy.plugins import plugin_manager
from comfy.get_wfs import get_wf_list, get_wf_params, get_wf, _wf_files_dir
from starlette.concurrency import run_in_threadpool
import global_data
from auth.permissions import get_current_identity, require_permissions # 更改導入
from history import save_generation_history, get_all_generation_history, process_image_paths
from history import get_user_generation_history as get_user_history

router = APIRouter(prefix="/api/v1/forms", tags=["表单工作流"])


class WorkflowExecutionRequest(BaseModel):
    """工作流执行请求"""
    workflow_id: str = Field(..., description="工作流ID")
    inputs: Dict[str, Any] = Field(default_factory=dict, description="输入参数")


class WorkflowExecutionResponse(BaseModel):
    """工作流执行响应"""
    execution_id: str
    status: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


@router.get("/workflows", response_model=List[str])
async def get_available_workflows(identity: Dict[str, Any] = Depends(require_permissions(["workflow:read:*"]))): # 修改為新的細粒度權限
    """獲取可用工作流列表"""
    logging.info("開始獲取可用工作流列表")
    try:
        workflows = get_wf_list()
        logging.info(f"成功獲取 {len(workflows)} 個工作流")
        return workflows
    except Exception as e:
        logging.error(f"獲取可用工作流列表失敗: {str(e)}")
        raise


@router.get("/user/workflows", response_model=List[str])
async def get_user_workflows(identity: Dict[str, Any] = Depends(require_permissions(["workflow:read:*"]))): # 暫定為此權限，以便和 get_available_workflows 一致
    """獲取当前用戶可用的工作流列表"""
    logging.info("開始獲取當前用戶可用的工作流列表")
    try:
        workflows = get_wf_list()
        logging.info(f"成功獲取 {len(workflows)} 個工作流")
        return workflows
    except Exception as e:
        logging.error(f"獲取當前用戶可用的工作流列表失敗: {str(e)}")
        raise


@router.get("/workflows/{workflow_id}/form-schema")
async def get_workflow_form_schema(workflow_id: str, identity: Dict[str, Any] = Depends(require_permissions(["workflow:read:*"]))): # 添加權限檢查
    """獲取工作流表單模式"""
    logging.info(f"開始獲取工作流 '{workflow_id}' 的表單模式")
    try:
        logging.debug(f"獲取工作流 '{workflow_id}' 的參數")
        params = get_wf_params(workflow_id)
        logging.debug(f"獲取工作流 '{workflow_id}' 的數據")
        workflow_data = get_wf(workflow_id)

        # 構建表單模式
        form_schema = {
            "workflow_id": workflow_id,
            "title": f"工作流: {workflow_id}",
            "fields": []
        }

        logging.debug(f"為工作流 '{workflow_id}' 構建表單模式，參數數量: {len(params)}")
        for param in params:
            field = {
                "node_id": param["node_id"],
                "title": param["title"],
                "class_type": param["class_type"],
                "type": _get_field_type(param["class_type"]),
                "required": True
            }
            form_schema["fields"].append(field)
            logging.debug(f"添加字段: {field['title']} (類型: {field['type']})")

        logging.info(f"成功構建工作流 '{workflow_id}' 的表單模式，字段數量: {len(form_schema['fields'])}")
        return form_schema

    except Exception as e:
        logging.error(f"獲取工作流 '{workflow_id}' 表單模式失敗: {str(e)}")
        raise HTTPException(status_code=404, detail=f"獲取工作流 '{workflow_id}' 表單模式失敗: {str(e)}")


@router.post("/workflows/{workflow_id}/execute", response_model=WorkflowExecutionResponse)
async def execute_workflow_with_form(
    workflow_id: str,
    nodes: str = Form(..., description="节点數據，格式: [{node},{node}, ...]"),
    files: Optional[List[UploadFile]] = File(None),
    identity: Dict[str, Any] = Depends(require_permissions(["workflow:execute:*"])) # 修改為新的細粒度權限
):
    """通過表單執行工作流"""
    logging.info(f"開始通過表單執行工作流 '{workflow_id}'")
    try:
        # 獲取工作流數據
        logging.debug(f"獲取工作流 '{workflow_id}' 的數據")
        workflow_data = get_wf(workflow_id)

        # 解析節點數據
        logging.debug("解析節點數據")
        nodes_data = json.loads(nodes)
        logging.debug(f"解析到 {len(nodes_data)} 個節點")

        # 处理上传的文件，将其保存到服务器并构建名称到路径的映射
        saved_files_by_name: Dict[str, str] = {}
        if files:
            logging.info(f"接收到 {len(files)} 个上传文件")
            upload_dir = os.path.abspath(global_data.UPLOAD_DIR)
            try:
                os.makedirs(upload_dir, exist_ok=True)
            except Exception as mk_e:
                logging.warning("创建上传目录失败: %s", mk_e)
            for f in files:
                try:
                    original_name = os.path.basename(getattr(f, "filename", "") or "upload.bin")
                    logging.debug(f"处理上传文件: original_name={original_name}, content_type={getattr(f, 'content_type', 'unknown')}")
                    unique_name = f"{uuid.uuid4().hex}_{original_name}"
                    save_path = os.path.join(upload_dir, unique_name)
                    content = await f.read()
                    with open(save_path, "wb") as out:
                        out.write(content)
                    saved_files_by_name[original_name] = save_path
                    logging.debug("保存上传文件: original=%s path=%s size=%s", original_name, save_path, len(content))
                except Exception as fe:
                    logging.warning("保存上传文件失败: %s (%s)", getattr(f, "filename", "(unknown)"), fe)

        # 构建输入参数（仅接受映射类型，避免将字符串作为 **kwargs 传入）
        inputs: Dict[str, Any] = {}
        for idx, node in enumerate(nodes_data):
            node_id = node.get("node_id")
            class_type = node.get("class_type")
            has_value = "value" in node
            raw_value = node.get("value", None)

            logging.debug(
                "解析节点[%s] node_id=%s class_type=%s has_value=%s raw_type=%s raw_preview=%s",
                idx, node_id, class_type, has_value, type(raw_value).__name__, str(raw_value)[:200]
            )

            # 忽略没有 node_id 或没有提供 value 的节点（避免覆盖默认 workflow 配置）
            if not node_id or not has_value:
                continue

            # 空字符串/None 视为未提供，跳过（避免把 "" 当成 **kwargs）
            if raw_value in ("", None):
                logging.debug("跳过空值节点: node_id=%s", node_id)
                continue

            # 规范化为映射类型，避免类型推断造成的 __setitem__ 报错
            value_map: Dict[str, Any]
            if isinstance(raw_value, dict):
                value_map = dict(raw_value)
            else:
                # 文本类输入（支持 CLIPTextEncode 及其变体）
                if class_type == "Text" or (isinstance(class_type, str) and "CLIPTextEncode" in class_type):
                    value_map = {"text": raw_value}
                elif class_type == "LoadImageOutput":
                    value_map = {"image_path": raw_value}
                elif class_type == "Switch any [Crystools]":
                    if isinstance(raw_value, bool):
                        value_map = {"boolean": raw_value}
                    else:
                        logging.debug("无法从非布尔值推断 Switch any 的映射, 跳过 node_id=%s", node_id)
                        continue
                else:
                    logging.debug("未知 class_type 且 value 非映射，跳过 node_id=%s", node_id)
                    continue

            # 若为图片类型且提供的值是文件名，则映射成保存后的服务器路径
            if class_type == "LoadImageOutput":
                try:
                    img_ref = value_map.get("image_path")
                    if isinstance(img_ref, str) and img_ref in saved_files_by_name:
                        value_map["image_path"] = saved_files_by_name[img_ref]
                        logging.debug("映射图片文件名到路径: %s -> %s", img_ref, value_map["image_path"])
                except Exception as map_e:
                    logging.debug("图片文件名映射失败 node_id=%s: %s", node_id, map_e)

            inputs[str(node_id)] = value_map
            logging.debug("设置输入参数: node_id=%s value_type=%s value=%s", node_id, type(value_map).__name__, value_map)

        # 获取工作流执行器
        logging.debug("获取工作流执行器")
        executor = plugin_manager.get_workflow_executor()

        # 执行工作流（节点内容交由插件处理）
        logging.info(f"开始执行工作流 '{workflow_id}'，输入参数数量: {len(inputs)}")
        logging.debug("准备在线程池中执行工作流")
        # 在线程池中执行阻塞型工作，防止阻塞事件循环造成后端“卡住”
        result = await run_in_threadpool(executor.execute_workflow, workflow_data, inputs)
        logging.debug("工作流执行完成")
        logging.info(f"工作流 '{workflow_id}' 执行完成，执行ID: {result['execution_id']}，状态: {result['status']}")

        # 準備生成歷史數據
        user_id = identity.get("sub", "unknown_user")
        input_params = {
            "nodes": nodes_data,
            "files": [f.filename for f in files] if files else []
        }

        # 处理图像数据，将base64转换为文件路径
        processed_result = _process_images_for_history(result, result["execution_id"])

        # 保存生成歷史（在返回結果之前）
        try:
            save_generation_history(
                user_id=user_id,
                workflow_id=workflow_id,
                execution_id=result["execution_id"],
                input_params=input_params,
                result=processed_result
            )
            logging.info(f"生成歷史已保存: user_id={user_id}, execution_id={result['execution_id']}")
        except Exception as e:
            logging.error(f"保存生成歷史失敗: {e}")

        return WorkflowExecutionResponse(
            execution_id=result["execution_id"],
            status=result["status"],
            result=result
        )
    except Exception as e:
        logging.error(f"执行工作流 '{workflow_id}' 失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"执行工作流失败: {str(e)}")


@router.get("/user/history", response_model=List[Dict[str, Any]])
async def get_user_generation_history(identity: Dict[str, Any] = Depends(require_permissions(["history:read:self"]))): # 修改為新的細粒度權限
    """獲取當前用戶的生成歷史記錄"""
    logging.info("開始獲取當前用戶的生成歷史記錄")
    try:
        user_id = identity.get("sub", "unknown_user")
        history = await get_user_history(user_id)
        # 處理圖片路徑以避免重複前綴
        processed_history = process_image_paths(history)
        # 先將輸入圖片（nodes/files）轉為 base64，確保帶圖片的歷史輸入也無論如何是 data URL
        processed_history = _convert_input_images_to_base64_for_frontend(processed_history)
        # 再將結果圖片轉為 base64
        frontend_history = _convert_images_to_base64_for_frontend(processed_history)
        logging.info(f"成功獲取用戶 {user_id} 的生成歷史記錄，共 {len(frontend_history)} 條")
        return frontend_history
    except Exception as e:
        logging.error(f"獲取當前用戶的生成歷史記錄失敗: {str(e)}")
        raise


@router.get("/user/history/{execution_id}", response_model=Dict[str, Any])
async def get_user_generation_history_detail(execution_id: str, identity: Dict[str, Any] = Depends(require_permissions(["history:read:self"]))): # 修改為新的細粒度權限
    """獲取當前用戶特定執行ID的生成歷史記錄詳情"""
    logging.info(f"開始獲取執行ID '{execution_id}' 的生成歷史記錄詳情")
    try:
        user_id = identity.get("sub", "unknown_user")
        history = await get_user_history(user_id)
        # 處理圖片路徑以避免重複前綴
        processed_history = process_image_paths(history)

        # 查找匹配的記錄
        record = None
        for item in processed_history:
            if item.get("execution_id") == execution_id:
                record = item
                break

        if record is None:
            logging.warning(f"未找到執行ID '{execution_id}' 的生成歷史記錄")
            raise HTTPException(status_code=404, detail=f"未找到執行ID '{execution_id}' 的生成歷史記錄")

        # 先將輸入圖片（nodes/files）轉為 base64
        converted_list = _convert_input_images_to_base64_for_frontend([record])
        # 再將結果圖片轉為 base64
        frontend_record = _convert_images_to_base64_for_frontend(converted_list)[0]
        logging.info(f"成功獲取執行ID '{execution_id}' 的生成歷史記錄詳情")
        return frontend_record
    except HTTPException:
        # 重新抛出HTTP異常
        raise
    except Exception as e:
        logging.error(f"獲取執行ID '{execution_id}' 的生成歷史記錄詳情失敗: {str(e)}")
        raise HTTPException(status_code=500, detail=f"獲取生成歷史記錄詳情失敗: {str(e)}")


@router.get("/admin/history", response_model=List[Dict[str, Any]])
async def get_all_users_generation_history(identity: Dict[str, Any] = Depends(require_permissions(["admin:history:read"]))): # 修改為新的細粒度權限
    """獲取所有用戶的生成歷史記錄（僅限管理員）"""
    logging.info("管理員開始獲取所有用戶的生成歷史記錄")
    try:
        history = get_all_generation_history()
        # 處理圖片路徑以避免重複前綴
        processed_history = process_image_paths(history)
        # 先將輸入圖片（nodes/files）轉為 base64
        processed_history = _convert_input_images_to_base64_for_frontend(processed_history)
        # 再將結果圖片轉為 base64
        frontend_history = _convert_images_to_base64_for_frontend(processed_history)
        logging.info(f"管理員成功獲取所有用戶的生成歷史記錄，共 {len(frontend_history)} 條")
        return frontend_history
    except Exception as e:
        logging.error(f"管理員獲取所有用戶的生成歷史記錄失敗: {str(e)}")
        raise


@router.get("/admin/history/{execution_id}", response_model=Dict[str, Any])
async def get_any_user_generation_history_detail(execution_id: str, identity: Dict[str, Any] = Depends(require_permissions(["admin:history:read"]))): # 修改為新的細粒度權限
    """獲取任意用戶特定執行ID的生成歷史記錄詳情（僅限管理員）"""
    logging.info(f"管理員開始獲取執行ID '{execution_id}' 的生成歷史記錄詳情")
    try:
        history = get_all_generation_history()
        # 處理圖片路徑以避免重複前綴
        processed_history = process_image_paths(history)

        # 查找匹配的記錄
        record = None
        for item in processed_history:
            if item.get("execution_id") == execution_id:
                record = item
                break

        if record is None:
            logging.warning(f"未找到執行ID '{execution_id}' 的生成歷史記錄")
            raise HTTPException(status_code=404, detail=f"未找到執行ID '{execution_id}' 的生成歷史記錄")

        # 先將輸入圖片（nodes/files）轉為 base64
        converted_list = _convert_input_images_to_base64_for_frontend([record])
        # 再將結果圖片轉為 base64
        frontend_record = _convert_images_to_base64_for_frontend(converted_list)[0]
        logging.info(f"管理員成功獲取執行ID '{execution_id}' 的生成歷史記錄詳情")
        return frontend_record
    except HTTPException:
        # 重新抛出HTTP異常
        raise
    except Exception as e:
        logging.error(f"管理員獲取執行ID '{execution_id}' 的生成歷史記錄詳情失敗: {str(e)}")
        raise HTTPException(status_code=500, detail=f"獲取生成歷史記錄詳情失敗: {str(e)}")


@router.get("/executions/{execution_id}/status", response_model=WorkflowExecutionResponse)
async def get_execution_status(execution_id: str):
    """获取执行状态"""
    logging.info(f"开始获取执行 '{execution_id}' 的状态")
    try:
        logging.debug("获取工作流执行器")
        executor = plugin_manager.get_workflow_executor()
        logging.debug(f"查询执行 '{execution_id}' 的状态")
        status = executor.get_execution_status(execution_id)

        logging.info(f"执行 '{execution_id}' 状态: {status['status']}")
        if status.get("error"):
            logging.warning(f"执行 '{execution_id}' 存在错误: {status['error']}")

        return WorkflowExecutionResponse(
            execution_id=execution_id,
            status=status["status"],
            result=status.get("result"),
            error=status.get("error")
        )

    except Exception as e:
        logging.error(f"获取执行 '{execution_id}' 状态失败: {str(e)}")
        raise HTTPException(status_code=404, detail=f"获取执行状态失败: {str(e)}")


@router.delete("/executions/{execution_id}")
async def cancel_execution(execution_id: str):
    """取消执行"""
    logging.info(f"开始取消执行 '{execution_id}'")
    try:
        logging.debug("获取工作流执行器")
        executor = plugin_manager.get_workflow_executor()
        logging.debug(f"尝试取消执行 '{execution_id}'")
        success = executor.cancel_execution(execution_id)

        if success:
            logging.info(f"执行 '{execution_id}' 已成功取消")
            return {"message": f"执行 '{execution_id}' 已取消"}
        else:
            logging.warning(f"无法取消执行 '{execution_id}'")
            raise HTTPException(status_code=400, detail="无法取消执行")

    except Exception as e:
        logging.error(f"取消执行 '{execution_id}' 失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"取消执行失败: {str(e)}")


def _process_images_for_history(result: Dict[str, Any], execution_id: str) -> Dict[str, Any]:
    """
    处理结果中的图像数据，将base64图像保存为文件并更新路径

    Args:
        result: 工作流执行结果
        execution_id: 执行ID

    Returns:
        处理后的结果
    """
    if not result or 'images' not in result:
        return result

    processed_result = result.copy()
    processed_images = []

    for image_data in result['images']:
        if isinstance(image_data, str):
            if image_data.startswith('data:image/'):
                # base64数据URL，需要保存为文件
                try:
                    # 解析base64数据
                    header, base64_string = image_data.split(',', 1)
                    image_format = header.split(';')[0].split('/')[1]  # 例如 'png', 'jpeg'

                    # 解码base64
                    image_bytes = base64.b64decode(base64_string)

                    # 创建输出目录
                    output_dir = os.path.join(global_data.COMFY_OUTPUT_DIR, 'comfy_out_image')
                    os.makedirs(output_dir, exist_ok=True)

                    # 生成文件名
                    filename = f"{execution_id}_{uuid.uuid4().hex}.{image_format}"
                    filepath = os.path.join(output_dir, filename)

                    # 保存文件
                    with open(filepath, 'wb') as f:
                        f.write(image_bytes)

                    # 使用相对路径存储（不带前缀）
                    processed_images.append(filename)
                    logging.debug(f"保存base64图像为文件: {filepath}")

                except Exception as e:
                    logging.error(f"处理base64图像失败: {e}")
                    # 如果处理失败，保留原始数据
                    processed_images.append(image_data)
            else:
                # 已经是文件路径，直接使用
                processed_images.append(image_data)
        else:
            # 非字符串数据，直接使用
            processed_images.append(image_data)

    processed_result['images'] = processed_images
    return processed_result


def _convert_images_to_base64_for_frontend(history_records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    将历史记录中的文件路径图像转换为base64格式供前端使用。
    无论如何，保证返回给前端的 images 字段均为 data URL。
    当源文件不存在或读取失败时，使用 1x1 透明 PNG 作为占位图。
    """
    processed_records = []
    PLACEHOLDER_DATA_URL = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGMAAQAABQABDQottAAAAABJRU5ErkJggg=="

    for record in history_records:
        processed_record = json.loads(json.dumps(record))  # 深拷贝

        if 'result' in processed_record and 'images' in processed_record['result']:
            images = processed_record['result']['images']
            if isinstance(images, list):
                for i, image_entry in enumerate(images):
                    # 已经是 data URL，直接跳过
                    if isinstance(image_entry, str) and image_entry.startswith('data:'):
                        continue

                    try:
                        file_candidates = []
                        if isinstance(image_entry, str):
                            candidate_rel = image_entry.lstrip('/')

                            # 1) 默认保存目录：.../comfy_out_image/<filename>
                            file_candidates.append(os.path.join(global_data.COMFY_OUTPUT_DIR, 'comfy_out_image', candidate_rel))

                            # 2) 如果记录里自带 comfy_out_image/ 前缀，去掉后再尝试一次
                            if candidate_rel.startswith('comfy_out_image/'):
                                trimmed = candidate_rel[len('comfy_out_image/'):]
                                file_candidates.append(os.path.join(global_data.COMFY_OUTPUT_DIR, 'comfy_out_image', trimmed))

                            # 3) 兼容早期保存到 COMFY_OUTPUT_DIR 根目录的情况
                            file_candidates.append(os.path.join(global_data.COMFY_OUTPUT_DIR, candidate_rel))

                        # 找到第一个存在的文件
                        file_path = next((p for p in file_candidates if os.path.exists(p)), None)

                        if file_path:
                            with open(file_path, 'rb') as f:
                                image_data = f.read()

                            # 从扩展名推断 MIME
                            ext = os.path.splitext(file_path)[1].lower()
                            if ext == '.png':
                                mime_type = 'image/png'
                            elif ext in ['.jpg', '.jpeg']:
                                mime_type = 'image/jpeg'
                            elif ext == '.gif':
                                mime_type = 'image/gif'
                            elif ext == '.webp':
                                mime_type = 'image/webp'
                            else:
                                mime_type = 'image/png'  # 默认

                            base64_data = base64.b64encode(image_data).decode('utf-8')
                            images[i] = f"data:{mime_type};base64,{base64_data}"
                            logging.debug(f"转换图像路径为base64: {file_path}")
                        else:
                            logging.warning(f"图像文件不存在，使用占位图: {image_entry}")
                            images[i] = PLACEHOLDER_DATA_URL

                    except Exception as e:
                        logging.error(f"转换图像为base64失败，使用占位图 {image_entry}: {e}")
                        images[i] = PLACEHOLDER_DATA_URL

        processed_records.append(processed_record)

    return processed_records


def _convert_input_images_to_base64_for_frontend(history_records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    将历史记录中的输入图片（input_params.nodes 与 input_params.files）转换为 base64 数据URL，供前端使用。
    无论如何均返回 data URL；当源文件不存在或读取失败时，使用 1x1 透明 PNG 作为占位图。
    """
    processed_records: List[Dict[str, Any]] = []
    PLACEHOLDER_DATA_URL = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGMAAQAABQABDQottAAAAABJRU5ErkJggg=="

    try:
        upload_dir = os.fspath(global_data.UPLOAD_DIR)
    except Exception:
        upload_dir = str(global_data.UPLOAD_DIR)

    def _to_data_url_from_uploaded_or_path(ref: str) -> str:
        """将输入引用（原始文件名/相对或绝对路径/dataURL）转换为 data URL。"""
        if not isinstance(ref, str):
            return PLACEHOLDER_DATA_URL
        if ref.startswith("data:"):
            return ref

        try:
            candidates: List[str] = []

            # 绝对路径
            if os.path.isabs(ref):
                candidates.append(ref)

            # 作为相对路径或纯文件名，拼到 uploads 目录下
            candidates.append(os.path.join(upload_dir, ref))

            # 在 uploads 目录中查找形如 '<uuid>_<original_name>' 的文件
            try:
                if os.path.isdir(upload_dir):
                    for fname in os.listdir(upload_dir):
                        if fname == ref:
                            candidates.append(os.path.join(upload_dir, fname))
                        elif "_" in fname:
                            suffix = fname.split("_", 1)[1]
                            if suffix == ref:
                                candidates.append(os.path.join(upload_dir, fname))
            except Exception as e:
                logging.debug("列举上传目录失败: %s", e)

            file_path = next((p for p in candidates if os.path.exists(p)), None)
            if not file_path:
                logging.warning("未找到输入图像文件，使用占位图: %s", ref)
                return PLACEHOLDER_DATA_URL

            with open(file_path, "rb") as f:
                image_data = f.read()

            # 根据扩展名推断 MIME
            _, ext = os.path.splitext(file_path)
            ext = ext.lower()
            if ext == ".png":
                mime_type = "image/png"
            elif ext in [".jpg", ".jpeg"]:
                mime_type = "image/jpeg"
            elif ext == ".gif":
                mime_type = "image/gif"
            elif ext == ".webp":
                mime_type = "image/webp"
            else:
                mime_type = "image/png"  # 默认

            base64_data = base64.b64encode(image_data).decode("utf-8")
            return f"data:{mime_type};base64,{base64_data}"
        except Exception as e:
            logging.error("读取输入图像失败，使用占位图: %s", e)
            return PLACEHOLDER_DATA_URL

    for record in history_records:
        processed_record = json.loads(json.dumps(record))  # 深拷贝
        try:
            input_params = processed_record.get("input_params", {})

            # 1) 处理 nodes 中的 LoadImageOutput.value
            nodes = input_params.get("nodes")
            if isinstance(nodes, list):
                for node in nodes:
                    try:
                        if (
                            isinstance(node, dict)
                            and node.get("class_type") == "LoadImageOutput"
                            and "value" in node
                            and isinstance(node.get("value"), str)
                        ):
                            node["value"] = _to_data_url_from_uploaded_or_path(node["value"])
                    except Exception as ne:
                        logging.error("转换输入节点图像为base64失败: %s", ne)
                        if isinstance(node, dict):
                            node["value"] = PLACEHOLDER_DATA_URL

            # 2) 处理 files 列表中的原始文件名
            files_list = input_params.get("files")
            if isinstance(files_list, list):
                for i, fname in enumerate(files_list):
                    if isinstance(fname, str):
                        try:
                            files_list[i] = _to_data_url_from_uploaded_or_path(fname)
                        except Exception as fe:
                            logging.error("转换输入文件为base64失败 %s: %s", fname, fe)
                            files_list[i] = PLACEHOLDER_DATA_URL

        except Exception as e:
            logging.error("处理输入图像为base64失败: %s", e)

        processed_records.append(processed_record)

    return processed_records
def _get_field_type(class_type: str) -> str:
    """根据节点类型获取表单字段类型"""
    logging.debug(f"获取字段类型映射，class_type: {class_type}")
    type_mapping = {
        "LoadImageOutput": "file",
        "Text": "text",
        "CLIPTextEncode": "text",
        "Switch any [Crystools]": "boolean"
    }
    field_type = type_mapping.get(class_type, "text")
    logging.debug(f"映射结果: {class_type} -> {field_type}")
    return field_type


@router.post("/workflows/upload")
async def upload_workflow(
    file: UploadFile = File(...),
    identity: Dict[str, Any] = Depends(require_permissions(["admin:workflows:manage"])) # 修改為新的細粒度權限
):
    """上傳工作流文件"""
    logging.info(f"開始上傳工作流文件: {file.filename}")
    try:
        # 檢查文件擴展名
        if not file.filename or not file.filename.endswith('.json'):
            raise HTTPException(status_code=400, detail="只允許上傳 JSON 文件")
        
        # 讀取文件內容
        content = await file.read()
        
        # 驗證 JSON 格式
        try:
            workflow_data = json.loads(content)
        except json.JSONDecodeError as e:
            raise HTTPException(status_code=400, detail=f"無效的 JSON 格式: {str(e)}")
        
        # 獲取工作流 ID（檔名不帶擴展名）
        workflow_id = file.filename[:-5]  # 去掉 .json 擴展名
        
        # 構建保存路徑
        save_path = os.path.join(_wf_files_dir, file.filename)
        
        # 保存文件
        with open(save_path, "wb") as f:
            f.write(content)
        
        logging.info(f"工作流文件 '{workflow_id}' 上傳成功")
        return {"message": f"工作流 '{workflow_id}' 上傳成功", "workflow_id": workflow_id}
    except Exception as e:
        logging.error(f"上傳工作流文件失敗: {str(e)}")
        raise HTTPException(status_code=500, detail=f"上傳工作流文件失敗: {str(e)}")


@router.delete("/workflows/{workflow_id}")
async def delete_workflow(
    workflow_id: str,
    identity: Dict[str, Any] = Depends(require_permissions(["admin:workflows:manage"])) # 修改為新的細粒度權限
):
    """刪除工作流文件"""
    logging.info(f"開始刪除工作流: {workflow_id}")
    try:
        # 構建文件路徑
        file_path = os.path.join(_wf_files_dir, f"{workflow_id}.json")
        
        # 檢查文件是否存在
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail=f"工作流 '{workflow_id}' 不存在")
        
        # 刪除文件
        os.remove(file_path)
        
        logging.info(f"工作流 '{workflow_id}' 刪除成功")
        return {"message": f"工作流 '{workflow_id}' 刪除成功"}
    except Exception as e:
        logging.error(f"刪除工作流失敗: {str(e)}")
        raise HTTPException(status_code=500, detail=f"刪除工作流失敗: {str(e)}")