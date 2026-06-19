#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
实时进度窗口模块
真正解决状态显示问题的进度窗口
"""

import tkinter as tk
from tkinter import ttk
from typing import Dict, List, Optional
import threading
import time
import logging

from ..models.data_models import DownloadTask, ImageInfo, DownloadStatus
from .theme import center_window, style_button, style_window


class RealTimeProgressWindow:
    """实时下载进度窗口"""
    
    def __init__(self, parent, task: DownloadTask, scheduler=None):
        """
        初始化实时进度窗口
        
        Args:
            parent: 父窗口
            task: 下载任务
            scheduler: 任务调度器
        """
        self.parent = parent
        self.task = task
        self.scheduler = scheduler
        self.logger = logging.getLogger(__name__)
        
        # 状态跟踪
        self.is_running = True
        self.last_update_time = time.time()
        self.last_completed_count = 0
        self.image_status_cache = {}  # 缓存图片状态
        
        # 创建窗口
        self.window = tk.Toplevel(parent)
        self.window.title(f"实时下载进度 - {task.name}")
        self.window.transient(parent)
        style_window(self.window)
        
        # 窗口关闭事件
        self.window.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # 居中显示
        center_window(self.window, parent, width=900, height=700)
        
        self._create_widgets()
        self._start_real_time_update()
    
    def center_window(self):
        """窗口居中显示"""
        self.window.update_idletasks()
        x = (self.window.winfo_screenwidth() // 2) - (900 // 2)
        y = (self.window.winfo_screenheight() // 2) - (700 // 2)
        self.window.geometry(f"900x700+{x}+{y}")
    
    def _create_widgets(self):
        """创建界面控件"""
        main_frame = ttk.Frame(self.window, padding=16, style="App.TFrame")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 任务信息区域
        self._create_task_info_section(main_frame)
        
        # 实时统计区域
        self._create_stats_section(main_frame)
        
        # 总体进度区域
        self._create_progress_section(main_frame)
        
        # 详细列表区域
        self._create_detail_section(main_frame)
        
        # 控制按钮区域
        self._create_button_section(main_frame)
    
    def _create_task_info_section(self, parent):
        """创建任务信息区域"""
        info_frame = ttk.LabelFrame(parent, text="任务信息", padding=12, style="App.TLabelframe")
        info_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 任务基本信息
        info_grid = ttk.Frame(info_frame, style="Surface.TFrame")
        info_grid.pack(fill=tk.X)
        
        ttk.Label(info_grid, text="任务名称:").grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
        ttk.Label(info_grid, text=self.task.name, font=('', 9, 'bold')).grid(row=0, column=1, sticky=tk.W)
        
        ttk.Label(info_grid, text="目标URL:").grid(row=1, column=0, sticky=tk.W, padx=(0, 5))
        ttk.Label(info_grid, text=self.task.base_url).grid(row=1, column=1, sticky=tk.W)
        
        ttk.Label(info_grid, text="下载路径:").grid(row=2, column=0, sticky=tk.W, padx=(0, 5))
        ttk.Label(info_grid, text=self.task.download_path).grid(row=2, column=1, sticky=tk.W)
    
    def _create_stats_section(self, parent):
        """创建实时统计区域"""
        stats_frame = ttk.LabelFrame(parent, text="实时统计", padding=12, style="App.TLabelframe")
        stats_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 创建统计变量
        self.stats_vars = {
            'total': tk.StringVar(value="总数: 0"),
            'completed': tk.StringVar(value="已完成: 0"),
            'downloading': tk.StringVar(value="下载中: 0"),
            'failed': tk.StringVar(value="失败: 0"),
            'speed': tk.StringVar(value="速度: 0 图片/秒"),
            'eta': tk.StringVar(value="预计剩余: --")
        }
        
        # 布局统计信息
        stats_grid = ttk.Frame(stats_frame, style="Surface.TFrame")
        stats_grid.pack(fill=tk.X)
        
        # 第一行
        ttk.Label(stats_grid, textvariable=self.stats_vars['total']).grid(row=0, column=0, sticky=tk.W, padx=10)
        ttk.Label(stats_grid, textvariable=self.stats_vars['completed']).grid(row=0, column=1, sticky=tk.W, padx=10)
        ttk.Label(stats_grid, textvariable=self.stats_vars['downloading']).grid(row=0, column=2, sticky=tk.W, padx=10)
        
        # 第二行
        ttk.Label(stats_grid, textvariable=self.stats_vars['failed']).grid(row=1, column=0, sticky=tk.W, padx=10)
        ttk.Label(stats_grid, textvariable=self.stats_vars['speed']).grid(row=1, column=1, sticky=tk.W, padx=10)
        ttk.Label(stats_grid, textvariable=self.stats_vars['eta']).grid(row=1, column=2, sticky=tk.W, padx=10)
    
    def _create_progress_section(self, parent):
        """创建总体进度区域"""
        progress_frame = ttk.LabelFrame(parent, text="总体进度", padding=12, style="App.TLabelframe")
        progress_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 进度条
        self.overall_progress_var = tk.DoubleVar()
        self.overall_progress = ttk.Progressbar(
            progress_frame,
            variable=self.overall_progress_var,
            length=500,
            mode='determinate',
            style="App.Horizontal.TProgressbar"
        )
        self.overall_progress.pack(fill=tk.X, pady=5)
        
        # 进度文本
        self.overall_text_var = tk.StringVar(value="准备开始...")
        progress_label = ttk.Label(progress_frame, textvariable=self.overall_text_var)
        progress_label.pack(anchor=tk.W, pady=2)
        
        # 状态指示器
        self.status_indicator_var = tk.StringVar(value="● 准备中")
        status_label = ttk.Label(progress_frame, textvariable=self.status_indicator_var, foreground="orange")
        status_label.pack(anchor=tk.W)
    
    def _create_detail_section(self, parent):
        """创建详细列表区域"""
        detail_frame = ttk.LabelFrame(parent, text="下载详情 (实时更新)", padding=12, style="App.TLabelframe")
        detail_frame.pack(fill=tk.BOTH, expand=True)
        
        # 创建Treeview
        columns = ('filename', 'status', 'progress', 'size', 'speed', 'time')
        self.detail_tree = ttk.Treeview(detail_frame, columns=columns, show='headings', height=15, style="App.Treeview")
        
        # 设置列标题和宽度
        column_configs = {
            'filename': ('文件名', 250),
            'status': ('状态', 80),
            'progress': ('进度', 80),
            'size': ('大小', 80),
            'speed': ('速度', 100),
            'time': ('用时', 80)
        }
        
        for col, (title, width) in column_configs.items():
            self.detail_tree.heading(col, text=title)
            self.detail_tree.column(col, width=width, minwidth=50)
        
        # 添加滚动条
        detail_scroll_v = ttk.Scrollbar(detail_frame, orient=tk.VERTICAL, command=self.detail_tree.yview)
        detail_scroll_h = ttk.Scrollbar(detail_frame, orient=tk.HORIZONTAL, command=self.detail_tree.xview)
        self.detail_tree.configure(yscrollcommand=detail_scroll_v.set, xscrollcommand=detail_scroll_h.set)
        
        # 布局
        self.detail_tree.grid(row=0, column=0, sticky='nsew')
        detail_scroll_v.grid(row=0, column=1, sticky='ns')
        detail_scroll_h.grid(row=1, column=0, sticky='ew')
        
        detail_frame.grid_rowconfigure(0, weight=1)
        detail_frame.grid_columnconfigure(0, weight=1)
    
    def _create_button_section(self, parent):
        """创建控制按钮区域"""
        button_frame = ttk.Frame(parent, style="App.TFrame")
        button_frame.pack(fill=tk.X, pady=(10, 0))
        
        # 右侧按钮
        style_button(ttk.Button(button_frame, text="关闭", command=self.close), "ghost").pack(side=tk.RIGHT)
        style_button(ttk.Button(button_frame, text="手动刷新", command=self.manual_refresh), "secondary").pack(side=tk.RIGHT, padx=(0, 10))
        
        # 左侧状态
        self.update_status_var = tk.StringVar(value="实时更新: 启用")
        ttk.Label(button_frame, textvariable=self.update_status_var, foreground="green").pack(side=tk.LEFT)
    
    def _start_real_time_update(self):
        """启动实时更新"""
        self._update_display()
    
    def _update_display(self):
        """更新显示内容"""
        if not self.is_running or not self.window.winfo_exists():
            return
        
        try:
            # 获取最新任务状态
            current_task = self._get_latest_task()
            if not current_task:
                self.window.after(500, self._update_display)
                return
            
            # 更新统计信息
            self._update_statistics(current_task)
            
            # 更新总体进度
            self._update_overall_progress(current_task)
            
            # 更新详细列表
            self._update_detail_list(current_task)
            
            # 更新状态指示器
            self._update_status_indicator(current_task)
            
        except Exception as e:
            self.logger.error(f"更新显示时出错: {e}")
        
        # 继续更新 - 500ms间隔实现实时效果
        if self.is_running:
            self.window.after(500, self._update_display)
    
    def _get_latest_task(self) -> Optional[DownloadTask]:
        """获取最新的任务状态"""
        if self.scheduler:
            try:
                # 尝试从调度器获取最新状态
                latest_task = self.scheduler.get_task_status(self.task.id)
                if latest_task:
                    return latest_task
            except Exception as e:
                self.logger.debug(f"从调度器获取任务状态失败: {e}")
        
        # 返回当前任务
        return self.task
    
    def _update_statistics(self, task: DownloadTask):
        """更新统计信息"""
        # 获取所有图片 - 兼容不同数据结构
        from .progress_window_integration import get_all_images_from_task
        all_images = get_all_images_from_task(task)
        total_count = len(all_images)
        
        # 统计状态
        status_counts = {
            'completed': 0,
            'downloading': 0,
            'failed': 0,
            'pending': 0
        }
        
        for img in all_images:
            if img.status == DownloadStatus.COMPLETED:
                status_counts['completed'] += 1
            elif img.status == DownloadStatus.DOWNLOADING:
                status_counts['downloading'] += 1
            elif img.status == DownloadStatus.FAILED:
                status_counts['failed'] += 1
            else:
                status_counts['pending'] += 1
        
        # 更新统计显示
        self.stats_vars['total'].set(f"总数: {total_count}")
        self.stats_vars['completed'].set(f"已完成: {status_counts['completed']}")
        self.stats_vars['downloading'].set(f"下载中: {status_counts['downloading']}")
        self.stats_vars['failed'].set(f"失败: {status_counts['failed']}")
        
        # 计算下载速度
        current_time = time.time()
        time_diff = current_time - self.last_update_time
        
        if time_diff >= 1.0:  # 每秒计算一次速度
            completed_diff = status_counts['completed'] - self.last_completed_count
            speed = completed_diff / time_diff if time_diff > 0 else 0
            self.stats_vars['speed'].set(f"速度: {speed:.1f} 图片/秒")
            
            # 计算预计剩余时间
            remaining = total_count - status_counts['completed']
            if speed > 0 and remaining > 0:
                eta_seconds = remaining / speed
                eta_text = self._format_time(eta_seconds)
                self.stats_vars['eta'].set(f"预计剩余: {eta_text}")
            else:
                self.stats_vars['eta'].set("预计剩余: --")
            
            # 更新记录
            self.last_update_time = current_time
            self.last_completed_count = status_counts['completed']
    
    def _update_overall_progress(self, task: DownloadTask):
        """更新总体进度"""
        # 获取所有图片 - 兼容不同数据结构
        from .progress_window_integration import get_all_images_from_task
        all_images = get_all_images_from_task(task)
        
        total_count = len(all_images)
        if total_count == 0:
            self.overall_progress_var.set(0)
            self.overall_text_var.set("没有图片需要下载")
            return
        
        # 计算完成数量
        completed_count = sum(1 for img in all_images if img.status == DownloadStatus.COMPLETED)
        downloading_count = sum(1 for img in all_images if img.status == DownloadStatus.DOWNLOADING)
        
        # 计算进度百分比
        progress_percent = (completed_count / total_count) * 100
        self.overall_progress_var.set(progress_percent)
        
        # 更新进度文本
        if downloading_count > 0:
            self.overall_text_var.set(
                f"进度: {completed_count}/{total_count} ({progress_percent:.1f}%) - {downloading_count}个正在下载"
            )
        elif completed_count == total_count:
            self.overall_text_var.set(f"下载完成: {completed_count}/{total_count} (100%)")
        else:
            self.overall_text_var.set(f"进度: {completed_count}/{total_count} ({progress_percent:.1f}%)")
    
    def _update_detail_list(self, task: DownloadTask):
        """更新详细列表"""
        # 获取所有图片 - 兼容不同数据结构  
        from .progress_window_integration import get_all_images_from_task
        all_images = get_all_images_from_task(task)
        
        # 获取当前列表中的项目
        current_items = {}
        for item in self.detail_tree.get_children():
            values = self.detail_tree.item(item, 'values')
            if values and len(values) > 0:
                current_items[values[0]] = item
        
        # 更新或添加图片项目
        for i, img in enumerate(all_images):
            filename = img.filename or f"图片_{i+1}"
            
            # 状态文本和图标
            status_map = {
                DownloadStatus.PENDING: "⏳ 等待中",
                DownloadStatus.DOWNLOADING: "⬇️ 下载中",
                DownloadStatus.COMPLETED: "✅ 已完成",
                DownloadStatus.FAILED: "❌ 失败"
            }
            status_text = status_map.get(img.status, f"❓ 未知")
            
            # 进度显示
            if img.status == DownloadStatus.COMPLETED:
                progress_text = "100%"
            elif img.status == DownloadStatus.DOWNLOADING:
                progress_text = "下载中..."
            elif img.status == DownloadStatus.FAILED:
                progress_text = "失败"
            else:
                progress_text = "0%"
            
            # 文件大小
            size_text = self._format_size(getattr(img, 'file_size', 0) or getattr(img, 'size', 0))
            
            # 下载速度
            speed_text = "0 B/s"
            if img.status == DownloadStatus.DOWNLOADING:
                speed_text = "计算中..."
            
            # 用时
            time_text = "--"
            if img.status == DownloadStatus.COMPLETED:
                time_text = "已完成"
            elif img.status == DownloadStatus.DOWNLOADING:
                time_text = "进行中"
            
            values = (filename, status_text, progress_text, size_text, speed_text, time_text)
            
            if filename in current_items:
                # 更新现有项目
                self.detail_tree.item(current_items[filename], values=values)
            else:
                # 添加新项目
                self.detail_tree.insert('', 'end', values=values)
        
        # 移除不再存在的项目
        current_filenames = {img.filename or f"图片_{i+1}" for i, img in enumerate(all_images)}
        for filename, item in current_items.items():
            if filename not in current_filenames:
                self.detail_tree.delete(item)
    
    def _update_status_indicator(self, task: DownloadTask):
        """更新状态指示器"""
        # 获取所有图片
        if hasattr(task, 'images') and task.images:
            all_images = task.images
        else:
            all_images = [img for page in getattr(task, 'pages', []) for img in page.images]
        
        if not all_images:
            self.status_indicator_var.set("● 无图片")
            return
        
        downloading_count = sum(1 for img in all_images if img.status == DownloadStatus.DOWNLOADING)
        completed_count = sum(1 for img in all_images if img.status == DownloadStatus.COMPLETED)
        failed_count = sum(1 for img in all_images if img.status == DownloadStatus.FAILED)
        
        if downloading_count > 0:
            self.status_indicator_var.set("🔄 下载中")
        elif completed_count == len(all_images):
            self.status_indicator_var.set("✅ 全部完成")
        elif failed_count > 0:
            self.status_indicator_var.set("⚠️ 部分失败")
        else:
            self.status_indicator_var.set("⏳ 等待中")
    
    def _format_size(self, size: int) -> str:
        """格式化文件大小"""
        if not size or size <= 0:
            return "未知"
        
        units = ['B', 'KB', 'MB', 'GB']
        size_float = float(size)
        
        for unit in units:
            if size_float < 1024.0:
                return f"{size_float:.1f} {unit}"
            size_float /= 1024.0
        
        return f"{size_float:.1f} TB"
    
    def _format_time(self, seconds: float) -> str:
        """格式化时间"""
        if seconds < 60:
            return f"{seconds:.0f}秒"
        elif seconds < 3600:
            return f"{seconds/60:.0f}分钟"
        else:
            return f"{seconds/3600:.1f}小时"
    
    def manual_refresh(self):
        """手动刷新"""
        try:
            current_task = self._get_latest_task()
            if current_task:
                self._update_statistics(current_task)
                self._update_overall_progress(current_task)
                self._update_detail_list(current_task)
                self._update_status_indicator(current_task)
                
                self.update_status_var.set("手动刷新完成")
                self.window.after(2000, lambda: self.update_status_var.set("实时更新: 启用"))
        except Exception as e:
            self.logger.error(f"手动刷新失败: {e}")
            self.update_status_var.set("刷新失败")
    
    def on_closing(self):
        """窗口关闭事件"""
        self.is_running = False
        self.window.destroy()
    
    def close(self):
        """关闭窗口"""
        self.on_closing()
