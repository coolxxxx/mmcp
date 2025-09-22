#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
进度窗口集成模块
提供统一的进度窗口创建接口
"""

import logging
from typing import Optional

from ..models.data_models import DownloadTask


def create_progress_window(parent, task: DownloadTask, scheduler=None):
    """
    创建进度窗口
    优先使用实时进度窗口，如果失败则回退到原始进度窗口
    
    Args:
        parent: 父窗口
        task: 下载任务
        scheduler: 任务调度器
        
    Returns:
        进度窗口实例
    """
    logger = logging.getLogger(__name__)
    
    try:
        # 尝试使用实时进度窗口
        from .real_time_progress_window import RealTimeProgressWindow
        logger.info("使用实时进度窗口")
        return RealTimeProgressWindow(parent, task, scheduler)
        
    except Exception as e:
        logger.warning(f"创建实时进度窗口失败，回退到原始进度窗口: {e}")
        
        try:
            # 回退到原始进度窗口
            from .progress_window import ProgressWindow
            return ProgressWindow(parent, task, scheduler)
            
        except Exception as e2:
            logger.error(f"创建原始进度窗口也失败: {e2}")
            raise e2


def get_all_images_from_task(task: DownloadTask):
    """
    从任务中获取所有图片信息
    兼容不同的数据结构
    
    Args:
        task: 下载任务
        
    Returns:
        图片信息列表
    """
    all_images = []
    
    # 方法1: 直接从task.images获取
    if hasattr(task, 'images') and task.images:
        all_images.extend(task.images)
    
    # 方法2: 从task.pages获取
    if hasattr(task, 'pages') and task.pages:
        for page in task.pages:
            if hasattr(page, 'images') and page.images:
                all_images.extend(page.images)
    
    return all_images


def calculate_task_statistics(task: DownloadTask):
    """
    计算任务统计信息
    
    Args:
        task: 下载任务
        
    Returns:
        统计信息字典
    """
    from ..models.data_models import DownloadStatus
    
    all_images = get_all_images_from_task(task)
    
    stats = {
        'total': len(all_images),
        'completed': 0,
        'downloading': 0,
        'failed': 0,
        'pending': 0
    }
    
    for img in all_images:
        if img.status == DownloadStatus.COMPLETED:
            stats['completed'] += 1
        elif img.status == DownloadStatus.DOWNLOADING:
            stats['downloading'] += 1
        elif img.status == DownloadStatus.FAILED:
            stats['failed'] += 1
        else:
            stats['pending'] += 1
    
    return stats


def format_file_size(size: Optional[int]) -> str:
    """
    格式化文件大小显示
    
    Args:
        size: 文件大小（字节）
        
    Returns:
        格式化的大小字符串
    """
    if not size or size <= 0:
        return "未知"
    
    units = ['B', 'KB', 'MB', 'GB', 'TB']
    size_float = float(size)
    
    for unit in units:
        if size_float < 1024.0:
            if unit == 'B':
                return f"{int(size_float)} {unit}"
            else:
                return f"{size_float:.1f} {unit}"
        size_float /= 1024.0
    
    return f"{size_float:.1f} PB"


def get_status_display_text(status):
    """
    获取状态的显示文本
    
    Args:
        status: 下载状态
        
    Returns:
        显示文本
    """
    from ..models.data_models import DownloadStatus
    
    status_map = {
        DownloadStatus.WAITING: "⏳ 等待中",
        DownloadStatus.DOWNLOADING: "⬇️ 下载中", 
        DownloadStatus.COMPLETED: "✅ 已完成",
        DownloadStatus.FAILED: "❌ 失败",
        DownloadStatus.CANCELLED: "🚫 已取消"
    }
    
    return status_map.get(status, "❓ 未知")


def format_time_duration(seconds: float) -> str:
    """
    格式化时间长度
    
    Args:
        seconds: 秒数
        
    Returns:
        格式化的时间字符串
    """
    if seconds < 0:
        return "--"
    elif seconds < 60:
        return f"{seconds:.0f}秒"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.0f}分钟"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}小时"