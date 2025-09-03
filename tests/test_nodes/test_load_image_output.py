import os
import pytest
import comfy.nodes.load_image_output as load_image_output

@pytest.fixture
def tmp_image_file(tmp_path):
    p = tmp_path / "sample.png"
    p.write_bytes(b"\x89PNG\r\n\x1a\n")
    return str(p)

@pytest.fixture
def server_address():
    return "localhost:1234"

@pytest.fixture
def post_spy(monkeypatch):
    """
    提供一个可配置的 requests.post 替身，并记录调用参数
    """
    calls = {"count": 0, "url": None, "files": None}

    class DummyResponse:
        def __init__(self, status_code=200, json_data=None, text=""):
            self.status_code = status_code
            self._json = json_data or {}
            self.text = text
        def json(self):
            return self._json

    def make_post(status_code=200, name="uploaded"):
        def _post(url, files):
            calls["count"] += 1
            calls["url"] = url
            calls["files"] = files
            return DummyResponse(status_code, {"name": name}, text="error" if status_code != 200 else "")
        return _post

    return calls, make_post

def test_handle_image_node_success_upload(tmp_image_file, server_address, post_spy, monkeypatch):
    calls, make_post = post_spy
    # mock input 和网络请求
    monkeypatch.setattr(load_image_output.requests, "post", make_post(200, "server_file"))
    monkeypatch.setattr("builtins.input", lambda prompt: tmp_image_file)

    node_info = {"_meta": {"title": "输入原图-Input"}, "inputs": {}}
    result = load_image_output.handle_image_node("1", node_info, server_address)

    assert result == {"image": "server_file [input]"}
    assert calls["count"] == 1
    assert calls["url"] == f"http://{server_address}/upload/image"
    assert "image" in calls["files"]
    fname, fobj = calls["files"]["image"]
    assert fname == os.path.basename(tmp_image_file)

def test_handle_image_node_upload_failure_returns_local_path(tmp_image_file, server_address, post_spy, monkeypatch):
    calls, make_post = post_spy
    monkeypatch.setattr(load_image_output.requests, "post", make_post(500, "ignored"))
    monkeypatch.setattr("builtins.input", lambda prompt: tmp_image_file)

    node_info = {"_meta": {"title": "输入原图-Input"}, "inputs": {}}
    result = load_image_output.handle_image_node("1", node_info, server_address)

    assert result == {"image": tmp_image_file}
    assert calls["count"] == 1

def test_handle_image_node_file_not_found_returns_path_and_no_post(server_address, post_spy, monkeypatch):
    calls, make_post = post_spy
    missing_path = "/no/such/dir/nonexistent.png"
    monkeypatch.setattr(load_image_output.requests, "post", make_post(200, "server_file"))
    monkeypatch.setattr("builtins.input", lambda prompt: missing_path)

    node_info = {"_meta": {"title": "输入原图-Input"}, "inputs": {}}
    result = load_image_output.handle_image_node("1", node_info, server_address)

    assert result == {"image": missing_path}
    assert calls["count"] == 0  # 打开文件失败前就返回，post 不应被调用

def test_handle_image_node_invalid_node_info_raises_keyerror(server_address):
    with pytest.raises(KeyError):
        load_image_output.handle_image_node("1", {}, server_address)