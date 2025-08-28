"""
工作流执行器插件实现
"""
import os
import sys
import websocket
import uuid
import json
import urllib.request
import urllib.parse
from typing import Dict, Any, List, Optional
from .base import WorkflowExecutorPlugin, PluginMetadata
from ..get_wfs import get_wf


class ComfyUIWorkflowExecutor(WorkflowExecutorPlugin):
    """ComfyUI工作流执行器插件"""

    def __init__(self):
        self.server_address = "106.52.220.169:6889"
        self.client_id = str(uuid.uuid4())
        self.output_dir = "comfy_out_image"
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
        from .node_handlers import ImageInputHandler, TextInputHandler, SwitchInputHandler

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

            if node_type == 'LoadImageOutput':
                result = image_handler.handle_node(node_id, node_info, **node_inputs)
            elif node_type == 'Text':
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
        # 队列工作流
        prompt_id = self._queue_prompt(workflow_data)['prompt_id']

        # 创建WebSocket连接
        ws = websocket.WebSocket()
        ws.connect(f"ws://{self.server_address}/ws?clientId={self.client_id}")

        output_images = []

        try:
            # 等待执行完成
            while True:
                out = ws.recv()
                if isinstance(out, str):
                    message = json.loads(out)
                    if message['type'] == 'executing':
                        data = message['data']
                        if data['node'] is None and data['prompt_id'] == prompt_id:
                            break  # 执行完成

            # 获取结果
            history = self._get_history(prompt_id)[prompt_id]
            for node_id in history['outputs']:
                node_output = history['outputs'][node_id]
                if 'images' in node_output:
                    for image in node_output['images']:
                        filepath = self._get_image(image['filename'], image['subfolder'], image['type'])
                        output_images.append(filepath)

        finally:
            ws.close()

        return output_images

    def _queue_prompt(self, prompt: Dict[str, Any]) -> Dict[str, Any]:
        """将工作流加入队列"""
        p = {"prompt": prompt, "client_id": self.client_id}
        data = json.dumps(p).encode('utf-8')
        req = urllib.request.Request(f"http://{self.server_address}/prompt", data=data)
        return json.loads(urllib.request.urlopen(req).read())

    def _get_image(self, filename: str, subfolder: str, folder_type: str) -> str:
        """下载图像"""
        os.makedirs(self.output_dir, exist_ok=True)
        filepath = os.path.join(self.output_dir, filename)

        data = {"filename": filename, "subfolder": subfolder, "type": folder_type}
        url_values = urllib.parse.urlencode(data)
        with urllib.request.urlopen(f"http://{self.server_address}/view?{url_values}") as response:
            with open(filepath, 'wb') as f:
                f.write(response.read())
        return filepath

    def _get_history(self, prompt_id: str) -> Dict[str, Any]:
        """获取执行历史"""
        with urllib.request.urlopen(f"http://{self.server_address}/history/{prompt_id}") as response:
            return json.loads(response.read())


# 导出执行器
__all__ = ['ComfyUIWorkflowExecutor']