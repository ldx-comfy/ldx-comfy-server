"""
tests.test_nodes package.

确保测试模块能正确导入项目根模块（comfy 等）。
"""
import os
import sys

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

__all__ = []
