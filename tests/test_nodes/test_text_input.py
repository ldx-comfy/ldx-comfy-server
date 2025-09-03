import pytest
import comfy.nodes.text_input as text_input


@pytest.fixture
def node_info():
    return {"_meta": {"title": "Text Input"}}


def test_handle_text_node_is_callable():
    assert callable(text_input.handle_text_node)


def test_handle_text_node_returns_text_and_prompt_contains_title(monkeypatch, node_info):
    captured = {}

    def fake_input(prompt: str):
        captured["prompt"] = prompt
        return "hello world"

    monkeypatch.setattr("builtins.input", fake_input)

    result = text_input.handle_text_node("node1", node_info)
    assert result == {"text": "hello world"}
    assert "Text Input" in captured["prompt"]


def test_handle_text_node_empty_text(monkeypatch, node_info):
    monkeypatch.setattr("builtins.input", lambda prompt: "")
    result = text_input.handle_text_node("node1", node_info)
    assert result == {"text": ""}


def test_handle_text_node_long_text(monkeypatch, node_info):
    long_text = "a" * 5000
    monkeypatch.setattr("builtins.input", lambda prompt: long_text)
    result = text_input.handle_text_node("node1", node_info)
    assert result["text"] == long_text
    assert len(result["text"]) == 5000


def test_handle_text_node_missing_meta_raises_keyerror(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda prompt: "anything")
    with pytest.raises(KeyError):
        text_input.handle_text_node("node1", {})
    with pytest.raises(KeyError):
        text_input.handle_text_node("node1", {"_meta": {}})