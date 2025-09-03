import os
import json
import pytest

from comfy.get_wfs import get_wf_list, get_wf, get_wf_params


# --------------------------- get_wf_list ---------------------------

def test_get_wf_list_returns_empty_when_dir_missing(tmp_path, monkeypatch):
    """当目录不存在时返回空列表"""
    import comfy.get_wfs as get_wfs_mod
    missing_dir = tmp_path / "missing"
    assert not missing_dir.exists()
    monkeypatch.setattr(get_wfs_mod, "_wf_files_dir", str(missing_dir))
    assert get_wf_list() == []


def test_get_wf_list_filters_json_only(patch_wf_dir, tmp_workflows_dir, make_wf):
    """仅返回 .json（区分大小写）文件的名字（去掉扩展名）"""
    make_wf("a", {"1": {"class_type": "X", "_meta": {"title": "A"}}})
    (tmp_workflows_dir / "b.txt").write_text("not json", encoding="utf-8")
    (tmp_workflows_dir / "C.JSON").write_text("{}", encoding="utf-8")  # 不应被识别（大小写）
    wfs = get_wf_list()
    assert isinstance(wfs, list)
    assert set(wfs) == {"a"}


# ----------------------------- get_wf -----------------------------

def test_get_wf_returns_parsed_dict(patch_wf_dir, make_wf):
    """能正确读取并解析指定工作流"""
    content = {
        "10": {"class_type": "Text", "_meta": {"title": "Name-Input"}}
    }
    make_wf("demo", content)
    wf = get_wf("demo")
    assert isinstance(wf, dict)
    assert "10" in wf
    assert wf["10"]["class_type"] == "Text"


def test_get_wf_raises_when_not_found(patch_wf_dir):
    """文件不存在时抛出 FileNotFoundError"""
    with pytest.raises(FileNotFoundError):
        get_wf("no_such_workflow")


def test_get_wf_raises_on_invalid_json(patch_wf_dir, tmp_workflows_dir):
    """JSON 无法解析时抛出 JSONDecodeError"""
    bad = tmp_workflows_dir / "bad.json"
    bad.write_text("{ invalid json", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        get_wf("bad")


# -------------------------- get_wf_params --------------------------

def test_get_wf_params_extracts_inputs(patch_wf_dir, make_wf):
    """
    能解析带 '-Input' 标题的节点，并正确去掉后缀，返回 node_id/title/class_type
    """
    content = {
        "10": {"class_type": "Text", "_meta": {"title": "Name-Input"}},
        "11": {"class_type": "LoadImageOutput", "_meta": {"title": "输入原图-Input"}},
        "12": {"class_type": "Other"},  # 无 _meta，忽略
        "13": {"class_type": "FluxGuidance", "_meta": {"title": "FluxGuidance"}},  # 非 Input，忽略
    }
    make_wf("params_demo", content)
    params = get_wf_params("params_demo")
    assert isinstance(params, list)
    assert len(params) == 2

    ids = {p["node_id"] for p in params}
    assert ids == {"10", "11"}

    titles_by_id = {p["node_id"]: p["title"] for p in params}
    classes_by_id = {p["node_id"]: p["class_type"] for p in params}
    assert titles_by_id["10"] == "Name"
    assert classes_by_id["10"] == "Text"
    assert titles_by_id["11"] == "输入原图"
    assert classes_by_id["11"] == "LoadImageOutput"


def test_get_wf_params_returns_empty_when_no_input(patch_wf_dir, make_wf):
    """当没有任何 *-Input 节点时返回空列表"""
    content = {
        "1": {"class_type": "A", "_meta": {"title": "A"}},
        "2": {"class_type": "B"},
    }
    make_wf("no_input", content)
    assert get_wf_params("no_input") == []


def test_get_wf_params_ignores_nodes_without_meta(patch_wf_dir, make_wf):
    """缺少 _meta 或 title 字段的节点应被忽略"""
    content = {
        "1": {"class_type": "X"},  # 无 _meta
        "2": {"class_type": "Y", "_meta": {}},  # 无 title
        "3": {"class_type": "Z", "_meta": {"title": "Z-Input"}},  # 合法
    }
    make_wf("partial_meta", content)
    params = get_wf_params("partial_meta")
    assert len(params) == 1
    assert params[0]["node_id"] == "3"
    assert params[0]["title"] == "Z"
    assert params[0]["class_type"] == "Z"
