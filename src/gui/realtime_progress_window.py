#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
实时进度窗口模块
提供精确的实时下载进度显示，确保与实际下载状态完全同步
"""

import tkinter as tk
from tkinter import ttk
import threading
import time
from typing import Dict, Any, Optional, Callable, List
from datetime import datetime, timedelta
from dataclasses import dataclass

from ..models.data_models import DownloadTask, DownloadStatus, ImageInfo


@dataclass
class ProgressStats:
    """进度统计数据"""
    total_files: int = 0
    completed_files: int = 0
    failed_files: int = 0
    total_bytes: int = 0
    downloaded_bytes: int = 0
    current_speed: float = 0.0  # bytes/second
    average_speed: float = 0.0  # bytes/second
    eta_seconds: int = 0
    start_time: Optional[datetime] = None
    last_update_time: Optional[datetime] = None


class RealTimeProgressWindow:
    """实时进度窗口 - 精确反映实际下载进度"""
    
    def __init__(self, parent: tk.Tk, task: DownloadTask, scheduler: Any):
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
        self.task_id = task.id
        
        # 进度统计
        self.stats = ProgressStats()
        self.stats.start_time = datetime.now()
        self.stats.last_update_time = datetime.now()
        
        # 实时数据缓存
        self.image_progress: Dict[str, Dict[str, Any]] = {}  # url -> progress_data
        self.speed_history: List[float] = []  # 用于计算平均速度
        self.last_bytes = 0
        self.update_interval = 0.5  # 更新间隔（秒）
        
        # 线程控制
        self.is_running = True
        self.update_thread = None
        self.data_lock = threading.Lock()
        
        # 创建窗口
        self.create_window()
        
        # 注册回调函数到下载管理器
        self.register_callbacks()
        
        # 启动更新线程
        self.start_update_thread()
    
    def create_window(self):
        """创建进度窗口界面"""
        self.window = tk.Toplevel(self.parent)
        self.window.title(f"下载进度 - {self.task.name}")
        self.window.geometry("800x600")
        self.window.resizable(True, True)
        
        # 设置窗口图标和属性
        self.window.transient(self.parent)
        self.window.grab_set()
        
        # 创建主框架
        main_frame = ttk.Frame(self.window, padding="10")
        main_frame.grid(row=0, column=0, sticky="wens")
        
        # 配置网格权重
        self.window.columnconfigure(0, weight=1)
        self.window.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        
        # 任务信息区域
        info_frame = ttk.LabelFrame(main_frame, text="任务信息", padding="5")
        info_frame.grid(row=0, column=0, columnspan=2, sticky="we", pady=(0, 10))
        info_frame.columnconfigure(1, weight=1)
        
        ttk.Label(info_frame, text="任务名称:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        self.task_name_label = ttk.Label(info_frame, text=self.task.name)
        self.task_name_label.grid(row=0, column=1, sticky="we")
        
        ttk.Label(info_frame, text="目标URL:").grid(row=1, column=0, sticky=tk.W, padx=(0, 10))
        task_url = getattr(self.task, 'url', 'Unknown URL')
        self.url_label = ttk.Label(info_frame, text=task_url[:80] + "..." if len(task_url) > 80 else task_url)
        self.url_label.grid(row=1, column=1, sticky="we")
        
        # 总体进度区域
        progress_frame = ttk.LabelFrame(main_frame, text="总体进度", padding="5")
        progress_frame.grid(row=1, column=0, columnspan=2, sticky="we", pady=(0, 10))
        progress_frame.columnconfigure(1, weight=1)
        
        # 文件进度
        ttk.Label(progress_frame, text="文件进度:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        self.file_progress_var = tk.StringVar(value="0 / 0 (0%)")
        self.file_progress_label = ttk.Label(progress_frame, textvariable=self.file_progress_var)
        self.file_progress_label.grid(row=0, column=1, sticky="we")
        
        # 文件进度条
        self.file_progress_bar = ttk.Progressbar(progress_frame, mode='determinate')
        self.file_progress_bar.grid(row=1, column=0, columnspan=2, sticky="we", pady=(5, 0))
        
        # 字节进度
        ttk.Label(progress_frame, text="数据进度:").grid(row=2, column=0, sticky=tk.W, padx=(0, 10), pady=(10, 0))
        self.byte_progress_var = tk.StringVar(value="0 B / 0 B (0%)")
        self.byte_progress_label = ttk.Label(progress_frame, textvariable=self.byte_progress_var)
        self.byte_progress_label.grid(row=2, column=1, sticky="we", pady=(10, 0))
        
        # 字节进度条
        self.byte_progress_bar = ttk.Progressbar(progress_frame, mode='determinate')
        self.byte_progress_bar.grid(row=3, column=0, columnspan=2, sticky="we", pady=(5, 0))
        
        # 速度和时间信息
        stats_frame = ttk.LabelFrame(main_frame, text="速度统计", padding="5")
        stats_frame.grid(row=2, column=0, columnspan=2, sticky="we", pady=(0, 10))
        stats_frame.columnconfigure(1, weight=1)
        stats_frame.columnconfigure(3, weight=1)
        
        ttk.Label(stats_frame, text="当前速度:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        self.current_speed_var = tk.StringVar(value="0 B/s")
        ttk.Label(stats_frame, textvariable=self.current_speed_var).grid(row=0, column=1, sticky=tk.W)
        
        ttk.Label(stats_frame, text="平均速度:").grid(row=0, column=2, sticky=tk.W, padx=(20, 10))
        self.average_speed_var = tk.StringVar(value="0 B/s")
        ttk.Label(stats_frame, textvariable=self.average_speed_var).grid(row=0, column=3, sticky=tk.W)
        
        ttk.Label(stats_frame, text="已用时间:").grid(row=1, column=0, sticky=tk.W, padx=(0, 10))
        self.elapsed_time_var = tk.StringVar(value="00:00:00")
        ttk.Label(stats_frame, textvariable=self.elapsed_time_var).grid(row=1, column=1, sticky=tk.W)
        
        ttk.Label(stats_frame, text="预计剩余:").grid(row=1, column=2, sticky=tk.W, padx=(20, 10))
        self.eta_var = tk.StringVar(value="--:--:--")
        ttk.Label(stats_frame, textvariable=self.eta_var).grid(row=1, column=3, sticky=tk.W)
        
        # 详细进度列表
        details_frame = ttk.LabelFrame(main_frame, text="下载详情", padding="5")
        details_frame.grid(row=3, column=0, columnspan=2, sticky="wens", pady=(0, 10))
        details_frame.columnconfigure(0, weight=1)
        details_frame.rowconfigure(0, weight=1)
        main_frame.rowconfigure(3, weight=1)
        
        # 创建Treeview
        columns = ("文件名", "状态", "进度", "大小", "速度")
        self.tree = ttk.Treeview(details_frame, columns=columns, show="headings", height=12)
        
        # 设置列标题和宽度
        self.tree.heading("文件名", text="文件名")
        self.tree.heading("状态", text="状态")
        self.tree.heading("进度", text="进度")
        self.tree.heading("大小", text="大小")
        self.tree.heading("速度", text="速度")
        
        self.tree.column("文件名", width=300, minwidth=200)
        self.tree.column("状态", width=80, minwidth=60)
        self.tree.column("进度", width=100, minwidth=80)
        self.tree.column("大小", width=100, minwidth=80)
        self.tree.column("速度", width=100, minwidth=80)
        
        # 添加滚动条
        scrollbar = ttk.Scrollbar(details_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        self.tree.grid(row=0, column=0, sticky="wens")
        scrollbar.grid(row=0, column=1, sticky="ns")
        
        # 控制按钮
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=4, column=0, columnspan=2, sticky="we", pady=(10, 0))
        
        self.pause_button = ttk.Button(button_frame, text="暂停", command=self.toggle_pause)
        self.pause_button.pack(side=tk.LEFT, padx=(0, 10))
        
        self.cancel_button = ttk.Button(button_frame, text="取消", command=self.cancel_download)
        self.cancel_button.pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(button_frame, text="关闭", command=self.close_window).pack(side=tk.RIGHT)
        
        # 绑定窗口关闭事件
        self.window.protocol("WM_DELETE_WINDOW", self.close_window)
    
    def register_callbacks(self):
        """注册下载进度回调函数"""
        try:
            # 获取下载管理器
            download_manager = self.scheduler.download_manager
            
            # 注册进度回调
            download_manager.add_progress_callback(self.on_download_progress)
            
            # 如果有状态回调接口，也注册状态回调
            if hasattr(download_manager, 'add_status_callback'):
                download_manager.add_status_callback(self.on_status_change)
                
        except Exception as e:
            print(f"注册回调函数失败: {e}")
    
    def on_download_progress(self, image_info: ImageInfo, downloaded: int, total: int):
        """下载进度回调"""
        with self.data_lock:
            url = image_info.url
            current_time = datetime.now()
            
            # 计算速度
            speed = 0.0
            if url in self.image_progress:
                last_data = self.image_progress[url]
                if 'last_downloaded' in last_data and 'last_time' in last_data:
                    time_diff = (current_time - last_data['last_time']).total_seconds()
                    if time_diff > 0:
                        bytes_diff = downloaded - last_data.get('last_downloaded', 0)
                        speed = bytes_diff / time_diff
            
            # 更新图片进度数据
            self.image_progress[url] = {
                'image_info': image_info,
                'downloaded': downloaded,
                'total': total,
                'progress': (downloaded / total * 100) if total > 0 else 0,
                'speed': speed,
                'last_update': current_time,
                'last_downloaded': downloaded,
                'last_time': current_time
            }
    
    def on_status_change(self, image_info: ImageInfo, old_status: DownloadStatus, new_status: DownloadStatus):
        """状态变化回调"""
        with self.data_lock:
            url = image_info.url
            if url not in self.image_progress:
                self.image_progress[url] = {
                    'image_info': image_info,
                    'downloaded': 0,
                    'total': 0,
                    'progress': 0,
                    'last_update': datetime.now()
                }
            
            self.image_progress[url]['status'] = new_status
            self.image_progress[url]['last_update'] = datetime.now()
    
    def start_update_thread(self):
        """启动更新线程"""
        self.update_thread = threading.Thread(target=self.update_loop, daemon=True)
        self.update_thread.start()
    
    def update_loop(self):
        """更新循环"""
        while self.is_running:
            try:
                self.update_display()
                time.sleep(self.update_interval)
            except Exception as e:
                print(f"更新显示时出错: {e}")
                time.sleep(1)
    
    def update_display(self):
        """更新显示内容"""
        if not self.is_running:
            return
            
        try:
            with self.data_lock:
                # 计算总体统计
                self.calculate_stats()
                
                # 更新GUI（在主线程中执行）
                self.window.after(0, self.update_gui)
                
        except Exception as e:
            print(f"更新显示数据时出错: {e}")
    
    def calculate_stats(self):
        """计算统计数据"""
        total_files = 0
        completed_files = 0
        failed_files = 0
        total_bytes = 0
        downloaded_bytes = 0
        current_speeds = []
        
        # 获取任务中的所有图片
        all_images = []
        if hasattr(self.task, 'images') and getattr(self.task, 'images', None):
            all_images.extend(self.task.images)
        elif hasattr(self.task, 'pages') and getattr(self.task, 'pages', None):
            for page in self.task.pages:
                if hasattr(page, 'images') and page.images:
                    all_images.extend(page.images)
        
        # 统计每个图片的状态
        for image in all_images:
            total_files += 1
            
            if image.url in self.image_progress:
                progress_data = self.image_progress[image.url]
                downloaded_bytes += progress_data.get('downloaded', 0)
                total_bytes += progress_data.get('total', 0)
                
                if progress_data.get('speed', 0) > 0:
                    current_speeds.append(progress_data['speed'])
                
                # 根据状态统计
                status = progress_data.get('status', image.status)
                if status == DownloadStatus.COMPLETED:
                    completed_files += 1
                elif status == DownloadStatus.FAILED:
                    failed_files += 1
            else:
                # 使用图片本身的状态
                if image.status == DownloadStatus.COMPLETED:
                    completed_files += 1
                elif image.status == DownloadStatus.FAILED:
                    failed_files += 1
        
        # 更新统计数据
        self.stats.total_files = total_files
        self.stats.completed_files = completed_files
        self.stats.failed_files = failed_files
        self.stats.total_bytes = total_bytes
        self.stats.downloaded_bytes = downloaded_bytes
        
        # 计算速度
        self.stats.current_speed = sum(current_speeds) if current_speeds else 0
        
        # 计算平均速度
        if self.stats.start_time:
            elapsed = (datetime.now() - self.stats.start_time).total_seconds()
            if elapsed > 0:
                self.stats.average_speed = downloaded_bytes / elapsed
        
        # 计算ETA
        if self.stats.current_speed > 0 and total_bytes > downloaded_bytes:
            remaining_bytes = total_bytes - downloaded_bytes
            self.stats.eta_seconds = int(remaining_bytes / self.stats.current_speed)
        else:
            self.stats.eta_seconds = 0
    
    def update_gui(self):
        """更新GUI显示"""
        try:
            # 更新文件进度
            if self.stats.total_files > 0:
                file_percent = (self.stats.completed_files / self.stats.total_files) * 100
                self.file_progress_var.set(f"{self.stats.completed_files} / {self.stats.total_files} ({file_percent:.1f}%)")
                self.file_progress_bar['value'] = file_percent
            else:
                self.file_progress_var.set("0 / 0 (0%)")
                self.file_progress_bar['value'] = 0
            
            # 更新字节进度
            if self.stats.total_bytes > 0:
                byte_percent = (self.stats.downloaded_bytes / self.stats.total_bytes) * 100
                total_mb = self.stats.total_bytes / (1024 * 1024)
                downloaded_mb = self.stats.downloaded_bytes / (1024 * 1024)
                self.byte_progress_var.set(f"{downloaded_mb:.1f} MB / {total_mb:.1f} MB ({byte_percent:.1f}%)")
                self.byte_progress_bar['value'] = byte_percent
            else:
                self.byte_progress_var.set("0 B / 0 B (0%)")
                self.byte_progress_bar['value'] = 0
            
            # 更新速度信息
            self.current_speed_var.set(self.format_speed(self.stats.current_speed))
            self.average_speed_var.set(self.format_speed(self.stats.average_speed))
            
            # 更新时间信息
            if self.stats.start_time:
                elapsed = datetime.now() - self.stats.start_time
                self.elapsed_time_var.set(self.format_time(elapsed.total_seconds()))
            
            if self.stats.eta_seconds > 0:
                self.eta_var.set(self.format_time(self.stats.eta_seconds))
            else:
                self.eta_var.set("--:--:--")
            
            # 更新详细列表
            self.update_details_tree()
            
        except Exception as e:
            print(f"更新GUI时出错: {e}")
    
    def update_details_tree(self):
        """更新详细信息树"""
        try:
            # 清空现有项目
            for item in self.tree.get_children():
                self.tree.delete(item)
            
            # 获取所有图片
            all_images = []
            if hasattr(self.task, 'images') and getattr(self.task, 'images', None):
                all_images.extend(self.task.images)
            elif hasattr(self.task, 'pages') and getattr(self.task, 'pages', None):
                for page in self.task.pages:
                    if hasattr(page, 'images') and page.images:
                        all_images.extend(page.images)
            
            # 添加每个图片的信息
            for image in all_images:
                filename = image.filename or "未知文件"
                
                # 获取进度数据
                if image.url in self.image_progress:
                    progress_data = self.image_progress[image.url]
                    status = self.get_status_text(progress_data.get('status', image.status))
                    progress = f"{progress_data.get('progress', 0):.1f}%"
                    
                    total_size = progress_data.get('total', 0)
                    size_text = self.format_size(total_size) if total_size > 0 else "未知"
                    
                    speed = progress_data.get('speed', 0)
                    speed_text = self.format_speed(speed) if speed > 0 else "--"
                else:
                    status = self.get_status_text(image.status)
                    progress = "0%"
                    size_text = "未知"
                    speed_text = "--"
                
                # 插入到树中
                self.tree.insert("", "end", values=(filename, status, progress, size_text, speed_text))
                
        except Exception as e:
            print(f"更新详细列表时出错: {e}")
    
    def get_status_text(self, status: DownloadStatus) -> str:
        """获取状态文本"""
        status_map = {
            DownloadStatus.WAITING: "⏳ 等待",
            DownloadStatus.DOWNLOADING: "⬇️ 下载中",
            DownloadStatus.COMPLETED: "✅ 完成",
            DownloadStatus.FAILED: "❌ 失败",
            DownloadStatus.CANCELLED: "🚫 取消"
        }
        return status_map.get(status, "❓ 未知")
    
    def format_speed(self, speed: float) -> str:
        """格式化速度显示"""
        if speed < 1024:
            return f"{speed:.0f} B/s"
        elif speed < 1024 * 1024:
            return f"{speed/1024:.1f} KB/s"
        else:
            return f"{speed/(1024*1024):.1f} MB/s"
    
    def format_size(self, size: int) -> str:
        """格式化大小显示"""
        if size < 1024:
            return f"{size} B"
        elif size < 1024 * 1024:
            return f"{size/1024:.1f} KB"
        else:
            return f"{size/(1024*1024):.1f} MB"
    
    def format_time(self, seconds: float) -> str:
        """格式化时间显示"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    
    def toggle_pause(self):
        """切换暂停/继续状态"""
        try:
            # 检查调度器是否有暂停功能
            if hasattr(self.scheduler, 'pause_task') and hasattr(self.scheduler, 'resume_task'):
                if self.pause_button['text'] == "暂停":
                    self.scheduler.pause_task(self.task_id)
                    self.pause_button['text'] = "继续"
                    print(f"任务 {self.task_id} 已暂停")
                else:
                    self.scheduler.resume_task(self.task_id)
                    self.pause_button['text'] = "暂停"
                    print(f"任务 {self.task_id} 已继续")
            else:
                # 如果调度器没有暂停功能，直接操作下载管理器
                if hasattr(self.scheduler, 'download_manager'):
                    dm = self.scheduler.download_manager
                    if self.pause_button['text'] == "暂停":
                        dm.is_running = False
                        self.pause_button['text'] = "继续"
                        print("下载已暂停")
                    else:
                        dm.is_running = True
                        self.pause_button['text'] = "暂停"
                        print("下载已继续")
                else:
                    print("暂停功能不可用")
        except Exception as e:
            print(f"切换暂停状态时出错: {e}")
    
    def cancel_download(self):
        """取消下载"""
        try:
            print("开始取消下载...")
            
            # 立即停止更新线程
            self.is_running = False
            
            # 检查调度器是否有取消功能
            if hasattr(self.scheduler, 'cancel_task'):
                self.scheduler.cancel_task(self.task_id)
                print(f"任务 {self.task_id} 已取消")
            else:
                # 如果调度器没有取消功能，直接停止下载管理器
                if hasattr(self.scheduler, 'download_manager'):
                    self.scheduler.download_manager.stop()
                    print("下载已停止")
                else:
                    print("取消功能不可用")
            
            # 在后台线程中更新状态，避免GUI阻塞
            def update_cancelled_status():
                try:
                    with self.data_lock:
                        for url, progress_data in self.image_progress.items():
                            if 'image_info' in progress_data:
                                image_info = progress_data['image_info']
                                if image_info.status not in [DownloadStatus.COMPLETED, DownloadStatus.FAILED]:
                                    # 直接更新状态，不调用回调避免循环
                                    image_info.status = DownloadStatus.CANCELLED
                                    progress_data['status'] = DownloadStatus.CANCELLED
                    print("所有图片状态已更新为取消")
                except Exception as e:
                    print(f"更新取消状态时出错: {e}")
            
            # 在后台线程中执行状态更新
            status_thread = threading.Thread(target=update_cancelled_status, daemon=True)
            status_thread.start()
            
            # 延迟关闭窗口，确保状态更新完成
            self.window.after(500, self.close_window)
            
        except Exception as e:
            print(f"取消下载时出错: {e}")
            # 确保窗口能够关闭
            self.window.after(100, self.close_window)
    
    def close_window(self):
        """关闭窗口"""
        try:
            print("开始关闭进度窗口...")
            
            # 停止更新线程
            self.is_running = False
            
            # 非阻塞方式等待线程结束
            if self.update_thread and self.update_thread.is_alive():
                # 不使用join，避免GUI线程阻塞
                print("更新线程将在后台自动结束")
            
            # 清理回调函数（如果存在）
            if hasattr(self, 'progress_callbacks'):
                self.progress_callbacks.clear()
            if hasattr(self, 'status_callbacks'):
                self.status_callbacks.clear()
            
            # 销毁窗口
            if hasattr(self, 'window') and self.window:
                self.window.destroy()
                print("进度窗口已关闭")
            
        except Exception as e:
            print(f"关闭窗口时出错: {e}")
            # 强制销毁窗口
            try:
                if hasattr(self, 'window'):
                    self.window.quit()
            except:
                pass