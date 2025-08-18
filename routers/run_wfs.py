from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/workflow", tags=["工作流"])

@router.get("/list")
def get_workflow_list():
    """获取所有WorkFlow列表:./wf_fils/*.json
    """
@router.get("/wf_params")
def get_wf_params(wf_id):
    """获取指定WorkFlow需要的参数列表
    """
