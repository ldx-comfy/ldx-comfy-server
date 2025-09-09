"""
工作流执行器插件实现
"""
import os
import sys
import websocket
import uuid
import json
import httpx
from typing import Dict, Any, List, Optional
from .base import WorkflowExecutorPlugin, PluginMetadata
from ..get_wfs import get_wf
import config
import logging
from .node_handlers import ImageInputHandler, TextInputHandler, SwitchInputHandler

class ComfyUIWorkflowExecutor(WorkflowExecutorPlugin):
    """ComfyUI工作流执行器插件"""

    def __init__(self):
        self.server_address = "106.52.220.169:6889"
        self.client_id = str(uuid.uuid4())
        self.output_dir = config.COMFY_OUTPUT_DIR
        self._active_executions: Dict[str, Dict[str, Any]] = {}

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="comfyui_workflow_executor",
            version="1.0.0",
            description="ComfyUI工作流执行器",
            author="yinghao",
            plugin_type="workflow_executor"
        )

    def initialize(self, config: Dict[str, Any]) -> None:
        """初始化插件"""
        self.server_address = config.get('server_address', self.server_address)
        self.output_dir = config.get('output_dir', self.output_dir)
        os.makedirs(self.output_dir, exist_ok=True)

        # 支持通过配置覆盖超时，值为 0/None/"none" 表示不设置超时（无限等待）
        def _coerce_timeout(val, current):
            try:
                if val is None:
                    return None
                sval = str(val).strip().lower()
                if sval in ("0", "none", "null", ""):
                    return None
                return float(val)
            except Exception:
                return current

        self.ws_timeout = _coerce_timeout(config.get('ws_timeout'), 30.0)
        self.http_timeout = _coerce_timeout(config.get('http_timeout'), 30.0)

    def cleanup(self) -> None:
        """清理资源"""
        self._active_executions.clear()

    def execute_workflow(self, workflow_data: Dict[str, Any], inputs: Dict[str, Any]) -> Dict[str, Any]:
        """执行工作流"""
        execution_id = str(uuid.uuid4())

        # 存储执行信息
        self._active_executions[execution_id] = {
            'status': 'running',
            'workflow_data': workflow_data,
            'inputs': inputs,
            'start_time': None,
            'result': None
        }

        try:
            # 处理输入节点
            processed_workflow = self._process_inputs(workflow_data, inputs)

            # 执行工作流
            images = self._execute_on_comfyui(processed_workflow)

            # 更新执行状态
            self._active_executions[execution_id].update({
                'status': 'completed',
                'result': {
                    'images': images,
                    'execution_id': execution_id
                }
            })

            return {
                'execution_id': execution_id,
                'status': 'completed',
                'images': images
            }

        except Exception as e:
            # 更新执行状态为失败
            self._active_executions[execution_id].update({
                'status': 'failed',
                'error': str(e)
            })
            raise

    def get_execution_status(self, execution_id: str) -> Dict[str, Any]:
        """获取执行状态"""
        if execution_id not in self._active_executions:
            raise ValueError(f"执行ID '{execution_id}' 不存在")

        return self._active_executions[execution_id].copy()

    def cancel_execution(self, execution_id: str) -> bool:
        """取消执行"""
        if execution_id not in self._active_executions:
            return False

        execution_info = self._active_executions[execution_id]
        if execution_info['status'] == 'running':
            execution_info['status'] = 'cancelled'
            return True

        return False

    def _process_inputs(self, workflow_data: Dict[str, Any], inputs: Dict[str, Any]) -> Dict[str, Any]:
        """处理工作流输入"""
        

        # 创建处理器实例
        image_handler = ImageInputHandler()
        text_handler = TextInputHandler()
        switch_handler = SwitchInputHandler()

        # 初始化处理器
        image_handler.initialize({'server_address': self.server_address})

        # 查找输入节点
        input_nodes = self._find_input_nodes(workflow_data)

        # 复制工作流数据
        processed_workflow = json.loads(json.dumps(workflow_data))

        # 处理每个输入节点
        for node_id, node_type in input_nodes.items():
            node_info = processed_workflow[node_id]
            node_inputs = inputs.get(node_id, {})

            # 没有提供该节点的输入值则跳过，避免处理器抛出必填参数错误，保持workflow默认值
            if not node_inputs:
                continue

            # 校验必填键是否齐全
            required_keys = []
            if node_type == 'LoadImageOutput':
                required_keys = getattr(image_handler, 'get_required_inputs', lambda: [])()
            elif node_type == 'Text' or node_type == 'CLIPTextEncode' or ('CLIPTextEncode' in str(node_type)):
                required_keys = getattr(text_handler, 'get_required_inputs', lambda: [])()
            elif node_type == 'Switch any [Crystools]':
                required_keys = getattr(switch_handler, 'get_required_inputs', lambda: [])()
            # 如缺失必填输入，跳过该节点
            if required_keys and any(k not in node_inputs for k in required_keys):
                continue

            if node_type == 'LoadImageOutput':
                result = image_handler.handle_node(node_id, node_info, **node_inputs)
            elif node_type == 'Text' or node_type == 'CLIPTextEncode' or ('CLIPTextEncode' in str(node_type)):
                result = text_handler.handle_node(node_id, node_info, **node_inputs)
            elif node_type == 'Switch any [Crystools]':
                result = switch_handler.handle_node(node_id, node_info, **node_inputs)
            else:
                continue

            # 更新节点输入
            for key, value in result.items():
                if key in processed_workflow[node_id]['inputs']:
                    processed_workflow[node_id]['inputs'][key] = value

        return processed_workflow

    def _find_input_nodes(self, workflow_data: Dict[str, Any]) -> Dict[str, str]:
        """查找输入节点"""
        input_nodes = {}
        for node_id, node_info in workflow_data.items():
            if '_meta' in node_info and 'title' in node_info['_meta']:
                title = node_info['_meta']['title']
                if title.endswith('Input'):
                    input_nodes[node_id] = node_info['class_type']
        return input_nodes

    def _execute_on_comfyui(self, workflow_data: Dict[str, Any]) -> List[str]:
        """在ComfyUI上执行工作流"""
        logger = logging.getLogger(__name__)
        logger.info("开始在ComfyUI上执行工作流")
        # 队列工作流
        prompt_id = self._queue_prompt(workflow_data)['prompt_id']
        logger.info(f"工作流已加入队列，prompt_id: {prompt_id}")

        # 创建WebSocket连接
        ws = websocket.WebSocket()
        try:
            if self.ws_timeout is not None:
                ws.settimeout(self.ws_timeout)
                ws.connect(f"ws://{self.server_address}/ws?clientId={self.client_id}", timeout=self.ws_timeout)
            else:
                ws.settimeout(None)  # 无限超时
                ws.connect(f"ws://{self.server_address}/ws?clientId={self.client_id}")
        except Exception as e:
            logger.error(f"WebSocket连接失败: {str(e)}")
            raise

        output_images = []

        try:
            # 等待执行完成
            logger.info("开始等待工作流执行完成")
            while True:
                logger.debug("等待WebSocket消息")
                out = ws.recv()
                logger.debug(f"收到WebSocket消息: {out[:100]}...")  # 只显示前100个字符
                if isinstance(out, str):
                    message = json.loads(out)
                    logger.debug(f"解析消息类型: {message.get('type')}")
                    if message['type'] == 'executing':
                        data = message['data']
                        logger.debug(f"执行消息数据: {data}")
                        if data['node'] is None and data['prompt_id'] == prompt_id:
                            logger.info("工作流执行完成")
                            break  # 执行完成

            # 获取结果
            logger.info("开始获取执行结果")
            history = self._get_history(prompt_id)[prompt_id]
            logger.debug(f"获取到的历史记录: {list(history.keys())}")
            for node_id in history['outputs']:
                node_output = history['outputs'][node_id]
                logger.debug(f"处理节点 {node_id} 的输出")
                if 'images' in node_output:
                    logger.debug(f"节点 {node_id} 包含图片输出")
                    for image in node_output['images']:
                        logger.debug(f"处理图片: {image}")
                        filepath = self._get_image(image['filename'], image['subfolder'], image['type'])
                        output_images.append(filepath)
            logger.info(f"获取到 {len(output_images)} 张图片")

        finally:
            ws.close()

        return output_images

    def _queue_prompt(self, prompt: Dict[str, Any]) -> Dict[str, Any]:
        """将工作流加入队列"""
        p = {"prompt": prompt, "client_id": self.client_id}
        data = json.dumps(p)
        url = f"http://{self.server_address}/prompt"
        timeout = self.http_timeout if self.http_timeout is not None else 30.0
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(url, content=data, headers={"Content-Type": "application/json"})
            resp.raise_for_status()
            return resp.json()

    def _get_image(self, filename: str, subfolder: str, folder_type: str) -> str:
        """下载图像并返回base64编码的数据URL，同时保存图像文件"""
        import base64
        
        # 从ComfyUI服务器获取图像数据
        params = {"filename": filename, "subfolder": subfolder, "type": folder_type}
        url = f"http://{self.server_address}/view"
        timeout = self.http_timeout if self.http_timeout is not None else 30.0
        with httpx.Client(timeout=timeout) as client:
            response = client.get(url, params=params)
            response.raise_for_status()
            image_data = response.content
            
        # 保存图像文件
        filepath = os.path.join(config.COMFY_OUTPUT_DIR, filename)
        with open(filepath, 'wb') as f:
            f.write(image_data)
            
        # 将图像数据转换为base64编码
        encoded_image = base64.b64encode(image_data).decode('utf-8')
        
        # 根据内容类型确定数据URL前缀
        content_type = response.headers.get('content-type', 'image/png')
        data_url = f"data:{content_type};base64,{encoded_image}"
        
        return data_url

    def _get_history(self, prompt_id: str) -> Dict[str, Any]:
        """获取执行历史"""
        url = f"http://{self.server_address}/history/{prompt_id}"
        timeout = self.http_timeout if self.http_timeout is not None else 30.0
        with httpx.Client(timeout=timeout) as client:
            response = client.get(url)
            response.raise_for_status()
            return response.json()


# 导出执行器
__all__ = ['ComfyUIWorkflowExecutor']