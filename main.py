#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
图片批量下载程序 - 主程序入口
支持批量下载网页中的图片，自动创建目录结构，多线程下载，进度显示等功能
"""

import sys
import os
import tkinter as tk
from tkinter import ttk
import logging
from datetime import datetime

# 添加项目路径到sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.gui.main_window import MainWindow
from src.core.config import Config
from src.utils.logger import setup_logger

def main():
    """主程序入口"""
    try:
        # 初始化配置
        config = Config()
        
        # 设置日志（传入日志文件路径）
        log_file = config.get('log_file')
        setup_logger(
            name=__name__,
            log_level=config.get('log_level', 'INFO'),
            log_file=log_file,
            max_size=config.get('log_max_size', 10485760),
            backup_count=config.get('log_backup_count', 5)
        )
        logger = logging.getLogger(__name__)
        
        logger.info("程序启动")
        logger.info(f"工作目录: {os.getcwd()}")
        logger.info(f"日志文件: {log_file}")
        
        # 创建主窗口
        root = tk.Tk()
        app = MainWindow(root, config)
        
        # 启动GUI
        root.mainloop()
        
    except Exception as e:
        print(f"程序启动失败: {e}")
        logging.error(f"程序启动失败: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()