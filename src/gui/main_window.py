#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
主窗口GUI模块
"""

import tkinter as tk
from tkinter import ttk, messagebox
import logging
import os

from ..core.scheduler import TaskScheduler
from ..models.data_models import TaskStatus, DownloadStatus
from .task_dialog import TaskDialog
from .batch_task_dialog import BatchTaskDialog
from .progress_window import ProgressWindow
from .settings_dialog import SettingsDialog

class MainWindow:
    """主窗口类"""
    
    def __init__(self, root: tk.Tk, config):
        """初始化主窗口"""
        self.root: tk.Tk = root
        self.config = config
        self.logger: logging.Logger = logging.getLogger(__name__)
        
        # 初始化调度器
        self.scheduler: TaskScheduler = TaskScheduler(config)
        self.scheduler.add_task_callback(self.on_task_status_changed)
        
        # 界面变量
        self.progress_windows: dict[str, ProgressWindow] = {}
        self.batch_stats_var: tk.StringVar = tk.StringVar(value="任务统计: 0个任务")
        self.selected_tasks: set[str] = set()  # 持久化存储选中任务ID
        
        # GUI控件变量
        self.selection_status_var: tk.StringVar
        self.task_tree: ttk.Treeview
        self.status_var: tk.StringVar
        self.stats_var: tk.StringVar
        self._update_timer: str | None = None
        
        self._setup_window()
        self._create_widgets()
        
        # 启动调度器
        self.scheduler.start_scheduler()
        
        # 定时更新界面
        self._update_interface()
        
        # 设置关闭事件
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
    
    def _setup_window(self):
        """设置窗口"""
        self.root.title("图片批量下载器")
        width = self.config.get('gui.window_width', 900)
        height = self.config.get('gui.window_height', 700)
        
        # 居中显示
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = (screen_width - width) // 2
        y = (screen_height - height) // 2
        
        self.root.geometry(f"{width}x{height}+{x}+{y}")
        self.root.minsize(800, 600)
    
    def _create_widgets(self):
        """创建界面控件"""
        # 主框架
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # 工具栏
        self._create_toolbar(main_frame)
        
        # 分隔器
        ttk.Separator(main_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=5)
        
        # 任务列表
        self._create_task_list(main_frame)
        
        # 状态栏
        self._create_status_bar(main_frame)
    
    def _create_toolbar(self, parent: ttk.Frame) -> None:
        """创建工具栏"""
        toolbar = ttk.Frame(parent)
        toolbar.pack(fill=tk.X, pady=(0, 5))
        
        # 任务操作组
        task_group = ttk.LabelFrame(toolbar, text="任务操作", padding=5)
        task_group.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        
        # 使用网格布局
        ttk.Button(task_group, text="新建任务", command=self.new_task, width=12).grid(row=0, column=0, padx=2, pady=2)
        ttk.Button(task_group, text="批量创建", command=self.open_batch_creator, width=12).grid(row=0, column=1, padx=2, pady=2)
        ttk.Button(task_group, text="开始任务", command=self.start_selected_task, width=12).grid(row=1, column=0, padx=2, pady=2)
        ttk.Button(task_group, text="重新下载", command=self.restart_selected_task, width=12).grid(row=1, column=1, padx=2, pady=2)
        
        # 管理操作组
        manage_group = ttk.LabelFrame(toolbar, text="管理操作", padding=5)
        manage_group.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        
        ttk.Button(manage_group, text="取消任务", command=self.cancel_selected_task, width=12).grid(row=0, column=0, padx=2, pady=2)
        ttk.Button(manage_group, text="删除任务", command=self.delete_selected_task, width=12).grid(row=0, column=1, padx=2, pady=2)
        ttk.Button(manage_group, text="图片预览", command=self.preview_images, width=12).grid(row=1, column=0, padx=2, pady=2)
        ttk.Button(manage_group, text="打开目录", command=self.open_download_folder, width=12).grid(row=1, column=1, padx=2, pady=2)
        
        # 右侧设置按钮
        right_buttons = ttk.Frame(toolbar)
        right_buttons.pack(side=tk.RIGHT)
        
        ttk.Button(right_buttons, text="设置", command=self.open_settings, width=8).pack()
    
    def _create_task_list(self, parent: ttk.Frame) -> None:
        """创建任务列表"""
        # 添加批量操作工具栏
        batch_toolbar = ttk.Frame(parent)
        batch_toolbar.pack(fill=tk.X, pady=(0, 5))
        
        # 批量选择操作
        batch_select_frame = ttk.LabelFrame(batch_toolbar, text="批量选择", padding=5)
        batch_select_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        
        ttk.Button(batch_select_frame, text="全选", command=self.select_all_tasks, width=8).grid(row=0, column=0, padx=2)
        ttk.Button(batch_select_frame, text="反选", command=self.invert_selection, width=8).grid(row=0, column=1, padx=2)
        ttk.Button(batch_select_frame, text="清空", command=self.clear_selection, width=8).grid(row=0, column=2, padx=2)
        
        # 批量操作
        batch_ops_frame = ttk.LabelFrame(batch_toolbar, text="批量操作", padding=5)
        batch_ops_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        
        ttk.Button(batch_ops_frame, text="开始", command=self.batch_start_tasks, width=8).grid(row=0, column=0, padx=2)
        ttk.Button(batch_ops_frame, text="暂停", command=self.batch_pause_tasks, width=8).grid(row=0, column=1, padx=2)
        ttk.Button(batch_ops_frame, text="取消", command=self.batch_cancel_tasks, width=8).grid(row=0, column=2, padx=2)
        ttk.Button(batch_ops_frame, text="删除", command=self.batch_delete_tasks, width=8).grid(row=0, column=3, padx=2)
        
        # 选择状态显示
        self.selection_status_var = tk.StringVar(value="已选择: 0 个任务")
        ttk.Label(batch_toolbar, textvariable=self.selection_status_var).pack(side=tk.RIGHT, padx=(10, 0))
        
        # 任务列表
        columns = ('name', 'status', 'progress', 'images')
        self.task_tree = ttk.Treeview(parent, columns=columns, show='headings', height=15, selectmode='extended')
        
        # 设置列标题
        self.task_tree.heading('name', text='任务名称')
        self.task_tree.heading('status', text='状态')
        self.task_tree.heading('progress', text='进度')
        self.task_tree.heading('images', text='图片数')
        
        # 设置列宽
        self.task_tree.column('name', width=300)
        self.task_tree.column('status', width=100)
        self.task_tree.column('progress', width=100)
        self.task_tree.column('images', width=100)
        
        # 添加滚动条
        scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=self.task_tree.yview)
        self.task_tree.configure(yscrollcommand=scrollbar.set)
        
        # 布局
        task_frame = ttk.Frame(parent)
        task_frame.pack(fill=tk.BOTH, expand=True)
        self.task_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 绑定事件
        self.task_tree.bind('<Double-1>', self.show_task_progress)
        self.task_tree.bind('<<TreeviewSelect>>', self.on_selection_changed)
    
    def _create_status_bar(self, parent: ttk.Frame) -> None:
        """创建状态栏"""
        status_frame = ttk.Frame(parent)
        status_frame.pack(fill=tk.X, pady=(5, 0))
        
        ttk.Separator(status_frame, orient=tk.HORIZONTAL).pack(fill=tk.X)
        
        info_frame = ttk.Frame(status_frame)
        info_frame.pack(fill=tk.X, pady=2)
        
        self.status_var = tk.StringVar(value="就绪")
        ttk.Label(info_frame, textvariable=self.status_var).pack(side=tk.LEFT)
        
        self.stats_var = tk.StringVar(value="任务: 0 | 运行: 0 | 完成: 0")
        ttk.Label(info_frame, textvariable=self.stats_var).pack(side=tk.LEFT)
        
        # 批量任务统计
        ttk.Label(info_frame, textvariable=self.batch_stats_var).pack(side=tk.RIGHT, padx=(20, 0))
    
    def new_task(self):
        """新建任务"""
        dialog = TaskDialog(self.root)
        result = dialog.show()
        
        if result:
            try:
                task = self.scheduler.create_task_from_url(
                    url=result['base_url'],
                    name=result['name'],
                    download_path=result.get('download_path'),
                    max_depth=result.get('max_depth', 1),
                    url_patterns=result.get('url_patterns', []),
                    scheduled_time=result.get('scheduled_time')
                )
                
                # 根据操作类型决定是否立即执行
                if result.get('save_only', False):
                    # 只保存，不执行
                    with self.scheduler.lock:
                        self.scheduler.tasks[task.id] = task
                    messagebox.showinfo("成功", f"任务已保存: {task.name}")
                else:
                    # 调度执行
                    self.scheduler.schedule_task(task)
                    if result.get('scheduled_time'):
                        messagebox.showinfo("成功", f"任务已创建并计划在 {result['scheduled_time'].strftime('%Y-%m-%d %H:%M')} 执行")
                    else:
                        messagebox.showinfo("成功", "任务已创建并开始执行")
                
                # 更新任务列表
                self.update_task_list()
                
            except Exception as e:
                self.logger.error(f"创建任务失败: {e}")
                messagebox.showerror("错误", f"创建任务失败: {e}")
    
    def open_batch_creator(self):
        """打开批量任务创建器"""
        try:
            dialog = BatchTaskDialog(self.root, self.scheduler, self.config)
            result = dialog.show()
            
            if result:
                # 批量任务已经在对话框中创建完成，只需要更新界面
                self.update_task_list()
                self._update_batch_stats()
                
                # 显示成功消息已经在对话框中显示，这里不需要重复显示
                
        except Exception as e:
            self.logger.error(f"打开批量任务创建器失败: {e}")
            messagebox.showerror("错误", f"打开批量任务创建器失败: {e}")
    
    def start_selected_task(self):
        """开始选中的任务"""
        selection = list(self.selected_tasks)
        if not selection:
            messagebox.showwarning("警告", "请先选择一个任务")
            return
        
        task_id = selection[0]
        task = self.scheduler.get_task(task_id)
        
        if task and task.status == TaskStatus.PENDING:
            self.scheduler.schedule_task(task)
            messagebox.showinfo("成功", "任务已开始")
    
    def cancel_selected_task(self):
        """取消选中的任务"""
        selection = list(self.selected_tasks)
        if not selection:
            messagebox.showwarning("警告", "请先选择一个任务")
            return
        
        task_id = selection[0]
        if messagebox.askyesno("确认", "确定要取消这个任务吗?"):
            if self.scheduler.cancel_task(task_id):
                messagebox.showinfo("成功", "任务已取消")
            else:
                messagebox.showerror("错误", "取消任务失败")
    
    def delete_selected_task(self):
        """删除选中的任务"""
        selection = list(self.selected_tasks)
        if not selection:
            messagebox.showwarning("警告", "请先选择一个任务")
            return
        
        task_id = selection[0]
        if messagebox.askyesno("确认", "确定要删除这个任务吗?（将永久删除）"):
            if self.scheduler.delete_task(task_id):
                # 从选中状态中移除已删除的任务
                self.selected_tasks.discard(task_id)
                self.update_task_list()
                messagebox.showinfo("成功", "任务已删除")
            else:
                messagebox.showerror("错误", "删除任务失败")
    
    def restart_selected_task(self):
        """重新下载选中的任务"""
        selection = list(self.selected_tasks)
        if not selection:
            messagebox.showwarning("警告", "请先选择一个任务")
            return
        
        task_id = selection[0]
        task = self.scheduler.get_task(task_id)
        
        if not task:
            messagebox.showerror("错误", "任务不存在")
            return
        
        if task.status not in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
            messagebox.showwarning("警告", "只能重新下载已完成、失败或取消的任务")
            return
        
        if messagebox.askyesno("确认", "确定要重新下载这个任务吗?"):
            # 重置任务状态
            task.status = TaskStatus.PENDING
            task.downloaded_images = 0
            task.failed_images = 0
            task.downloaded_size = 0
            task.started_time = None
            task.completed_time = None
            task.error_message = None
            
            # 重置所有图片状态
            for page in task.pages:
                for image in page.images:
                    image.status = DownloadStatus.WAITING
                    image.progress = 0.0
                    image.error_message = None
                    image.retry_count = 0
            
            # 重新调度任务
            self.scheduler.schedule_task(task)
            self.update_task_list()
            messagebox.showinfo("成功", "任务已重新开始")
    
    def preview_images(self):
        """预览选中任务的图片"""
        selection = list(self.selected_tasks)
        if not selection:
            messagebox.showwarning("警告", "请先选择一个任务")
            return
        
        task_id = selection[0]
        task = self.scheduler.get_task(task_id)
        
        if not task:
            messagebox.showerror("错误", "任务不存在")
            return
        
        # 收集所有已下载的图片 - 根据目录中实际存在的图片文件
        downloaded_images = []
        
        # 首先检查任务目录中实际存在的图片文件
        if task.download_path and os.path.exists(task.download_path):
            for filename in os.listdir(task.download_path):
                if filename.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp')):
                    file_path = os.path.join(task.download_path, filename)
                    downloaded_images.append(file_path)
        
        # 如果没有找到图片文件，再检查任务状态中的图片
        if not downloaded_images:
            for page in task.pages:
                for image in page.images:
                    if image.status == DownloadStatus.COMPLETED and os.path.exists(image.file_path):
                        downloaded_images.append(image.file_path)
        
        if not downloaded_images:
            messagebox.showinfo("提示", "该任务还没有已下载的图片")
            return
        
        try:
            # 优先使用增强的图片预览窗口
            try:
                from .enhanced_image_preview import EnhancedImagePreviewWindow
                preview_window = EnhancedImagePreviewWindow(self.root, downloaded_images)
                preview_window.show()
            except ImportError:
                # 如果增强窗口不可用，使用原有的预览窗口
                from .image_preview import ImagePreviewWindow
                preview_window = ImagePreviewWindow(self.root, downloaded_images)
                preview_window.show()
        except ImportError:
            # 如果没有预览窗口，就直接打开目录
            self._open_task_folder(task)
        except Exception as e:
            self.logger.error(f"打开图片预览失败: {e}")
            messagebox.showerror("错误", f"打开图片预览失败: {e}")
    
    def open_download_folder(self):
        """打开选中任务的下载目录"""
        selection = list(self.selected_tasks)
        if not selection:
            # 如果没有选中任务，打开默认下载目录
            default_path = self.config.get('download_path', './downloads')
            self._open_folder(default_path)
            return
        
        task_id = selection[0]
        task = self.scheduler.get_task(task_id)
        
        if not task:
            messagebox.showerror("错误", "任务不存在")
            return
        
        self._open_task_folder(task)
    
    def _open_task_folder(self, task):
        """打开任务的下载目录"""
        if task.download_path and os.path.exists(task.download_path):
            self._open_folder(task.download_path)
        else:
            # 如果任务目录不存在，打开默认目录
            default_path = self.config.get('download_path', './downloads')
            self._open_folder(default_path)
    
    def _open_folder(self, folder_path: str):
        """打开文件夹"""
        try:
            import subprocess
            import platform
            
            abs_path = os.path.abspath(folder_path)
            
            # 确保目录存在
            if not os.path.exists(abs_path):
                os.makedirs(abs_path, exist_ok=True)
            
            # 根据操作系统打开文件夹
            system = platform.system()
            if system == "Windows":
                subprocess.Popen(['explorer', abs_path])
            elif system == "Darwin":  # macOS
                subprocess.Popen(['open', abs_path])
            elif system == "Linux":
                subprocess.Popen(['xdg-open', abs_path])
            else:
                messagebox.showinfo("提示", f"下载目录: {abs_path}")
                
        except Exception as e:
            self.logger.error(f"打开文件夹失败: {e}")
            messagebox.showerror("错误", f"打开文件夹失败: {e}")
    

    
    def show_task_progress(self, event: tk.Event) -> None:
        """显示任务进度"""
        selection = list(self.selected_tasks)
        if not selection:
            return
        
        task_id = selection[0]
        task = self.scheduler.get_task(task_id)
        
        if task:
            if task_id not in self.progress_windows:
                self.progress_windows[task_id] = ProgressWindow(self.root, task, self.scheduler)
            else:
                try:
                    self.progress_windows[task_id].window.lift()
                except:
                    self.progress_windows[task_id] = ProgressWindow(self.root, task, self.scheduler)
    
    def open_settings(self):
        """打开设置"""
        dialog = SettingsDialog(self.root, self.config)
        result = dialog.show()
        if result:
            # 设置已经在对话框中保存了
            # 不需要额外操作
            pass
    
    def on_task_status_changed(self, task, old_status):
        """任务状态改变回调"""
        self.root.after(0, self.update_task_list)
    
    def update_task_list(self):
        """更新任务列表（保留选中状态）"""
        # 保存当前选中状态（使用持久化存储作为主要来源）
        current_selection = list(self.selected_tasks)
        
        # 清除现有项目
        for item in self.task_tree.get_children():
            self.task_tree.delete(item)
        
        # 添加任务
        tasks = self.scheduler.get_all_tasks()
        for task in tasks:
            status_text = self._get_status_text(task.status)
            progress_text = f"{task.progress:.1f}%" if task.total_images > 0 else "0%"
            images_text = f"{task.downloaded_images}/{task.total_images}"
            
            self.task_tree.insert('', tk.END, iid=task.id, values=(
                task.name,
                status_text,
                progress_text,
                images_text
            ))
        
        # 恢复选中状态（只恢复仍然存在的任务）
        valid_selection = [task_id for task_id in current_selection if self.task_tree.exists(task_id)]
        if valid_selection:
            self.task_tree.selection_set(valid_selection)
            self.selected_tasks = set(valid_selection)  # 更新持久化存储，移除无效任务
        
        # 更新选择状态显示
        selected_count = len(valid_selection)
        self.selection_status_var.set(f"已选择: {selected_count} 个任务")
        
        # 更新统计信息
        stats = self.scheduler.get_statistics()
        self.stats_var.set(
            f"任务: {stats['total_tasks']} | "
            f"运行: {stats['running_tasks']} | "
            f"完成: {stats['completed_tasks']}"
        )
        
        # 更新批量任务统计
        self._update_batch_stats()
    
    def _get_status_text(self, status: TaskStatus) -> str:
        """获取状态文本"""
        status_map = {
            TaskStatus.PENDING: "等待",
            TaskStatus.RUNNING: "运行中",
            TaskStatus.COMPLETED: "完成",
            TaskStatus.FAILED: "失败",
            TaskStatus.CANCELLED: "取消",
            TaskStatus.SCHEDULED: "计划中"
        }
        return status_map.get(status, "未知")
    
    def _update_interface(self):
        """定时更新界面"""
        if not self.scheduler.is_running:
            return  # 如果调度器已停止，不再更新
            
        try:
            self.update_task_list()
        except Exception as e:
            self.logger.warning(f"更新界面失败: {e}")
        
        # 保存定时器ID以便取消
        self._update_timer = self.root.after(5000, self._update_interface)
    
    def on_closing(self):
        """窗口关闭事件"""
        try:
            # 停止定时器
            update_timer = getattr(self, '_update_timer', None)
            if update_timer:
                self.root.after_cancel(update_timer)
            
            # 快速停止调度器
            self.scheduler.is_running = False
            
            # 关闭所有进度窗口
            for window in self.progress_windows.values():
                try:
                    window.close()
                except:
                    pass
            
            # 立即销毁窗口，不等待确认
            self.root.destroy()
            
        except Exception as e:
            self.logger.error(f"关闭窗口时出错: {e}")
            # 强制退出
            import os
            os._exit(0)
    
    def _update_batch_stats(self):
        """更新批量任务统计"""
        try:
            tasks = self.scheduler.get_all_tasks()
            
            # 统计所有任务（不再区分批量任务和单个任务）
            pending_tasks = sum(1 for task in tasks if task.status == TaskStatus.PENDING)
            running_tasks = sum(1 for task in tasks if task.status == TaskStatus.RUNNING)
            completed_tasks = sum(1 for task in tasks if task.status == TaskStatus.COMPLETED)
            total_tasks = len(tasks)
            
            if total_tasks > 0:
                self.batch_stats_var.set(
                    f"任务统计: 总计{total_tasks}个 | "
                    f"排队{pending_tasks}个 | 运行{running_tasks}个 | 完成{completed_tasks}个"
                )
            else:
                self.batch_stats_var.set("任务统计: 0个任务")
                
        except Exception as e:
            self.logger.warning(f"更新任务统计失败: {e}")
    
    # =============批量操作方法=============
    
    def on_selection_changed(self, event):
        """选择变化事件"""
        current_selection = self.task_tree.selection()
        selected_count = len(current_selection)
        self.selection_status_var.set(f"已选择: {selected_count} 个任务")
        
        # 更新持久化选中状态
        self.selected_tasks = set(current_selection)
    
    def select_all_tasks(self):
        """全选任务"""
        all_items = self.task_tree.get_children()
        self.task_tree.selection_set(all_items)
        # 更新持久化存储
        self.selected_tasks = set(all_items)
        self.selection_status_var.set(f"已选择: {len(all_items)} 个任务")
    
    def invert_selection(self):
        """反选任务"""
        all_items = self.task_tree.get_children()
        current_selection = set(self.task_tree.selection())
        new_selection = [item for item in all_items if item not in current_selection]
        self.task_tree.selection_set(new_selection)
        # 更新持久化存储
        self.selected_tasks = set(new_selection)
        self.selection_status_var.set(f"已选择: {len(new_selection)} 个任务")
    
    def clear_selection(self):
        """清空选择"""
        self.task_tree.selection_remove(self.task_tree.selection())
        # 更新持久化存储
        self.selected_tasks = set()
        self.selection_status_var.set("已选择: 0 个任务")
    
    def batch_start_tasks(self):
        """批量开始任务"""
        selection = list(self.selected_tasks)
        if not selection:
            messagebox.showwarning("警告", "请先选择要开始的任务")
            return
        
        started_count = 0
        for task_id in selection:
            task = self.scheduler.get_task(task_id)
            if task and task.status == TaskStatus.PENDING:
                self.scheduler.schedule_task(task)
                started_count += 1
        
        if started_count > 0:
            messagebox.showinfo("成功", f"已开始 {started_count} 个任务")
        else:
            messagebox.showwarning("提示", "没有可以开始的任务（只能开始等待中的任务）")
    
    def batch_pause_tasks(self):
        """批量暂停任务（实际为取消正在运行的任务）"""
        selection = list(self.selected_tasks)
        if not selection:
            messagebox.showwarning("警告", "请先选择要暂停的任务")
            return
        
        paused_count = 0
        for task_id in selection:
            task = self.scheduler.get_task(task_id)
            if task and task.status == TaskStatus.RUNNING:
                if self.scheduler.cancel_task(task_id):
                    paused_count += 1
        
        if paused_count > 0:
            messagebox.showinfo("成功", f"已停止 {paused_count} 个运行中的任务")
        else:
            messagebox.showwarning("提示", "没有可以停止的任务（只能停止运行中的任务）")
    
    def batch_cancel_tasks(self):
        """批量取消任务"""
        selection = list(self.selected_tasks)
        if not selection:
            messagebox.showwarning("警告", "请先选择要取消的任务")
            return
        
        if not messagebox.askyesno("确认", f"确定要取消选中的 {len(selection)} 个任务吗？"):
            return
        
        cancelled_count = 0
        for task_id in selection:
            if self.scheduler.cancel_task(task_id):
                cancelled_count += 1
        
        if cancelled_count > 0:
            messagebox.showinfo("成功", f"已取消 {cancelled_count} 个任务")
        else:
            messagebox.showerror("错误", "取消任务失败")
    
    def batch_delete_tasks(self):
        """批量删除任务"""
        selection = list(self.selected_tasks)
        if not selection:
            messagebox.showwarning("警告", "请先选择要删除的任务")
            return
        
        if not messagebox.askyesno("确认", f"确定要删除选中的 {len(selection)} 个任务吗？（将永久删除）"):
            return
        
        deleted_count = 0
        for task_id in selection:
            if self.scheduler.delete_task(task_id):
                deleted_count += 1
                # 从选中状态中移除已删除的任务
                self.selected_tasks.discard(task_id)
        
        if deleted_count > 0:
            self.update_task_list()
            messagebox.showinfo("成功", f"已删除 {deleted_count} 个任务")
        else:
            messagebox.showerror("错误", "删除任务失败")