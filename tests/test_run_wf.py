from comfy.run_wf import find_input_nodes

def test_find_input_nodes_extracts_by_title_suffix():
    prompt = {
        "1": {"_meta": {"title": "Text Input"}, "class_type": "Text", "inputs": {}},
        "2": {"_meta": {"title": "NoInput"}, "class_type": "Other", "inputs": {}},
        "abc": {"_meta": {"title": "Switch Input"}, "class_type": "Switch any [Crystools]", "inputs": {}},
    }
    nodes = find_input_nodes(prompt)
    assert nodes == {"1": "Text", "abc": "Switch any [Crystools]"}
