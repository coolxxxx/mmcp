#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置管理模块
"""

import json
import os
from typing import Any, Optional

class Config:
    """配置管理类"""
    
    def __init__(self, config_file: str = "config.json"):
        """
        初始化配置
        
        Args:
            config_file: 配置文件路径
        """
        self.config_file = config_file
        self._config = self._load_default_config()
        self._load_config()
    
    def _load_default_config(self) -> dict[str, Any]:
        """加载默认配置"""
        return {
            # 下载设置
            "max_threads": 5,
            "timeout": 30,
            "retry_times": 3,
            "download_path": "./downloads",
            "chunk_size": 8192,
            
            # 图片过滤设置
            "image_filters": {
                "types": ["jpg", "jpeg", "png", "gif", "webp", "bmp"],
                "fast_filter": False,  # 快速过滤模式
                "quick_parse": False,  # 快速解析模式
                "min_size": 51200,  # 50KB
                "max_size": 10485760,  # 10MB
                "min_width": 800,  # 最小宽度800像素
                "min_height": 600,  # 最小高度600像素
                "enable_size_filter": True,  # 启用文件大小过滤
                "enable_resolution_filter": True,  # 启用分辨率过滤
                "resolution_check_mode": "smart",  # 分辨率检查模式: fast(跳过), smart(智能), always(总是)
                "parallel_filter": True,  # 启用并行过滤
                "filter_timeout": 3,  # 单个图片过滤超时时间(秒)
                
                # 装饰性图片过滤规则
                "decorative_patterns": [
                    # 明确的装饰元素
                    "logo", "icon", "btn", "button", "arrow",
                    "header", "footer", "nav", "menu", "sidebar",
                    "ad", "ads", "banner", "sponsor",
                    
                    # 常见的小图标
                    "close", "minimize", "maximize", "loading", "spinner",
                    
                    # 社交媒体图标
                    "facebook", "twitter", "instagram", "weibo", "qq", "wechat",
                    
                    # 明确的小尺寸标识
                    "thumb", "thumbnail", "small", "mini", "tiny",
                    
                    # 常见的固定尺寸装饰图
                    "16x16", "20x20", "24x24", "32x32", "48x48", "64x64",
                    "100x100", "120x120", "150x150", "200x200",
                    
                    # 常见的装饰图片文件名模式
                    # 注意：mm系列图片可能是内容图片，需要更精确的匹配
                    # "mm01", "mm02", "mm03", "mm04", "mm05", "mm06", "mm07", "mm08", "mm09",
                    
                    # Xiuren网站特定的装饰图片模式
                    "logo.gif", "favicon.ico", "style.css", "main.js", "slider.js",
                    "aqml00", "tj.js", "xiu.js", "wang/"
                ],
                
                # 图片过滤速率限制设置
                "rate_limit_for_filtering": False,  # 是否在图片过滤时应用速率限制
                
                # 尺寸指示器模式（用于文件名中的尺寸检测）
                "size_indicators": [
                    # 明确的缩略图尺寸模式
                    r'thumb.*?(\d+)x(\d+)',
                    r'small.*?(\d+)x(\d+)', 
                    r'mini.*?(\d+)x(\d+)',
                    r'(\d+)x(\d+).*?thumb',
                    r'(\d+)x(\d+).*?small',
                    # 明确的小尺寸文件名模式
                    r'^(\d+)x(\d+)\.',  # 开头就是尺寸的文件名
                    r'_(\d+)x(\d+)\.',  # _尺寸.扩展名的格式
                ],
                
                # 数字后缀页面模式
                "numbered_page_patterns": [
                    r'/\w+\d+_\d+\.',  # 如 /Xiuren33893_1.html
                    r'/\w+\d+_\d+/',   # 如 /Xiuren33893_1/
                    r'_\d+\.',         # 如 _1.html
                    r'_\d+/',          # 如 _1/
                    # Xiuren网站特定的模式
                    r'/Xiuren\d+_\d+\.',  # Xiuren33893_1.html
                    r'/Xiuren\d+_\d+/',   # Xiuren33893_1/
                    r'/tuigirl\d+_\d+\.', # tuigirl1391_1.html
                    r'/tuigirl\d+_\d+/',  # tuigirl1391_1/
                    r'/批量任务_\w+\d+_\d+\.', # 批量任务_Xiuren33893_1.html
                    r'/批量任务_\w+\d+_\d+/',  # 批量任务_Xiuren33893_1/
                ],
                
                # Xiuren图片URL模式
                "xiuren_image_patterns": [
                    r'/uploadfile/\d{4}/\d{2}/[A-Z0-9]+\.webp',  # /uploadfile/2024/06/5C91117996.webp
                    r'/uploadfile/\d{6}/[A-Z0-9]+\.webp',        # /uploadfile/202406/A991117250.webp
                    r'/pic/\d+/[A-Za-z0-9]+\.jpg',               # /pic/33829/abc123.jpg
                ],
                
                # 装饰性图片文件名长度阈值
                "max_decorative_filename_length": 2,
                "max_decorative_digit_length": 3
            },
            
            # 网页解析设置
            "page_settings": {
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "headers": {
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                    "Accept-Language": "zh-CN,zh;q=0.8,en-US;q=0.5,en;q=0.3",
                    "Accept-Encoding": "gzip, deflate",
                    "Connection": "keep-alive",
                    "Upgrade-Insecure-Requests": "1"
                }
            },
            
            # 任务调度设置
            "scheduler": {
                "max_concurrent_tasks": 3,
                "task_check_interval": 60  # 秒
            },
            
            # 请求速率限制设置
            "rate_limiting": {
                "enabled": True,
                "max_requests_per_second": 2.0,  # 每秒最大请求数
                "burst_capacity": 5,  # 突发请求容量
                "global_limit": True,  # 是否使用全局限制
                "fast_mode": False  # 快速模式，关闭速率限制
            },
            
            # 日志设置
            "log_level": "INFO",
            "log_file": "./logs/downloader.log",
            "log_max_size": 10485760,  # 10MB
            "log_backup_count": 5,
            
            # GUI设置
            "gui": {
                "window_width": 800,
                "window_height": 600,
                "theme": "default",
                "last_download_directory": ""  # 记住上次选择的下载目录
            }
        }
    
    def _load_config(self) -> None:
        """从文件加载配置"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    file_config = json.load(f)
                    self._merge_config(file_config)
            except Exception as e:
                print(f"加载配置文件失败: {e}，使用默认配置")
    
    def _merge_config(self, file_config: dict[str, Any]) -> None:
        """合并配置"""
        def merge_dict(default: dict[str, Any], custom: dict[str, Any]) -> dict[str, Any]:
            result = default.copy()
            for key, value in custom.items():
                if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                    result[key] = merge_dict(result[key], value)
                else:
                    result[key] = value
            return result
        
        self._config = merge_dict(self._config, file_config)
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置值
        
        Args:
            key: 配置键，支持点号分隔的嵌套键
            default: 默认值
            
        Returns:
            配置值
        """
        keys = key.split('.')
        value = self._config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def set(self, key: str, value: Any) -> None:
        """
        设置配置值
        
        Args:
            key: 配置键
            value: 配置值
        """
        keys = key.split('.')
        config = self._config
        
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        
        config[keys[-1]] = value
    
    def save(self) -> bool:
        """
        保存配置到文件
        
        Returns:
            是否保存成功
        """
        try:
            # 确保目录存在
            config_dir = os.path.dirname(os.path.abspath(self.config_file))
            if config_dir and not os.path.exists(config_dir):
                os.makedirs(config_dir, exist_ok=True)
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self._config, f, indent=2, ensure_ascii=False)
            print(f"配置已保存到: {os.path.abspath(self.config_file)}")
            return True
        except Exception as e:
            print(f"保存配置文件失败: {e}")
            return False
    
    def get_all(self) -> dict[str, Any]:
        """获取所有配置"""
        return self._config.copy()
    
    def reset_to_default(self) -> None:
        """重置为默认配置"""
        self._config = self._load_default_config()