def handle_text_node(node_id, node_info):
    """处理文本输入节点"""
    title = node_info['_meta']['title']
    text = input(f"请输入节点 '{title}' 的文本: ")
    return {'text': text}