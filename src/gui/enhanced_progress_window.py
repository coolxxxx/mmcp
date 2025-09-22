"""
增强版进度窗口
解决状态显示和实时更新问题
"""

import tkinter as tk
from tkinter import ttk
from typing import Dict, List, Optional, Callable
import threading
import time

from ..models.data_models import DownloadTask, ImageInfo, DownloadStatus
from ..core.enhanced_downloader import EnhancedDownloadManager


class EnhancedProgressWindow:
    """增强版下载进度窗口，支持实时状态更新"""
    
    def __init__(self, parent, task: DownloadTask, scheduler=None, download_manager=None):
        """
        初始化增强版进度窗口
        
        Args:
            parent: 父窗口
            task: 下载任务
            scheduler: 任务调度器（可选）
            download_manager: 下载管理器（可选）
        """
        self.parent = parent
        self.task = task
        self.scheduler = scheduler
        self.download_manager = download_manager
        
        # 状态跟踪
        self.image_status_cache: Dict[str, ImageInfo] = {}
        self.last_update_time = 0
        self.update_interval = 0.5  # 更频繁的更新间隔
        
        # 性能统计
        self.performance_stats = {
            'start_time': time.time(),
            'last_speed_update': time.time(),
            'last_downloaded_size': 0,
            'speed_samples': []
        }
        
        # 创建窗口
        self.window = tk.Toplevel(parent)
        self.window.title(f"下载进度 - {task.name}")
        self.window.geometry("900x700")  # 增加窗口大小
        self.window.transient(parent)
        
        # 居中显示
        self.window.geometry("+%d+%d" % (
            parent.winfo_rootx() + 50,
            parent.winfo_rooty() + 50
        ))
        
        # 设置窗口图标和属性
        self.window.resizable(True, True)
        
        self._create_widgets()
        self._setup_callbacks()
        self._start_update_loop()
    
    def _create_widgets(self):
        """创建界面控件"""
        main_frame = ttk.Frame(self.window, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 任务信息区域
        self._create_task_info_section(main_frame)
        
        # 总体进度区域
        self._create_overall_progress_section(main_frame)
        
        # 性能监控区域
        self._create_performance_section(main_frame)
        
        # 详细列表区域
        self._create_detail_list_section(main_frame)
        
        # 按钮区域
        self._create_button_section(main_frame)
    
    def _create_task_info_section(self, parent):
        """创建任务信息区域"""
        info_frame = ttk.LabelFrame(parent, text="任务信息", padding=10)
        info_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 使用网格布局
        ttk.Label(info_frame, text="任务名称:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        ttk.Label(info_frame, text=self.task.name, font=('', 9, 'bold')).grid(row=0, column=1, sticky=tk.W)
        
        ttk.Label(info_frame, text="目标URL:").grid(row=1, column=0, sticky=tk.W, padx=(0, 10))
        url_label = ttk.Label(info_frame, text=self.task.base_url, foreground='blue')
        url_label.grid(row=1, column=1, sticky=tk.W)
        
        ttk.Label(info_frame, text="下载路径:").grid(row=2, column=0, sticky=tk.W, padx=(0, 10))
        ttk.Label(info_frame, text=self.task.download_path).grid(row=2, column=1, sticky=tk.W)
        
        # 任务状态
        ttk.Label(info_frame, text="任务状态:").grid(row=3, column=0, sticky=tk.W, padx=(0, 10))
        self.task_status_var = tk.StringVar(value=self.task.status.value)
        self.task_status_label = ttk.Label(info_frame, textvariable=self.task_status_var, font=('', 9, 'bold'))
        self.task_status_label.grid(row=3, column=1, sticky=tk.W)
    
    def _create_overall_progress_section(self, parent):
        """创建总体进度区域"""
        progress_frame = ttk.LabelFrame(parent, text="总体进度", padding=10)
        progress_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 主进度条
        self.overall_progress_var = tk.DoubleVar()
        self.overall_progress = ttk.Progressbar(
            progress_frame,
            variable=self.overall_progress_var,
            length=500,
            mode='determinate'
        )
        self.overall_progress.pack(fill=tk.X, pady=5)
        
        # 进度文本
        self.overall_text_var = tk.StringVar(value="准备开始...")
        ttk.Label(progress_frame, textvariable=self.overall_text_var, font=('', 10)).pack(anchor=tk.W, pady=2)
        
        # 统计信息网格
        stats_frame = ttk.Frame(progress_frame)
        stats_frame.pack(fill=tk.X, pady=5)
        
        self.stats_vars = {
            'total': tk.StringVar(value="总数: 0"),
            'completed': tk.StringVar(value="完成: 0"),
            'downloading': tk.StringVar(value="下载中: 0"),
            'failed': tk.StringVar(value="失败: 0"),
            'speed': tk.StringVar(value="速度: 0 B/s"),
            'eta': tk.StringVar(value="预计剩余: --")
        }
        
        # 两行三列布局
        row1_vars = ['total', 'completed', 'downloading']
        row2_vars = ['failed', 'speed', 'eta']
        
        for i, var_name in enumerate(row1_vars):
            ttk.Label(stats_frame, textvariable=self.stats_vars[var_name]).grid(
                row=0, column=i, padx=15, sticky=tk.W
            )
        
        for i, var_name in enumerate(row2_vars):
            ttk.Label(stats_frame, textvariable=self.stats_vars[var_name]).grid(
                row=1, column=i, padx=15, sticky=tk.W
            )
    
    def _create_performance_section(self, parent):
        """创建性能监控区域"""
        perf_frame = ttk.LabelFrame(parent, text="性能监控", padding=10)
        perf_frame.pack(fill=tk.X, pady=(0, 10))
        
        perf_grid = ttk.Frame(perf_frame)
        perf_grid.pack(fill=tk.X)
        
        self.perf_vars = {
            'threads': tk.StringVar(value="活跃线程: 0"),
            'queue': tk.StringVar(value="队列长度: 0"),
            'avg_speed': tk.StringVar(value="平均速度: 0 B/s"),
            'peak_speed': tk.StringVar(value="峰值速度: 0 B/s")
        }
        
        for i, (key, var) in enumerate(self.perf_vars.items()):
            ttk.Label(perf_grid, textvariable=var).grid(
                row=i // 2, column=i % 2, padx=20, sticky=tk.W
            )
    
    def _create_detail_list_section(self, parent):
        """创建详细列表区域"""
        detail_frame = ttk.LabelFrame(parent, text="下载详情", padding=10)
        detail_frame.pack(fill=tk.BOTH, expand=True)
        
        # 创建Treeview
        columns = ('filename', 'status', 'progress', 'size', 'speed', 'error')
        self.detail_tree = ttk.Treeview(detail_frame, columns=columns, show='headings', height=15)
        
        # 设置列标题和宽度
        column_configs = {
            'filename': ('文件名', 250),
            'status': ('状态', 80),
            'progress': ('进度', 80),
            'size': ('大小', 80),
            'speed': ('速度', 100),
            'error': ('错误信息', 200)
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
        
        # 状态颜色标记
        self.detail_tree.tag_configure('waiting', background='#f0f0f0')
        self.detail_tree.tag_configure('downloading', background='#e6f3ff')
        self.detail_tree.tag_configure('completed', background='#e6ffe6')
        self.detail_tree.tag_configure('failed', background='#ffe6e6')
    
    def _create_button_section(self, parent):
        """创建按钮区域"""
        button_frame = ttk.Frame(parent)
        button_frame.pack(fill=tk.X, pady=(10, 0))
        
        # 右侧按钮
        ttk.Button(button_frame, text="关闭", command=self.close).pack(side=tk.RIGHT)
        ttk.Button(button_frame, text="刷新", command=self.manual_refresh).pack(side=tk.RIGHT, padx=(0, 10))
        ttk.Button(button_frame, text="导出日志", command=self.export_log).pack(side=tk.RIGHT, padx=(0, 10))
        
        # 左侧控制按钮
        self.pause_resume_var = tk.StringVar(value="暂停")
        ttk.Button(button_frame, textvariable=self.pause_resume_var, command=self.toggle_pause).pack(side=tk.LEFT)
        ttk.Button(button_frame, text="取消下载", command=self.cancel_download).pack(side=tk.LEFT, padx=(10, 0))
    
    def _setup_callbacks(self):
        """设置回调函数"""
        if self.download_manager and hasattr(self.download_manager, 'add_status_callback'):
            # 添加状态更新回调
            self.download_manager.add_status_callback(self._on_status_change)
            self.download_manager.add_progress_callback(self._on_progress_update)
    
    def _start_update_loop(self):
        """启动更新循环"""
        self._update_display()
    
    def _update_display(self):
        """更新显示内容"""
        if not self.window.winfo_exists():
            return
        
        try:
            current_time = time.time()
            
            # 限制更新频率
            if current_time - self.last_update_time < self.update_interval:
                self.window.after(int(self.update_interval * 1000), self._update_display)
                return
            
            self.last_update_time = current_time
            
            # 获取最新任务状态
            current_task = self._get_current_task()
            
            # 更新任务状态
            self._update_task_status(current_task)
            
            # 更新总体进度
            self._update_overall_progress(current_task)
            
            # 更新统计信息
            self._update_statistics(current_task)
            
            # 更新性能信息
            self._update_performance_info()
            
            # 更新详细列表
            self._update_detail_list(current_task)
            
        except Exception as e:
            print(f"更新显示错误: {e}")
        
        # 继续更新循环
        self.window.after(int(self.update_interval * 1000), self._update_display)
    
    def _get_current_task(self) -> DownloadTask:
        """获取当前任务的最新状态"""
        if self.scheduler:
            # 从调度器获取最新任务状态
            current_task = self.scheduler.get_task(self.task.id)
            if current_task:
                return current_task
        # 如果没有调度器或者获取失败，返回原始任务
        return self.task
    
    def _update_task_status(self, current_task: DownloadTask):
        """更新任务状态"""
        status_text = current_task.status.value
        self.task_status_var.set(status_text)
        
        # 根据状态设置颜色
        color_map = {
            'pending': 'orange',
            'running': 'blue',
            'completed': 'green',
            'failed': 'red',
            'cancelled': 'gray'
        }
        
        color = color_map.get(status_text, 'black')
        self.task_status_label.configure(foreground=color)
    
    def _update_overall_progress(self, current_task: DownloadTask):
        """更新总体进度"""
        progress = current_task.progress
        self.overall_progress_var.set(progress)
        
        # 更新进度文本
        if current_task.total_images > 0:
            progress_text = (
                f"{current_task.downloaded_images} / {current_task.total_images} "
                f"({progress:.1f}%) - {self._format_size(current_task.downloaded_size)}"
            )
        else:
            progress_text = "正在解析页面..."
        
        self.overall_text_var.set(progress_text)
    
    def _update_statistics(self, current_task: DownloadTask):
        """更新统计信息"""
        # 基础统计
        self.stats_vars['total'].set(f"总数: {current_task.total_images}")
        self.stats_vars['completed'].set(f"完成: {current_task.downloaded_images}")
        self.stats_vars['failed'].set(f"失败: {current_task.failed_images}")
        
        # 计算正在下载的数量
        downloading_count = 0
        if self.download_manager and hasattr(self.download_manager, 'active_downloads'):
            downloading_count = len(getattr(self.download_manager, 'active_downloads', {}))
        
        self.stats_vars['downloading'].set(f"下载中: {downloading_count}")
        
        # 计算并显示下载速度
        download_speed = self._calculate_download_speed(current_task)
        self.stats_vars['speed'].set(f"速度: {download_speed}")
        
        # 计算预计剩余时间
        eta = self._calculate_eta(current_task)
        self.stats_vars['eta'].set(f"预计剩余: {eta}")
    
    def _update_performance_info(self):
        """更新性能信息"""
        if self.download_manager and hasattr(self.download_manager, 'get_performance_info'):
            try:
                perf_info = self.download_manager.get_performance_info()
                
                self.perf_vars['threads'].set(f"活跃线程: {perf_info.get('max_threads', 0)}")
                self.perf_vars['queue'].set(f"队列长度: {perf_info.get('queue_size', 0)}")
                
                # 获取速度信息
                if hasattr(self.download_manager, 'get_stats'):
                    stats = self.download_manager.get_stats()
                    current_speed = stats.get('download_speed', 0)
                    self.perf_vars['avg_speed'].set(f"当前速度: {self._format_speed(current_speed)}")
                    
                    # 更新峰值速度
                    if not hasattr(self, '_peak_speed'):
                        self._peak_speed = 0
                    if current_speed > self._peak_speed:
                        self._peak_speed = current_speed
                    self.perf_vars['peak_speed'].set(f"峰值速度: {self._format_speed(self._peak_speed)}")
                
            except Exception as e:
                print(f"更新性能信息错误: {e}")
    
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
                # 获取实时状态
                real_image = self._get_real_image_status(image)
                
                status_text = self._get_status_text(real_image.status)
                progress_text = f"{real_image.progress:.1f}%" if real_image.progress > 0 else "0%"
                size_text = self._format_size(real_image.size) if real_image.size else "未知"
                speed_text = self._get_image_speed(real_image)
                error_text = real_image.error_message or ""
                
                values = (
                    real_image.filename,
                    status_text,
                    progress_text,
                    size_text,
                    speed_text,
                    error_text
                )
                
                # 确定标签（用于颜色）
                tag = self._get_status_tag(real_image.status)
                
                if real_image.filename in current_items:
                    # 更新现有项目
                    item = current_items[real_image.filename]
                    self.detail_tree.item(item, values=values, tags=(tag,))
                else:
                    # 添加新项目
                    self.detail_tree.insert('', tk.END, values=values, tags=(tag,))
        
        # 移除不再存在的项目
        current_filenames = {image.filename for page in current_task.pages for image in page.images}
        for filename, item in current_items.items():
            if filename not in current_filenames:
                self.detail_tree.delete(item)
    
    def _get_real_image_status(self, image: ImageInfo) -> ImageInfo:
        """获取图片的实时状态"""
        if self.download_manager and hasattr(self.download_manager, 'get_image_status'):
            try:
                real_status = self.download_manager.get_image_status(image.url)
                if real_status:
                    return real_status
            except Exception:
                pass
        
        return image
    
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
    
    def _get_status_tag(self, status: DownloadStatus) -> str:
        """获取状态标签（用于颜色）"""
        tag_map = {
            DownloadStatus.WAITING: "waiting",
            DownloadStatus.DOWNLOADING: "downloading",
            DownloadStatus.COMPLETED: "completed",
            DownloadStatus.FAILED: "failed",
            DownloadStatus.CANCELLED: "failed"
        }
        return tag_map.get(status, "waiting")
    
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
    
    def _calculate_download_speed(self, current_task: DownloadTask) -> str:
        """计算下载速度"""
        current_time = time.time()
        
        # 初始化性能统计
        if not hasattr(self, '_last_speed_update'):
            self._last_speed_update = current_time
            self._last_downloaded_size = 0
            return "0 B/s"
        
        time_diff = current_time - self._last_speed_update
        
        if time_diff < 1.0:  # 至少1秒更新一次
            return getattr(self, '_last_speed_text', "0 B/s")
        
        # 计算速度
        size_diff = current_task.downloaded_size - self._last_downloaded_size
        speed_bps = size_diff / time_diff if time_diff > 0 else 0
        
        # 更新记录
        self._last_speed_update = current_time
        self._last_downloaded_size = current_task.downloaded_size
        
        # 格式化并缓存
        speed_text = self._format_speed(speed_bps)
        self._last_speed_text = speed_text
        
        return speed_text
    
    def _calculate_eta(self, current_task: DownloadTask) -> str:
        """计算预计剩余时间"""
        if current_task.total_images == 0 or current_task.downloaded_images == 0:
            return "--"
        
        # 计算平均每张图片的下载时间
        elapsed_time = time.time() - self.performance_stats['start_time']
        avg_time_per_image = elapsed_time / current_task.downloaded_images
        
        # 计算剩余图片数量
        remaining_images = current_task.total_images - current_task.downloaded_images - current_task.failed_images
        
        if remaining_images <= 0:
            return "即将完成"
        
        # 计算预计剩余时间
        eta_seconds = remaining_images * avg_time_per_image
        
        if eta_seconds < 60:
            return f"{int(eta_seconds)}秒"
        elif eta_seconds < 3600:
            return f"{int(eta_seconds / 60)}分钟"
        else:
            hours = int(eta_seconds / 3600)
            minutes = int((eta_seconds % 3600) / 60)
            return f"{hours}小时{minutes}分钟"
    
    def _get_image_speed(self, image: ImageInfo) -> str:
        """获取单个图片的下载速度"""
        # 这里可以从下载管理器获取实时速度
        if self.download_manager and hasattr(self.download_manager, 'active_downloads'):
            active_downloads = getattr(self.download_manager, 'active_downloads', {})
            if image.url in active_downloads:
                download_info = active_downloads[image.url]
                # 这里可以计算单个图片的下载速度
                return "下载中..."
        
        return "--"
    
    def _on_status_change(self, image_info: ImageInfo, status: DownloadStatus):
        """状态变化回调"""
        # 更新缓存
        self.image_status_cache[image_info.url] = image_info
    
    def _on_progress_update(self, image_info: ImageInfo, downloaded: int, total: int):
        """进度更新回调"""
        # 更新缓存中的进度信息
        if image_info.url in self.image_status_cache:
            cached_image = self.image_status_cache[image_info.url]
            if total > 0:
                cached_image.progress = (downloaded / total) * 100
    
    def manual_refresh(self):
        """手动刷新"""
        self.last_update_time = 0  # 强制立即更新
        self._update_display()
    
    def toggle_pause(self):
        """切换暂停/恢复"""
        # 这里可以实现暂停/恢复功能
        current_text = self.pause_resume_var.get()
        if current_text == "暂停":
            self.pause_resume_var.set("恢复")
            # 实现暂停逻辑
        else:
            self.pause_resume_var.set("暂停")
            # 实现恢复逻辑
    
    def cancel_download(self):
        """取消下载"""
        if self.download_manager:
            self.download_manager.cancel_download()
        
        if self.scheduler:
            self.scheduler.cancel_task(self.task.id)
    
    def export_log(self):
        """导出日志"""
        from tkinter import filedialog
        import json
        
        try:
            filename = filedialog.asksaveasfilename(
                title="导出下载日志",
                defaultextension=".json",
                filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
            )
            
            if filename:
                # 收集日志数据
                log_data = {
                    'task_info': {
                        'id': self.task.id,
                        'name': self.task.name,
                        'base_url': self.task.base_url,
                        'status': self.task.status.value,
                        'total_images': self.task.total_images,
                        'downloaded_images': self.task.downloaded_images,
                        'failed_images': self.task.failed_images
                    },
                    'images': []
                }
                
                # 添加图片信息
                for page in self.task.pages:
                    for image in page.images:
                        real_image = self._get_real_image_status(image)
                        log_data['images'].append({
                            'filename': real_image.filename,
                            'url': real_image.url,
                            'status': real_image.status.value,
                            'progress': real_image.progress,
                            'size': real_image.size,
                            'error_message': real_image.error_message
                        })
                
                # 写入文件
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(log_data, f, indent=2, ensure_ascii=False)
                
                tk.messagebox.showinfo("导出成功", f"日志已导出到: {filename}")
        
        except Exception as e:
            tk.messagebox.showerror("导出失败", f"导出日志时发生错误: {e}")
    
    def close(self):
        """关闭窗口"""
        self.window.destroy()