#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
可工作的进度窗口
直接修改原始进度窗口，确保能真正显示下载状态
"""

import tkinter as tk
from tkinter import ttk
from typing import Dict, List, Optional
import threading
import time
import logging

from ..models.data_models import DownloadTask, ImageInfo, DownloadStatus
from .theme import center_window, style_button, style_window


class WorkingProgressWindow:
    """可工作的下载进度窗口"""
    
    def __init__(self, parent, task: DownloadTask, scheduler=None):
        """
        初始化进度窗口
        
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
        
        # 创建窗口
        self.window = tk.Toplevel(parent)
        self.window.title(f"下载进度 - {task.name}")
        self.window.transient(parent)
        style_window(self.window)
        
        # 窗口关闭事件
        self.window.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # 居中显示
        center_window(self.window, parent, width=800, height=600)
        
        self._create_widgets()
        self._start_update()
    
    def center_window(self):
        """窗口居中显示"""
        self.window.update_idletasks()
        x = (self.window.winfo_screenwidth() // 2) - (400)
        y = (self.window.winfo_screenheight() // 2) - (300)
        self.window.geometry(f"800x600+{x}+{y}")
    
    def _create_widgets(self):
        """创建界面控件"""
        main_frame = ttk.Frame(self.window, padding=16, style="App.TFrame")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 任务信息
        info_frame = ttk.LabelFrame(main_frame, text="任务信息", padding=12, style="App.TLabelframe")
        info_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(info_frame, text=f"任务名称: {self.task.name}").pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"目标URL: {self.task.base_url}").pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"下载路径: {self.task.download_path}").pack(anchor=tk.W)
        
        # 总体进度
        progress_frame = ttk.LabelFrame(main_frame, text="总体进度", padding=12, style="App.TLabelframe")
        progress_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 进度条
        self.overall_progress_var = tk.DoubleVar()
        self.overall_progress = ttk.Progressbar(
            progress_frame,
            variable=self.overall_progress_var,
            length=400,
            style="App.Horizontal.TProgressbar"
        )
        self.overall_progress.pack(fill=tk.X, pady=5)
        
        # 进度文本
        self.overall_text_var = tk.StringVar()
        ttk.Label(progress_frame, textvariable=self.overall_text_var).pack(anchor=tk.W)
        
        # 统计信息
        stats_frame = ttk.Frame(progress_frame, style="Surface.TFrame")
        stats_frame.pack(fill=tk.X, pady=5)
        
        self.stats_vars = {
            'total': tk.StringVar(value="总数: 0"),
            'completed': tk.StringVar(value="完成: 0"),
            'failed': tk.StringVar(value="失败: 0"),
            'speed': tk.StringVar(value="速度: 0 图片/秒")
        }
        
        for i, (key, var) in enumerate(self.stats_vars.items()):
            ttk.Label(stats_frame, textvariable=var).grid(
                row=0, column=i, padx=10, sticky=tk.W
            )
        
        # 详细列表
        detail_frame = ttk.LabelFrame(main_frame, text="下载详情 (实时更新)", padding=12, style="App.TLabelframe")
        detail_frame.pack(fill=tk.BOTH, expand=True)
        
        # 创建Treeview
        columns = ('filename', 'status', 'progress', 'size')
        self.detail_tree = ttk.Treeview(detail_frame, columns=columns, show='headings', style="App.Treeview")
        
        # 设置列标题
        self.detail_tree.heading('filename', text='文件名')
        self.detail_tree.heading('status', text='状态')
        self.detail_tree.heading('progress', text='进度')
        self.detail_tree.heading('size', text='大小')
        
        # 设置列宽
        self.detail_tree.column('filename', width=300)
        self.detail_tree.column('status', width=100)
        self.detail_tree.column('progress', width=100)
        self.detail_tree.column('size', width=100)
        
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
        button_frame = ttk.Frame(main_frame, style="App.TFrame")
        button_frame.pack(fill=tk.X, pady=(10, 0))
        
        style_button(ttk.Button(button_frame, text="关闭", command=self.close), "ghost").pack(side=tk.RIGHT)
        style_button(ttk.Button(button_frame, text="刷新", command=self.manual_refresh), "secondary").pack(side=tk.RIGHT, padx=(0, 10))
        
        # 状态标签
        self.status_label = ttk.Label(button_frame, text="状态: 准备中", foreground="blue")
        self.status_label.pack(side=tk.LEFT)
    
    def _start_update(self):
        """启动更新"""
        self._update_display()
    
    def _update_display(self):
        """更新显示"""
        if not self.is_running or not self.window.winfo_exists():
            return
        
        try:
            # 获取最新任务状态
            current_task = self._get_latest_task()
            if current_task:
                self._update_progress(current_task)
                self.status_label.config(text="状态: 实时更新中", foreground="green")
            else:
                self.status_label.config(text="状态: 无法获取任务数据", foreground="red")
                
        except Exception as e:
            self.logger.error(f"更新显示时出错: {e}")
            self.status_label.config(text=f"状态: 更新错误 - {str(e)[:50]}", foreground="red")
        
        # 继续更新 - 1秒间隔
        if self.is_running:
            self.window.after(1000, self._update_display)
    
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
    
    def _update_progress(self, task: DownloadTask):
        """更新进度显示"""
        # 获取所有图片
        all_images = self._get_all_images(task)
        total_count = len(all_images)
        
        if total_count == 0:
            self.overall_progress_var.set(0)
            self.overall_text_var.set("没有图片需要下载")
            return
        
        # 统计各种状态
        completed_count = 0
        downloading_count = 0
        failed_count = 0
        waiting_count = 0
        
        for img in all_images:
            if img.status == DownloadStatus.COMPLETED:
                completed_count += 1
            elif img.status == DownloadStatus.DOWNLOADING:
                downloading_count += 1
            elif img.status == DownloadStatus.FAILED:
                failed_count += 1
            else:  # WAITING or other
                waiting_count += 1
        
        # 更新进度条
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
        
        # 更新统计信息
        self.stats_vars['total'].set(f"总数: {total_count}")
        self.stats_vars['completed'].set(f"完成: {completed_count}")
        self.stats_vars['failed'].set(f"失败: {failed_count}")
        
        # 计算下载速度
        current_time = time.time()
        time_diff = current_time - self.last_update_time
        
        if time_diff >= 1.0:  # 每秒计算一次速度
            completed_diff = completed_count - self.last_completed_count
            speed = completed_diff / time_diff if time_diff > 0 else 0
            self.stats_vars['speed'].set(f"速度: {speed:.1f} 图片/秒")
            
            # 更新记录
            self.last_update_time = current_time
            self.last_completed_count = completed_count
        
        # 更新详细列表
        self._update_detail_list(all_images)
    
    def _get_all_images(self, task: DownloadTask) -> List[ImageInfo]:
        """获取所有图片信息"""
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
    
    def _update_detail_list(self, all_images: List[ImageInfo]):
        """更新详细列表"""
        # 清空现有项目
        for item in self.detail_tree.get_children():
            self.detail_tree.delete(item)
        
        # 添加图片信息
        for i, img in enumerate(all_images):
            filename = img.filename or f"图片_{i+1}"
            
            # 状态文本
            status_text = self._get_status_text(img.status)
            
            # 进度显示
            if img.status == DownloadStatus.COMPLETED:
                progress_text = "100%"
            elif img.status == DownloadStatus.DOWNLOADING:
                progress_text = "下载中..."
            elif img.status == DownloadStatus.FAILED:
                progress_text = "失败"
            else:
                progress_text = "等待中"
            
            # 文件大小
            size = getattr(img, 'file_size', None) or getattr(img, 'size', None)
            size_text = self._format_size(size) if size else "未知"
            
            # 插入行
            self.detail_tree.insert('', 'end', values=(
                filename,
                status_text,
                progress_text,
                size_text
            ))
    
    def _get_status_text(self, status: DownloadStatus) -> str:
        """获取状态文本"""
        status_map = {
            DownloadStatus.WAITING: "⏳ 等待中",
            DownloadStatus.DOWNLOADING: "⬇️ 下载中",
            DownloadStatus.COMPLETED: "✅ 已完成",
            DownloadStatus.FAILED: "❌ 失败",
            DownloadStatus.CANCELLED: "🚫 已取消"
        }
        return status_map.get(status, "❓ 未知")
    
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
    
    def manual_refresh(self):
        """手动刷新"""
        try:
            current_task = self._get_latest_task()
            if current_task:
                self._update_progress(current_task)
                self.status_label.config(text="状态: 手动刷新完成", foreground="blue")
                self.window.after(2000, lambda: self.status_label.config(text="状态: 实时更新中", foreground="green"))
            else:
                self.status_label.config(text="状态: 刷新失败 - 无法获取任务", foreground="red")
        except Exception as e:
            self.logger.error(f"手动刷新失败: {e}")
            self.status_label.config(text=f"状态: 刷新失败 - {str(e)[:30]}", foreground="red")
    
    def on_closing(self):
        """窗口关闭事件"""
        self.is_running = False
        self.window.destroy()
    
    def close(self):
        """关闭窗口"""
        self.on_closing()
