def handle_switch_node(node_id, node_info):
    """处理开关节点"""
    title = node_info['_meta']['title']
    boolean_value = input(f"请输入节点 '{title}' 的布尔值 (true/false): ")
    return {'boolean': boolean_value.lower() == 'true'}