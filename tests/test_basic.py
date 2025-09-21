#!/usr/bin/env python3
"""
基本功能测试
"""

import unittest
import sys
import os

# 添加src目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


class TestBasicFunctionality(unittest.TestCase):
    """基本功能测试类"""
    
    def test_imports(self):
        """测试基本导入"""
        try:
            import core.config
            import core.downloader
            import core.parser
            import utils.logger
            self.assertTrue(True, "所有模块导入成功")
        except ImportError as e:
            self.fail(f"模块导入失败: {e}")
    
    def test_config_loading(self):
        """测试配置加载"""
        try:
            from core.config import ConfigManager
            config_manager = ConfigManager()
            self.assertIsNotNone(config_manager)
        except Exception as e:
            self.fail(f"配置加载失败: {e}")


if __name__ == '__main__':
    unittest.main()
