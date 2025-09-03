import os
import sys
import pytest
from comfy.logging_config import get_colorful_logger

# 确保项目根目录在 sys.path 中
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

@pytest.fixture(scope="session")
def logger():
    """提供一个带彩色格式的测试级别 logger"""
    return get_colorful_logger("tests")

# ============== 额外测试夹具（工作流相关） ==============

import pytest

@pytest.fixture
def tmp_workflows_dir(tmp_path):
    """
    提供一个临时的工作流目录（空目录）
    """
    d = tmp_path / "wf_files"
    d.mkdir()
    return d

@pytest.fixture
def make_wf(tmp_workflows_dir):
    """
    在临时工作流目录中创建工作流JSON文件的工厂方法
    使用方式:
        make_wf("demo", {"1": {"class_type": "X", "_meta": {"title": "Y"}}})
    """
    def _mk(name: str, content: dict):
        import json
        p = tmp_workflows_dir / f"{name}.json"
        p.write_text(json.dumps(content), encoding="utf-8")
        return p
    return _mk

@pytest.fixture
def patch_wf_dir(monkeypatch, tmp_workflows_dir):
    """
    将 comfy.get_wfs 模块内的 _wf_files_dir 指向到临时目录
    """
    import comfy.get_wfs as get_wfs
    monkeypatch.setattr(get_wfs, "_wf_files_dir", str(tmp_workflows_dir))
    return tmp_workflows_dir