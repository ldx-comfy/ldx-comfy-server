"""
节点处理器插件实现
"""
import os
import requests
from typing import Dict, Any, List
from .base import NodeHandlerPlugin, PluginMetadata
from logging_config import get_colorful_logger

# 配置彩色日志
logger = get_colorful_logger(__name__)


class ImageInputHandler(NodeHandlerPlugin):
    """图像输入处理器插件"""

    def __init__(self):
        self.server_address = "106.52.220.169:6889"

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="image_input_handler",
            version="1.0.0",
            description="处理图像输入节点",
            author="yinghao",
            plugin_type="node_handler"
        )

    def initialize(self, config: Dict[str, Any]) -> None:
        """初始化插件"""
        self.server_address = config.get('server_address', self.server_address)

    def cleanup(self) -> None:
        """清理资源"""
        pass

    def can_handle(self, node_type: str) -> bool:
        """判断是否能处理指定类型的节点"""
        return node_type == "LoadImageOutput"

    def handle_node(self, node_id: str, node_info: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """处理图像输入节点"""
        logger.debug(f"开始处理图像输入节点: node_id={node_id}, node_info={node_info}, kwargs={kwargs}")
        title = node_info['_meta']['title']
        image_path = kwargs.get('image_path')

        if not image_path:
            logger.warning(f"节点 '{title}' 缺少 image_path 参数")
            raise ValueError(f"节点 '{title}' 需要提供 image_path 参数")

        logger.info(f"正在上传图片到服务器: {image_path}")

        try:
            with open(image_path, 'rb') as f:
                files = {'image': (os.path.basename(image_path), f)}
                response = requests.post(f"http://{self.server_address}/upload/image", files=files)

            if response.status_code == 200:
                result = response.json()
                server_path = f"{result['name']} [input]"
                logger.info(f"图片已上传到服务器: {server_path}")
                logger.debug(f"上传成功响应: {result}")
                return {'image': server_path}
            else:
                logger.error(f"上传失败: {response.status_code} - {response.text}")
                logger.debug(f"上传失败响应: {response.text}")
                return {'image': image_path}
        except Exception as e:
            logger.error(f"上传出错: {str(e)}")
            logger.debug(f"上传异常详情: {e}", exc_info=True)
            return {'image': image_path}
    def get_required_inputs(self) -> List[str]:
        """获取所需输入参数"""
        return ['image_path']


class TextInputHandler(NodeHandlerPlugin):
    """文本输入处理器插件"""

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="text_input_handler",
            version="1.0.0",
            description="处理文本输入节点",
            author="yinghao",
            plugin_type="node_handler"
        )

    def initialize(self, config: Dict[str, Any]) -> None:
        """初始化插件"""
        pass

    def cleanup(self) -> None:
        """清理资源"""
        pass

    def can_handle(self, node_type: str) -> bool:
        """判断是否能处理指定类型的节点"""
        return node_type == "Text"

    def handle_node(self, node_id: str, node_info: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """处理文本输入节点"""
        text = kwargs.get('text')
        if text is None:
            raise ValueError("文本输入节点需要提供 text 参数")
        return {'text': text}

    def get_required_inputs(self) -> List[str]:
        """获取所需输入参数"""
        return ['text']


class SwitchInputHandler(NodeHandlerPlugin):
    """开关输入处理器插件"""

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="switch_input_handler",
            version="1.0.0",
            description="处理开关输入节点",
            author="yinghao",
            plugin_type="node_handler"
        )

    def initialize(self, config: Dict[str, Any]) -> None:
        """初始化插件"""
        pass

    def cleanup(self) -> None:
        """清理资源"""
        pass

    def can_handle(self, node_type: str) -> bool:
        """判断是否能处理指定类型的节点"""
        return node_type == "Switch any [Crystools]"

    def handle_node(self, node_id: str, node_info: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """处理开关输入节点"""
        boolean_value = kwargs.get('boolean')
        if boolean_value is None:
            raise ValueError("开关输入节点需要提供 boolean 参数")

        # 转换字符串为布尔值
        if isinstance(boolean_value, str):
            boolean_value = boolean_value.lower() == 'true'

        return {'boolean': boolean_value}

    def get_required_inputs(self) -> List[str]:
        """获取所需输入参数"""
        return ['boolean']


# 导出所有处理器
__all__ = [
    'ImageInputHandler',
    'TextInputHandler',
    'SwitchInputHandler'
]