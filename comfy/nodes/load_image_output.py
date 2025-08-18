import os
import requests

def handle_image_node(node_id, node_info, server_address):
    """处理图像输入节点"""
    title = node_info['_meta']['title']
    image_path = input(f"请输入节点 '{title}' 的本地图像路径: ")
    
    print(f"正在上传图片到服务器: {image_path}")
    try:
        with open(image_path, 'rb') as f:
            files = {'image': (os.path.basename(image_path), f)}
            response = requests.post(f"http://{server_address}/upload/image", files=files)
        
        if response.status_code == 200:
            result = response.json()
            server_path = f"{result['name']} [input]"
            print(f"图片已上传到服务器: {server_path}")
            return {'image': server_path}
        else:
            print(f"上传失败: {response.status_code} - {response.text}")
            return {'image': image_path}
    except Exception as e:
        print(f"上传出错: {str(e)}")
        return {'image': image_path}