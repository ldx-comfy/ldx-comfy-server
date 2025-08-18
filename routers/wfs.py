from typing import List
from fastapi import APIRouter
from pydantic import BaseModel, Field
from comfy import get_wfs

router = APIRouter(prefix="/api/v1/workflows", tags=["工作流"])

class WorkflowParam(BaseModel):
    node_id: str = Field(..., description="节点ID")
    title: str = Field(..., description="节点标题")
    class_type: str = Field(..., description="节点类型")

@router.get("/list", response_model=List[str])
def get_workflow_list():
    """获取所有WorkFlow列表:./wf_fils/*.json
    """
    return get_wfs.get_wf_list()

@router.get("/wf/{wf_id}/params", response_model=List[WorkflowParam])
def get_wf_params(wf_id: str):
    """获取指定WorkFlow需要的参数列表
    """
    return get_wfs.get_wf_params(wf_id)
