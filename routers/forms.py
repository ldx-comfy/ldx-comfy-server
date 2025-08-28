"""
表单式API路由
"""
from typing import Dict, Any, List, Optional
import json
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from pydantic import BaseModel, Field
from comfy.plugins import plugin_manager
from comfy.get_wfs import get_wf_list, get_wf_params, get_wf


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
    return get_wf_list()


@router.get("/workflows/{workflow_id}/form-schema")
async def get_workflow_form_schema(workflow_id: str):
    """获取工作流表单模式"""
    try:
        params = get_wf_params(workflow_id)
        workflow_data = get_wf(workflow_id)

        # 构建表单模式
        form_schema = {
            "workflow_id": workflow_id,
            "title": f"工作流: {workflow_id}",
            "fields": []
        }

        for param in params:
            field = {
                "node_id": param["node_id"],
                "title": param["title"],
                "class_type": param["class_type"],
                "type": _get_field_type(param["class_type"]),
                "required": True
            }
            form_schema["fields"].append(field)

        return form_schema

    except Exception as e:
        raise HTTPException(status_code=404, detail=f"获取工作流 '{workflow_id}' 表单模式失败: {str(e)}")


@router.post("/workflows/{workflow_id}/execute", response_model=WorkflowExecutionResponse)
async def execute_workflow_with_form(
    workflow_id: str,
    nodes: str = Form(..., description="节点数据，格式: [{node},{node}, ...]")
):
    """通过表单执行工作流"""
    try:
        # 获取工作流数据
        workflow_data = get_wf(workflow_id)

        # 解析节点数据
        nodes_data = json.loads(nodes)

        # 构建输入参数
        inputs = {}
        for node in nodes_data:
            node_id = node.get("node_id")
            value = node.get("value", "")
            if node_id:
                inputs[node_id] = value

        # 获取工作流执行器
        executor = plugin_manager.get_workflow_executor()

        # 执行工作流（节点内容交由插件处理）
        result = executor.execute_workflow(workflow_data, inputs)

        return WorkflowExecutionResponse(
            execution_id=result["execution_id"],
            status=result["status"],
            result=result
        )

    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="节点数据格式错误，应为JSON格式")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"执行工作流失败: {str(e)}")


@router.get("/executions/{execution_id}/status", response_model=WorkflowExecutionResponse)
async def get_execution_status(execution_id: str):
    """获取执行状态"""
    try:
        executor = plugin_manager.get_workflow_executor()
        status = executor.get_execution_status(execution_id)

        return WorkflowExecutionResponse(
            execution_id=execution_id,
            status=status["status"],
            result=status.get("result"),
            error=status.get("error")
        )

    except Exception as e:
        raise HTTPException(status_code=404, detail=f"获取执行状态失败: {str(e)}")


@router.delete("/executions/{execution_id}")
async def cancel_execution(execution_id: str):
    """取消执行"""
    try:
        executor = plugin_manager.get_workflow_executor()
        success = executor.cancel_execution(execution_id)

        if success:
            return {"message": f"执行 '{execution_id}' 已取消"}
        else:
            raise HTTPException(status_code=400, detail="无法取消执行")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"取消执行失败: {str(e)}")


def _get_field_type(class_type: str) -> str:
    """根据节点类型获取表单字段类型"""
    type_mapping = {
        "LoadImageOutput": "file",
        "Text": "text",
        "Switch any [Crystools]": "boolean"
    }
    return type_mapping.get(class_type, "text")