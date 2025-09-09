import os
import requests
from logging_config import get_colorful_logger

# 配置彩色日志
logger = get_colorful_logger(__name__)

def handle_image_node(node_id, node_info, server_address):
    """处理图像输入节点"""
    title = node_info['_meta']['title']
    image_path = input(f"请输入节点 '{title}' 的本地图像路径: ")

    logger.info(f"正在上传图片到服务器: {image_path}")
    try:
        with open(image_path, 'rb') as f:
            files = {'image': (os.path.basename(image_path), f)}
            response = requests.post(f"http://{server_address}/upload/image", files=files)

        if response.status_code == 200:
            result = response.json()
            server_path = f"{result['name']} [input]"
            logger.info(f"图片已上传到服务器: {server_path}")
            return {'image': server_path}
        else:
            logger.error(f"上传失败: {response.status_code} - {response.text}")
            return {'image': image_path}
    except Exception as e:
        logger.error(f"上传出错: {str(e)}")
        return {'image': image_path}