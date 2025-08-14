import os
import sys
# 将当前文件所在目录添加到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import websocket
import uuid
import json
import urllib.request
import urllib.parse

# ComfyUI服务器地址
server_address = "42.194.228.252:6889"
# 客户端ID，用于标识连接
client_id = str(uuid.uuid4())
# 图像输出目录
output_dir = "comfy_out_image"

def find_input_nodes(prompt):
    """
    查找所有以 "Input" 结尾的节点
    
    Args:
        prompt (dict): 从JSON文件加载的工作流
        
    Returns:
        dict: 包含输入节点ID和类型的字典
    """
    input_nodes = {}
    for node_id, node_info in prompt.items():
        if '_meta' in node_info and 'title' in node_info['_meta']:
            title = node_info['_meta']['title']
            if title.endswith('Input'):
                input_nodes[node_id] = node_info['class_type']
    return input_nodes

def queue_prompt(prompt):
    """
    将工作流加入队列

    Args:
        prompt (dict): 从JSON文件加载的工作流

    Returns:
        dict: 服务器返回的响应
    """
    p = {"prompt": prompt, "client_id": client_id}
    data = json.dumps(p).encode('utf-8')
    req = urllib.request.Request(f"http://{server_address}/prompt", data=data)
    return json.loads(urllib.request.urlopen(req).read())

def get_image(filename, subfolder, folder_type):
    """
    从服务器下载生成的图像并返回文件路径

    Args:
        filename (str): 图像文件名
        subfolder (str): 子文件夹
        folder_type (str): 文件夹类型 (e.g., 'output')

    Returns:
        str: 保存的图像文件路径
    """
    # 确保输出目录存在
    os.makedirs(output_dir, exist_ok=True)
    filepath = os.path.join(output_dir, filename)
    
    data = {"filename": filename, "subfolder": subfolder, "type": folder_type}
    url_values = urllib.parse.urlencode(data)
    with urllib.request.urlopen(f"http://{server_address}/view?{url_values}") as response:
        with open(filepath, 'wb') as f:
            f.write(response.read())
    return filepath

def get_history(prompt_id):
    """
    获取指定prompt_id的执行历史

    Args:
        prompt_id (str): Prompt的ID

    Returns:
        dict: 包含执行历史的字典
    """
    with urllib.request.urlopen(f"http://{server_address}/history/{prompt_id}") as response:
        return json.loads(response.read())

def get_images(ws, prompt):
    """
    执行工作流并获取所有生成的图像路径

    Args:
        ws (websocket.WebSocketApp): WebSocket连接实例
        prompt (dict): 工作流

    Returns:
        list: 生成的图像路径列表
    """
    prompt_id = queue_prompt(prompt)['prompt_id']
    output_images = []

    while True:
        out = ws.recv()
        if isinstance(out, str):
            message = json.loads(out)
            if message['type'] == 'executing':
                data = message['data']
                if data['node'] is None and data['prompt_id'] == prompt_id:
                    break  # 执行完成
    
    history = get_history(prompt_id)[prompt_id]
    for node_id in history['outputs']:
        node_output = history['outputs'][node_id]
        if 'images' in node_output:
            for image in node_output['images']:
                filepath = get_image(image['filename'], image['subfolder'], image['type'])
                output_images.append(filepath)

    return output_images

def run_workflow(input_values=None):
    """
    执行工作流并返回生成的图像路径
    
    Args:
        input_values (dict): 输入节点ID到输入值的映射
    """
    try:
        with open('workflow_api.json', 'r', encoding='utf-8') as f:
            prompt = json.load(f)
    except FileNotFoundError:
        print("错误: 'workflow_api.json' 未找到。")
        return []
    except json.JSONDecodeError as e:
        print(f"JSON解析错误: {str(e)}")
        return []
    
    # 查找所有以 "Input" 结尾的节点
    input_nodes = find_input_nodes(prompt)
    
    # 如果有提供输入值，直接使用它们
    if input_values:
        for node_id, value in input_values.items():
            if node_id in prompt:
                # 根据节点类型处理输入值
                node_type = prompt[node_id]['class_type']
                if node_type == 'Text':
                    prompt[node_id]['inputs']['text'] = value
                elif node_type == 'Switch any [Crystools]':
                    prompt[node_id]['inputs']['select'] = value
                elif node_type == 'LoadImageOutput':
                    # 图像输入需要特殊处理
                    prompt[node_id]['inputs']['image'] = value
                else:
                    # 默认处理方式
                    for input_key in prompt[node_id]['inputs']:
                        if 'text' in input_key:
                            prompt[node_id]['inputs'][input_key] = value
    else:
        # 导入节点处理器
        from comfy.nodes import handle_image_node, handle_text_node, handle_switch_node
        
        # 节点类型到处理函数的映射
        node_handlers = {
            'LoadImageOutput': handle_image_node,
            'Text': handle_text_node,
            'Switch any [Crystools]': handle_switch_node
        }
        
        # 处理输入节点
        for node_id, node_type in input_nodes.items():
            handler = node_handlers.get(node_type)
            
            if handler:
                if node_type == 'LoadImageOutput':
                    # 从input_values中获取图像数据（如果存在）
                    image_data = input_values.get(node_id) if input_values else None
                    result = handler(node_id, prompt[node_id], server_address, image_data)
                else:
                    # 对于其他节点类型，直接处理
                    result = handler(node_id, prompt[node_id])
                
                for key, value in result.items():
                    prompt[node_id]['inputs'][key] = value
            else:
                print(f"警告: 未知的输入节点类型 '{node_type}'")

    try:
        ws = websocket.WebSocket()
        ws.connect(f"ws://{server_address}/ws?clientId={client_id}")
        
        print("正在执行工作流...")
        images = get_images(ws, prompt)
        print("工作流执行完毕，图像已保存。")
        
        ws.close()
        return images
    except Exception as e:
        print(f"工作流执行错误: {str(e)}")
        import traceback
        traceback.print_exc()
        return []

def main():
    run_workflow()
if __name__ == "__main__":
    # 安装依赖: pip install websocket-client
    main()