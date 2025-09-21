#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
日志配置模块
"""

import logging
import logging.handlers
import os
from datetime import datetime

from typing import Optional

def setup_logger(name: str = "root", log_level: str = "INFO", log_file: Optional[str] = None, max_size: int = 10485760, backup_count: int = 5) -> logging.Logger:
    """
    设置日志系统并返回logger实例
    
    Args:
        name: logger名称
        log_level: 日志级别
        log_file: 日志文件路径
        max_size: 日志文件最大大小
        backup_count: 备份文件数量
        
    Returns:
        logging.Logger实例
    """
    # 确保日志目录存在
    if log_file:
        log_dir = os.path.dirname(log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
    
    # 设置日志级别
    level = getattr(logging, log_level.upper(), logging.INFO)
    
    # 创建格式化器
    formatter = logging.Formatter(
        fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # 获取或创建logger
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # 清除现有的处理器
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # 文件处理器（如果指定了日志文件）
    if log_file:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file, 
            maxBytes=max_size, 
            backupCount=backup_count,
            encoding='utf-8'
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    # 设置第三方库的日志级别
    logging.getLogger('requests').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('PIL').setLevel(logging.WARNING)
    
    return logger