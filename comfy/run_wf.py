import websocket
import uuid
import json
import urllib.request
import urllib.parse
import os
import requests

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
    从服务器下载生成的图像

    Args:
        filename (str): 图像文件名
        subfolder (str): 子文件夹
        folder_type (str): 文件夹类型 (e.g., 'output')
    """
    # 确保输出目录存在
    os.makedirs(output_dir, exist_ok=True)
    filepath = os.path.join(output_dir, filename)
    
    data = {"filename": filename, "subfolder": subfolder, "type": folder_type}
    url_values = urllib.parse.urlencode(data)
    with urllib.request.urlopen(f"http://{server_address}/view?{url_values}") as response:
        with open(filepath, 'wb') as f:
            f.write(response.read())

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
    执行工作流并获取所有生成的图像

    Args:
        ws (websocket.WebSocketApp): WebSocket连接实例
        prompt (dict): 工作流
    """
    prompt_id = queue_prompt(prompt)['prompt_id']
    output_images = {}

    while True:
        out = ws.recv()
        if isinstance(out, str):
            message = json.loads(out)
            if message['type'] == 'executing':
                data = message['data']
                if data['node'] is None and data['prompt_id'] == prompt_id:
                    break  # 执行完成
    
    history = get_history(prompt_id)[prompt_id]
    for o in history['outputs']:
        for node_id in history['outputs']:
            node_output = history['outputs'][node_id]
            if 'images' in node_output:
                images_output = []
                for image in node_output['images']:
                    image_data = get_image(image['filename'], image['subfolder'], image['type'])
                    images_output.append(image_data)
                output_images[node_id] = images_output

    return output_images

def main():
    """
    主函数
    """
    # 请将 "workflow_api.json" 替换为你的工作流API格式的JSON文件路径
    # 你可以通过在ComfyUI界面点击 "Save (API Format)" 来获取此文件
    try:
        with open('workflow_api.json', 'r', encoding='utf-8') as f:
            prompt = json.load(f)
    except FileNotFoundError:
        print("错误: 'workflow_api.json' 未找到。")
        print("请在ComfyUI中保存您的工作流 (Save (API Format)) 并将文件放在此脚本相同的目录下。")
        return
    
    # 查找所有以 "Input" 结尾的节点
    input_nodes = find_input_nodes(prompt)
    
    # 处理输入节点
    for node_id, node_type in input_nodes.items():
        title = prompt[node_id]['_meta']['title']
        if node_type == 'LoadImageOutput':
            # 图像输入节点（只接受用户本地路径）
            image_path = input(f"请输入节点 '{title}' 的本地图像路径: ")
            
            # 上传图片到服务器
            print(f"正在上传图片到服务器: {image_path}")
            try:
                with open(image_path, 'rb') as f:
                    files = {'image': (os.path.basename(image_path), f)}
                    response = requests.post(f"http://{server_address}/upload/image", files=files)
                
                if response.status_code == 200:
                    result = response.json()
                    # ComfyUI返回的路径格式为 "filename [type]"
                    server_path = f"{result['name']} [input]"
                    print(f"图片已上传到服务器: {server_path}")
                    prompt[node_id]['inputs']['image'] = server_path
                else:
                    print(f"上传失败: {response.status_code} - {response.text}")
                    # 上传失败时使用原始路径
                    prompt[node_id]['inputs']['image'] = image_path
            except Exception as e:
                print(f"上传出错: {str(e)}")
                # 出错时使用原始路径
                prompt[node_id]['inputs']['image'] = image_path
        elif node_type == 'Text':
            # 文本输入节点
            text = input(f"请输入节点 '{title}' 的文本: ")
            prompt[node_id]['inputs']['text'] = text
        elif node_type == 'Switch any [Crystools]':
            # 布尔值输入节点
            boolean_value = input(f"请输入节点 '{title}' 的布尔值 (true/false): ")
            prompt[node_id]['inputs']['boolean'] = boolean_value.lower() == 'true'
        else:
            print(f"警告: 未知的输入节点类型 '{node_type}'")

    ws = websocket.WebSocket()
    ws.connect(f"ws://{server_address}/ws?clientId={client_id}")
    
    print("正在执行工作流...")
    get_images(ws, prompt)
    print("工作流执行完毕，图像已保存。")
    
    ws.close()

if __name__ == "__main__":
    # 安装依赖: pip install websocket-client
    main()