#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
进度窗口模块
"""

import tkinter as tk
from tkinter import ttk
from typing import Dict, List
import threading
import time

from ..models.data_models import DownloadTask, ImageInfo, DownloadStatus

class ProgressWindow:
    """下载进度窗口"""
    
    def __init__(self, parent, task: DownloadTask, scheduler=None):
        """
        初始化进度窗口
        
        Args:
            parent: 父窗口
            task: 下载任务
            scheduler: 任务调度器（可选，用于获取最新任务状态）
        """
        self.parent = parent
        self.task = task
        self.scheduler = scheduler
        
        # 创建窗口
        self.window = tk.Toplevel(parent)
        self.window.title(f"下载进度 - {task.name}")
        self.window.geometry("800x600")
        self.window.transient(parent)
        
        # 居中显示
        self.window.geometry("+%d+%d" % (
            parent.winfo_rootx() + 100,
            parent.winfo_rooty() + 100
        ))
        
        self._create_widgets()
        self._update_progress()
    
    def _create_widgets(self):
        """创建界面控件"""
        main_frame = ttk.Frame(self.window, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 任务信息
        info_frame = ttk.LabelFrame(main_frame, text="任务信息", padding=10)
        info_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(info_frame, text=f"任务名称: {self.task.name}").pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"目标URL: {self.task.base_url}").pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"下载路径: {self.task.download_path}").pack(anchor=tk.W)
        
        # 总体进度
        progress_frame = ttk.LabelFrame(main_frame, text="总体进度", padding=10)
        progress_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 进度条
        self.overall_progress_var = tk.DoubleVar()
        self.overall_progress = ttk.Progressbar(
            progress_frame,
            variable=self.overall_progress_var,
            length=400
        )
        self.overall_progress.pack(fill=tk.X, pady=5)
        
        # 进度文本
        self.overall_text_var = tk.StringVar()
        ttk.Label(progress_frame, textvariable=self.overall_text_var).pack(anchor=tk.W)
        
        # 统计信息
        stats_frame = ttk.Frame(progress_frame)
        stats_frame.pack(fill=tk.X, pady=5)
        
        self.stats_vars = {
            'total': tk.StringVar(value="总数: 0"),
            'completed': tk.StringVar(value="完成: 0"),
            'failed': tk.StringVar(value="失败: 0"),
            'speed': tk.StringVar(value="速度: 0 B/s")
        }
        
        for i, (key, var) in enumerate(self.stats_vars.items()):
            ttk.Label(stats_frame, textvariable=var).grid(
                row=0, column=i, padx=10, sticky=tk.W
            )
        
        # 详细列表
        detail_frame = ttk.LabelFrame(main_frame, text="下载详情", padding=10)
        detail_frame.pack(fill=tk.BOTH, expand=True)
        
        # 创建Treeview
        columns = ('filename', 'status', 'progress', 'size', 'speed')
        self.detail_tree = ttk.Treeview(detail_frame, columns=columns, show='headings')
        
        # 设置列标题
        self.detail_tree.heading('filename', text='文件名')
        self.detail_tree.heading('status', text='状态')
        self.detail_tree.heading('progress', text='进度')
        self.detail_tree.heading('size', text='大小')
        self.detail_tree.heading('speed', text='速度')
        
        # 设置列宽
        self.detail_tree.column('filename', width=300)
        self.detail_tree.column('status', width=80)
        self.detail_tree.column('progress', width=100)
        self.detail_tree.column('size', width=100)
        self.detail_tree.column('speed', width=100)
        
        # 添加滚动条
        detail_scroll = ttk.Scrollbar(
            detail_frame, 
            orient=tk.VERTICAL, 
            command=self.detail_tree.yview
        )
        self.detail_tree.configure(yscrollcommand=detail_scroll.set)
        
        # 布局
        self.detail_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        detail_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 按钮区域
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))
        
        ttk.Button(button_frame, text="关闭", command=self.close).pack(side=tk.RIGHT)
        ttk.Button(button_frame, text="刷新", command=self.refresh).pack(side=tk.RIGHT, padx=(0, 10))
    
    def _update_progress(self):
        """更新进度显示"""
        if self.window.winfo_exists():
            self._refresh_data()
            # 每秒更新一次
            self.window.after(1000, self._update_progress)
    
    def _get_current_task(self) -> DownloadTask:
        """获取当前任务的最新状态"""
        if self.scheduler:
            # 从调度器获取最新任务状态
            current_task = self.scheduler.get_task(self.task.id)
            if current_task:
                return current_task
        # 如果没有调度器或者获取失败，返回原始任务
        return self.task

    def _refresh_data(self):
        """刷新数据显示"""
        # 获取最新任务状态
        current_task = self._get_current_task()
        
        # 更新总体进度
        progress = current_task.progress
        self.overall_progress_var.set(progress)
        
        # 更新进度文本
        self.overall_text_var.set(
            f"{current_task.downloaded_images} / {current_task.total_images} "
            f"({progress:.1f}%) - {self._format_size(current_task.downloaded_size)}"
        )
        
        # 更新统计信息
        self.stats_vars['total'].set(f"总数: {current_task.total_images}")
        self.stats_vars['completed'].set(f"完成: {current_task.downloaded_images}")
        self.stats_vars['failed'].set(f"失败: {current_task.failed_images}")
        
        # 计算并显示下载速度
        download_speed = self._calculate_download_speed(current_task)
        self.stats_vars['speed'].set(f"速度: {download_speed}")
        
        # 更新详细列表
        self._update_detail_list(current_task)
    
    def _update_detail_list(self, current_task: DownloadTask):
        """更新详细列表"""
        # 获取当前所有项目
        current_items = {}
        for item in self.detail_tree.get_children():
            values = self.detail_tree.item(item, 'values')
            if values and len(values) > 0:
                current_items[values[0]] = item  # 文件名作为键
        
        # 更新或添加图片项目
        for page in current_task.pages:
            for image in page.images:
                status_text = self._get_status_text(image.status)
                progress_text = f"{image.progress:.1f}%" if image.progress > 0 else "0%"
                size_text = self._format_size(image.size) if image.size else "未知"
                
                # 计算单个图片的下载速度
                speed_text = self._get_image_speed(image)
                
                values = (
                    image.filename,
                    status_text,
                    progress_text,
                    size_text,
                    speed_text
                )
                
                if image.filename in current_items:
                    # 更新现有项目
                    self.detail_tree.item(current_items[image.filename], values=values)
                else:
                    # 添加新项目
                    self.detail_tree.insert('', tk.END, values=values)
        
        # 移除不再存在的项目
        current_filenames = {image.filename for page in current_task.pages for image in page.images}
        for filename, item in current_items.items():
            if filename not in current_filenames:
                self.detail_tree.delete(item)
    
    def _get_status_text(self, status: DownloadStatus) -> str:
        """获取状态文本"""
        status_map = {
            DownloadStatus.WAITING: "等待",
            DownloadStatus.DOWNLOADING: "下载中",
            DownloadStatus.COMPLETED: "完成",
            DownloadStatus.FAILED: "失败",
            DownloadStatus.CANCELLED: "取消"
        }
        return status_map.get(status, "未知")
    
    def _format_size(self, size: int) -> str:
        """格式化文件大小"""
        if not size:
            return "0 B"
        
        units = ['B', 'KB', 'MB', 'GB']
        size_float = float(size)
        
        for unit in units:
            if size_float < 1024.0:
                return f"{size_float:.1f} {unit}"
            size_float /= 1024.0
        
        return f"{size_float:.1f} TB"
    
    def _calculate_download_speed(self, current_task: DownloadTask) -> str:
        """计算下载速度"""
        if not hasattr(self, '_last_update_time'):
            self._last_update_time = time.time()
            self._last_downloaded_size = 0
            return "0 B/s"
        
        current_time = time.time()
        time_diff = current_time - self._last_update_time
        
        if time_diff < 0.1:  # 避免除零和太短的时间间隔
            return self.stats_vars['speed'].get().split(': ')[1]  # 保持当前速度显示
        
        # 计算速度 (bytes per second)
        size_diff = current_task.downloaded_size - self._last_downloaded_size
        speed_bps = size_diff / time_diff
        
        # 更新记录
        self._last_update_time = current_time
        self._last_downloaded_size = current_task.downloaded_size
        
        # 格式化速度显示
        if speed_bps <= 0:
            return "0 B/s"
        
        units = ['B/s', 'KB/s', 'MB/s', 'GB/s']
        speed_float = float(speed_bps)
        
        for unit in units:
            if speed_float < 1024.0:
                return f"{speed_float:.1f} {unit}"
            speed_float /= 1024.0
        
        return f"{speed_float:.1f} GB/s"
    
    def _get_image_speed(self, image: ImageInfo) -> str:
        """获取单个图片的下载速度"""
        if not hasattr(self, '_image_speeds'):
            self._image_speeds = {}
            self._image_last_update = {}
            self._image_last_size = {}
        
        image_key = image.filename
        current_time = time.time()
        
        if image_key not in self._image_speeds:
            self._image_speeds[image_key] = 0
            self._image_last_update[image_key] = current_time
            self._image_last_size[image_key] = 0
            return "0 B/s"
        
        # 计算时间差
        time_diff = current_time - self._image_last_update[image_key]
        if time_diff < 0.1:  # 避免除零和太短的时间间隔
            return self._format_speed(self._image_speeds[image_key])
        
        # 计算速度 (bytes per second)
        current_size = image.size or 0
        size_diff = current_size - self._image_last_size[image_key]
        speed_bps = size_diff / time_diff
        
        # 更新记录
        self._image_speeds[image_key] = speed_bps
        self._image_last_update[image_key] = current_time
        self._image_last_size[image_key] = current_size
        
        return self._format_speed(speed_bps)
    
    def _format_speed(self, speed_bps: float) -> str:
        """格式化速度显示"""
        if speed_bps <= 0:
            return "0 B/s"
        
        units = ['B/s', 'KB/s', 'MB/s', 'GB/s']
        speed_float = float(speed_bps)
        
        for unit in units:
            if speed_float < 1024.0:
                return f"{speed_float:.1f} {unit}"
            speed_float /= 1024.0
        
        return f"{speed_float:.1f} GB/s"
    
    def refresh(self):
        """手动刷新"""
        self._refresh_data()
    
    def close(self):
        """关闭窗口"""
        self.window.destroy()