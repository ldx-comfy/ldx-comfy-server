from fastapi import APIRouter
from comfy import get_wfs

router = APIRouter(prefix="/api/v1/workflows", tags=["工作流"])

@router.get("/list")
def get_workflow_list():
    """获取所有WorkFlow列表:./wf_fils/*.json
    """
    return get_wfs.get_wf_list()
@router.get("/wf_params")
def get_wf_params(wf_id: str):
    """获取指定WorkFlow需要的参数列表
    """
    return get_wfs.get_wf_params(wf_id)
