import pytest
import comfy.nodes.switch_any as switch_any

@pytest.fixture
def node_info():
    return {"_meta": {"title": "Switch Input"}}

def test_handle_switch_node_is_callable():
    assert callable(switch_any.handle_switch_node)

def test_handle_switch_node_true_lower(monkeypatch, node_info):
    monkeypatch.setattr("builtins.input", lambda prompt: "true")
    result = switch_any.handle_switch_node("n1", node_info)
    assert result == {"boolean": True}

def test_handle_switch_node_true_upper(monkeypatch, node_info):
    monkeypatch.setattr("builtins.input", lambda prompt: "TRUE")
    result = switch_any.handle_switch_node("n1", node_info)
    assert result == {"boolean": True}

def test_handle_switch_node_false_lower(monkeypatch, node_info):
    monkeypatch.setattr("builtins.input", lambda prompt: "false")
    result = switch_any.handle_switch_node("n1", node_info)
    assert result == {"boolean": False}

def test_handle_switch_node_false_mixed_case(monkeypatch, node_info):
    monkeypatch.setattr("builtins.input", lambda prompt: "FalSe")
    result = switch_any.handle_switch_node("n1", node_info)
    assert result == {"boolean": False}

def test_handle_switch_node_unexpected_string_returns_false(monkeypatch, node_info):
    monkeypatch.setattr("builtins.input", lambda prompt: "yes")
    result = switch_any.handle_switch_node("n1", node_info)
    assert result == {"boolean": False}

def test_handle_switch_node_whitespace_not_trimmed(monkeypatch, node_info):
    # 由于实现未 strip，带空格字符串不会等于 'true'
    monkeypatch.setattr("builtins.input", lambda prompt: " true ")
    result = switch_any.handle_switch_node("n1", node_info)
    assert result == {"boolean": False}

def test_handle_switch_node_prompt_contains_title(monkeypatch, node_info):
    captured = {}
    def fake_input(prompt: str):
        captured["prompt"] = prompt
        return "true"
    monkeypatch.setattr("builtins.input", fake_input)
    _ = switch_any.handle_switch_node("n1", node_info)
    assert "Switch Input" in captured["prompt"]

def test_handle_switch_node_missing_meta_raises_keyerror(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda prompt: "true")
    with pytest.raises(KeyError):
        switch_any.handle_switch_node("n1", {})
    with pytest.raises(KeyError):
        switch_any.handle_switch_node("n1", {"_meta": {}})