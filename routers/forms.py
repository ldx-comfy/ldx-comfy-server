"""
表单式API路由
"""
from typing import Dict, Any, List, Optional
import json
import logging
import os
import uuid
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from pydantic import BaseModel, Field
from comfy.plugins import plugin_manager
from comfy.get_wfs import get_wf_list, get_wf_params, get_wf
from starlette.concurrency import run_in_threadpool


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
async def get_available_workflows():
    """获取可用工作流列表"""
    logging.info("开始获取可用工作流列表")
    try:
        workflows = get_wf_list()
        logging.info(f"成功获取 {len(workflows)} 个工作流")
        return workflows
    except Exception as e:
        logging.error(f"获取可用工作流列表失败: {str(e)}")
        raise


@router.get("/workflows/{workflow_id}/form-schema")
async def get_workflow_form_schema(workflow_id: str):
    """获取工作流表单模式"""
    logging.info(f"开始获取工作流 '{workflow_id}' 的表单模式")
    try:
        logging.debug(f"获取工作流 '{workflow_id}' 的参数")
        params = get_wf_params(workflow_id)
        logging.debug(f"获取工作流 '{workflow_id}' 的数据")
        workflow_data = get_wf(workflow_id)

        # 构建表单模式
        form_schema = {
            "workflow_id": workflow_id,
            "title": f"工作流: {workflow_id}",
            "fields": []
        }

        logging.debug(f"为工作流 '{workflow_id}' 构建表单模式，参数数量: {len(params)}")
        for param in params:
            field = {
                "node_id": param["node_id"],
                "title": param["title"],
                "class_type": param["class_type"],
                "type": _get_field_type(param["class_type"]),
                "required": True
            }
            form_schema["fields"].append(field)
            logging.debug(f"添加字段: {field['title']} (类型: {field['type']})")

        logging.info(f"成功构建工作流 '{workflow_id}' 的表单模式，字段数量: {len(form_schema['fields'])}")
        return form_schema

    except Exception as e:
        logging.error(f"获取工作流 '{workflow_id}' 表单模式失败: {str(e)}")
        raise HTTPException(status_code=404, detail=f"获取工作流 '{workflow_id}' 表单模式失败: {str(e)}")


@router.post("/workflows/{workflow_id}/execute", response_model=WorkflowExecutionResponse)
async def execute_workflow_with_form(
    workflow_id: str,
    nodes: str = Form(..., description="节点数据，格式: [{node},{node}, ...]"),
    files: Optional[List[UploadFile]] = File(None)
):
    """通过表单执行工作流"""
    logging.info(f"开始通过表单执行工作流 '{workflow_id}'")
    try:
        # 获取工作流数据
        logging.debug(f"获取工作流 '{workflow_id}' 的数据")
        workflow_data = get_wf(workflow_id)

        # 解析节点数据
        logging.debug("解析节点数据")
        nodes_data = json.loads(nodes)
        logging.debug(f"解析到 {len(nodes_data)} 个节点")

        # 处理上传的文件，将其保存到服务器并构建名称到路径的映射
        saved_files_by_name: Dict[str, str] = {}
        if files:
            upload_dir = os.path.abspath(os.path.join(os.getcwd(), "uploads"))
            try:
                os.makedirs(upload_dir, exist_ok=True)
            except Exception as mk_e:
                logging.warning("创建上传目录失败: %s", mk_e)
            for f in files:
                try:
                    original_name = os.path.basename(getattr(f, "filename", "") or "upload.bin")
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
        # 在线程池中执行阻塞型工作，防止阻塞事件循环造成后端“卡住”
        result = await run_in_threadpool(executor.execute_workflow, workflow_data, inputs)
        logging.info(f"工作流 '{workflow_id}' 执行完成，执行ID: {result['execution_id']}，状态: {result['status']}")

        return WorkflowExecutionResponse(
            execution_id=result["execution_id"],
            status=result["status"],
            result=result
        )

    except json.JSONDecodeError as e:
        logging.error(f"节点数据JSON解析错误: {str(e)}")
        raise HTTPException(status_code=400, detail="节点数据格式错误，应为JSON格式")
    except Exception as e:
        logging.error(f"执行工作流 '{workflow_id}' 失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"执行工作流失败: {str(e)}")


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