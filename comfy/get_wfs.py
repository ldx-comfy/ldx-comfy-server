# 从./wf_files目录下获取所有工作流文件
import os
import json
from logging_config import get_colorful_logger

# 配置彩色日志
logger = get_colorful_logger(__name__)

# 获取此文件所在的目录，并构建到 `wf_files` 目录的绝对路径
_current_dir = os.path.dirname(os.path.abspath(__file__))
_wf_files_dir = os.path.join(_current_dir, '..', 'wf_files')

def get_wf_list():
    """
    获取所有工作流文件列表
    """
    wf_list = []
    # 确保 `wf_files` 目录存在
    if not os.path.isdir(_wf_files_dir):
        logger.warning(f"警告: 工作流目录 '{_wf_files_dir}' 未找到。")
        return []
        
    for file in os.listdir(_wf_files_dir):
        if file.endswith('.json'):
            wf_list.append(file[:-5])
    return wf_list

def get_wf(wf_id: str) -> dict:
    """
    获取指定工作流文件的内容
    
    Args:
        wf_id (str): 工作流文件名 (不带 .json 扩展名).
    
    Returns:
        dict: 工作流内容的字典.
    """
    wf_path = os.path.join(_wf_files_dir, wf_id + '.json')
    try:
        with open(wf_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error(f"错误: 工作流文件 '{wf_path}' 未找到。")
        raise
    except json.JSONDecodeError as e:
        logger.error(f"错误: 解析工作流文件 '{wf_path}' 时出错: {e}")
        raise

def get_wf_params(wf_id: str) -> list:
    """
    获取指定工作流的输入参数列表。
    参照 `run_wf.py` 的 `find_input_nodes` 实现。

    Args:
        wf_id (str): 工作流文件名 (不带 .json 扩展名).

    Returns:
        list: 包含输入参数信息的字典列表.
              每个字典包含: 'node_id', 'title', 'class_type'
    """
    wf_content = get_wf(wf_id)
    
    params = []
    for node_id, node_info in wf_content.items():
        if '_meta' in node_info and 'title' in node_info['_meta']:
            title = node_info['_meta']['title']
            if title.endswith('Input'):
                param_info = {
                    'node_id': node_id,
                    'title': title.replace('-Input', '').strip(),
                    'class_type': node_info['class_type']
                }
                params.append(param_info)
    return params


if __name__ == '__main__':
    # 用于直接测试此模块
    print("可用工作流:")
    workflows = get_wf_list()
    print(workflows)
    
    # 测试加载一个工作流
    if "test" in workflows:
        print("\n测试加载 'test' 工作流:")
        try:
            wf_content = get_wf('test')
            print("加载成功！")
        except Exception as e:
            print(f"加载失败: {e}")

        print("\n测试获取 'test' 工作流的参数:")
        try:
            params = get_wf_params('test')
            print("获取参数成功！")
            import pprint
            pprint.pprint(params)
        except Exception as e:
            print(f"获取参数失败: {e}")