# ComfyUI Web插件系统

这是一个基于插件架构设计的ComfyUI Web服务系统，支持动态加载和管理各种组件。

## 架构概述

### 核心组件

1. **插件基类** (`base.py`)
   - `Plugin`: 所有插件的基类
   - `NodeHandlerPlugin`: 节点处理器插件接口
   - `WorkflowExecutorPlugin`: 工作流执行器插件接口
   - `PluginRegistry`: 插件注册器

2. **插件管理器** (`manager.py`)
   - `PluginManager`: 负责插件的自动发现、注册和生命周期管理

3. **节点处理器** (`node_handlers.py`)
   - `ImageInputHandler`: 处理图像输入节点
   - `TextInputHandler`: 处理文本输入节点
   - `SwitchInputHandler`: 处理开关输入节点

4. **工作流执行器** (`workflow_executors.py`)
   - `ComfyUIWorkflowExecutor`: ComfyUI工作流执行器

## 使用方法

### 1. 插件开发

创建新的插件需要继承相应的基类：

```python
from comfy.plugins import NodeHandlerPlugin, PluginMetadata

class MyCustomHandler(NodeHandlerPlugin):
    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="my_custom_handler",
            version="1.0.0",
            description="自定义处理器",
            author="your_name",
            plugin_type="node_handler"
        )

    def can_handle(self, node_type: str) -> bool:
        return node_type == "MyCustomNode"

    def handle_node(self, node_id: str, node_info: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        # 处理逻辑
        return {"result": "processed"}
```

### 2. 插件注册

插件会自动发现和注册，也可以通过编程方式注册：

```python
from comfy.plugins import plugin_registry

plugin_registry.register_plugin(MyCustomHandler())
```

### 3. 使用插件

```python
from comfy.plugins import plugin_manager

# 获取节点处理器
handler = plugin_manager.get_node_handler("MyCustomNode")

# 获取工作流执行器
executor = plugin_manager.get_workflow_executor()
```

## API端点

### 表单式API

- `GET /api/v1/forms/workflows` - 获取可用工作流列表
- `GET /api/v1/forms/workflows/{workflow_id}/form-schema` - 获取工作流表单模式
- `POST /api/v1/forms/workflows/execute` - 执行工作流
- `GET /api/v1/forms/executions/{execution_id}/status` - 获取执行状态
- `DELETE /api/v1/forms/executions/{execution_id}` - 取消执行

### 传统API

- `GET /api/v1/workflows/list` - 获取工作流列表
- `GET /api/v1/workflows/wf/{wf_id}/params` - 获取工作流参数

## 配置

插件系统通过 `config.py` 进行配置：

```python
PLUGIN_CONFIG = {
    'server_address': '106.52.220.169:6889',
    'output_dir': 'comfy_out_image',
    # ... 其他配置
}
```

## 扩展点

### 添加新的节点处理器

1. 创建新的处理器类继承 `NodeHandlerPlugin`
2. 实现所需的方法
3. 将处理器放在 `comfy/plugins/node_handlers/` 目录下
4. 系统会自动发现和注册

### 添加新的工作流执行器

1. 创建新的执行器类继承 `WorkflowExecutorPlugin`
2. 实现所需的方法
3. 将执行器放在 `comfy/plugins/workflow_executors/` 目录下
4. 系统会自动发现和注册

## 优势

1. **模块化**: 各组件独立开发和部署
2. **可扩展性**: 易于添加新的处理器和执行器
3. **可配置性**: 通过配置文件调整行为
4. **自动发现**: 无需手动注册即可使用新插件
5. **类型安全**: 完整的类型注解支持

## 示例

查看 `comfy/plugins/node_handlers.py` 和 `comfy/plugins/workflow_executors.py` 中的实现示例。