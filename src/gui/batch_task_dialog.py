# -*- coding: utf-8 -*-
"""
批量任务对话框模块
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable
import threading
import os

from ..models.data_models import BatchTaskConfig, BatchCreationResult, TaskPreviewInfo
from ..core.batch_task_creator import BatchTaskCreator

class BatchTaskDialog:
    """批量任务创建对话框"""
    
    def __init__(self, parent, scheduler, config):
        """
        初始化对话框
        
        Args:
            parent: 父窗口
            scheduler: 任务调度器
            config: 配置对象
        """
        self.parent = parent
        self.scheduler = scheduler
        self.config = config
        self.result = None
        
        # 界面变量
        self.url_var: tk.StringVar = tk.StringVar()
        
        # 创建批量任务创建器
        self.batch_creator = BatchTaskCreator(
            config.get_all(),
            scheduler, 
            progress_callback=self.on_progress_update
        )
        
        # 界面状态
        self.is_analyzing = False
        self.analysis_thread = None
        self.preview_tasks = []
        
        # 界面控件变量声明（在_create_widgets方法中初始化）
        self.analyze_button: ttk.Button
        self.detect_images_var: tk.BooleanVar
        self.skip_existing_var: tk.BooleanVar
        self.max_pages_var: tk.IntVar
        self.timeout_var: tk.IntVar
        self.stats_frame: ttk.Frame
        self.stats_var: tk.StringVar
        self.task_tree: ttk.Treeview
        self.progress_var: tk.StringVar
        self.exec_mode_var: tk.StringVar
        self.date_var: tk.StringVar
        self.time_var: tk.StringVar
        self.create_button: ttk.Button
        self.save_button: ttk.Button
        self.cancel_button: ttk.Button
        self.create_thread: Optional[threading.Thread] = None
        self.save_thread: Optional[threading.Thread] = None
        self._save_cancelled = False
        self._create_cancelled = False
        
        # 创建对话框窗口
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("批量任务创建")
        self.dialog.geometry("900x800")  # 增大窗口尺寸
        self.dialog.resizable(True, True)
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # 居中显示
        self.dialog.geometry("+%d+%d" % (
            parent.winfo_rootx() + 50,
            parent.winfo_rooty() + 50
        ))
        
        self._create_widgets()
        self._load_default_values()
        
        # 处理关闭事件
        self.dialog.protocol("WM_DELETE_WINDOW", self.on_closing)
    
    def _create_widgets(self):
        """创建界面控件"""
        main_frame = ttk.Frame(self.dialog, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 基本信息区域
        self._create_basic_info_section(main_frame)
        
        # 分析选项区域
        self._create_analysis_options_section(main_frame)
        
        # 任务预览区域
        self._create_task_preview_section(main_frame)
        
        # 执行选项区域
        self._create_execution_options_section(main_frame)
        
        # 按钮区域
        self._create_button_section(main_frame)
    
    def _create_basic_info_section(self, parent):
        """创建基本信息区域"""
        basic_frame = ttk.LabelFrame(parent, text="基本信息", padding=10)
        basic_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 主页面URL
        ttk.Label(basic_frame, text="主页面URL:").grid(row=0, column=0, sticky=tk.W, pady=5)
        url_frame = ttk.Frame(basic_frame)
        url_frame.grid(row=0, column=1, columnspan=2, sticky=tk.EW, padx=(10, 0), pady=5)
        
        ttk.Entry(url_frame, textvariable=self.url_var, width=50).pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.analyze_button = ttk.Button(url_frame, text="分析", command=self.analyze_main_page, width=10)
        self.analyze_button.pack(side=tk.RIGHT, padx=(5, 0))
        
        # 配置列权重
        basic_frame.columnconfigure(1, weight=1)
    
    def _create_analysis_options_section(self, parent):
        """创建分析选项区域"""
        options_frame = ttk.LabelFrame(parent, text="分析选项", padding=10)
        options_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 第一行选项
        row1_frame = ttk.Frame(options_frame)
        row1_frame.pack(fill=tk.X, pady=5)
        
        self.detect_images_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(row1_frame, text="检测图片内容", variable=self.detect_images_var).pack(side=tk.LEFT)
        
        self.skip_existing_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(row1_frame, text="跳过已下载目录", variable=self.skip_existing_var).pack(side=tk.LEFT, padx=(20, 0))
        
        # 第二行选项
        row2_frame = ttk.Frame(options_frame)
        row2_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(row2_frame, text="最大页面数:").pack(side=tk.LEFT)
        self.max_pages_var = tk.IntVar(value=100)
        ttk.Spinbox(row2_frame, from_=10, to=500, textvariable=self.max_pages_var, width=10).pack(side=tk.LEFT, padx=(5, 20))
        
        ttk.Label(row2_frame, text="超时设置:").pack(side=tk.LEFT)
        self.timeout_var = tk.IntVar(value=30)
        ttk.Spinbox(row2_frame, from_=10, to=120, textvariable=self.timeout_var, width=10).pack(side=tk.LEFT, padx=(5, 0))
        ttk.Label(row2_frame, text="秒").pack(side=tk.LEFT, padx=(2, 0))
    
    def _create_task_preview_section(self, parent):
        """创建任务预览区域"""
        preview_frame = ttk.LabelFrame(parent, text="任务预览", padding=10)
        preview_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # 统计信息
        self.stats_frame = ttk.Frame(preview_frame)
        self.stats_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.stats_var = tk.StringVar(value="发现页面: 0个  有效任务: 0个  跳过: 0个")
        ttk.Label(self.stats_frame, textvariable=self.stats_var, font=('Arial', 9, 'bold')).pack(side=tk.LEFT)
        
        # 任务列表
        list_frame = ttk.Frame(preview_frame)
        list_frame.pack(fill=tk.BOTH, expand=True)
        
        # 创建Treeview
        columns = ('status', 'url', 'directory', 'images')
        self.task_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=12)
        
        # 设置列标题
        self.task_tree.heading('#0', text='选择')
        self.task_tree.heading('status', text='状态')
        self.task_tree.heading('url', text='页面URL')
        self.task_tree.heading('directory', text='目录名')
        self.task_tree.heading('images', text='预估图片数')
        
        # 设置列宽
        self.task_tree.column('#0', width=60)
        self.task_tree.column('status', width=80)
        self.task_tree.column('url', width=250)
        self.task_tree.column('directory', width=150)
        self.task_tree.column('images', width=80)
        
        # 滚动条
        tree_scroll = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.task_tree.yview)
        self.task_tree.configure(yscrollcommand=tree_scroll.set)
        
        # 布局
        self.task_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 绑定事件
        self.task_tree.bind('<Button-1>', self.on_tree_click)
        
        # 选择按钮
        select_frame = ttk.Frame(preview_frame)
        select_frame.pack(fill=tk.X, pady=(10, 0))
        
        ttk.Button(select_frame, text="全选", command=self.select_all, width=8).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(select_frame, text="全不选", command=self.select_none, width=8).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(select_frame, text="反选", command=self.select_inverse, width=8).pack(side=tk.LEFT, padx=(0, 5))
        
        # 进度显示
        self.progress_var = tk.StringVar(value="")
        ttk.Label(select_frame, textvariable=self.progress_var, foreground='blue').pack(side=tk.RIGHT)
    
    def _create_execution_options_section(self, parent):
        """创建执行选项区域"""
        exec_frame = ttk.LabelFrame(parent, text="执行选项", padding=10)
        exec_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 执行方式选择
        self.exec_mode_var = tk.StringVar(value="immediate")
        
        ttk.Radiobutton(exec_frame, text="立即执行全部", variable=self.exec_mode_var, 
                       value="immediate", command=self.on_exec_mode_changed).pack(anchor=tk.W, pady=2)
        
        # 计划执行
        schedule_frame = ttk.Frame(exec_frame)
        schedule_frame.pack(fill=tk.X, pady=2)
        
        ttk.Radiobutton(schedule_frame, text="计划执行:", variable=self.exec_mode_var,
                       value="scheduled", command=self.on_exec_mode_changed).pack(side=tk.LEFT)
        
        self.date_var = tk.StringVar(value=(datetime.now() + timedelta(hours=1)).strftime("%Y-%m-%d"))
        ttk.Entry(schedule_frame, textvariable=self.date_var, width=12).pack(side=tk.LEFT, padx=(10, 5))
        
        self.time_var = tk.StringVar(value=(datetime.now() + timedelta(hours=1)).strftime("%H:%M"))
        ttk.Entry(schedule_frame, textvariable=self.time_var, width=8).pack(side=tk.LEFT, padx=(0, 5))
        
        ttk.Radiobutton(exec_frame, text="仅创建任务，手动执行", variable=self.exec_mode_var,
                       value="create_only", command=self.on_exec_mode_changed).pack(anchor=tk.W, pady=2)
        
        # 初始化状态
        self.on_exec_mode_changed()
    
    def _create_button_section(self, parent):
        """创建按钮区域"""
        button_frame = ttk.Frame(parent)
        button_frame.pack(fill=tk.X, pady=(20, 0))
        
        # 分隔线
        ttk.Separator(button_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=(0, 10))
        
        # 按钮容器
        buttons_container = ttk.Frame(button_frame)
        buttons_container.pack(fill=tk.X)
        
        # 左侧按钮
        left_buttons = ttk.Frame(buttons_container)
        left_buttons.pack(side=tk.LEFT)
        
        self.create_button = ttk.Button(left_buttons, text="创建任务", command=self.create_batch_tasks, width=12)
        self.create_button.pack(side=tk.LEFT, padx=(0, 10))
        self.create_button.configure(state='disabled')  # 初始禁用
        
        self.save_button = ttk.Button(left_buttons, text="保存任务", command=self.save_batch_tasks, width=12)
        self.save_button.pack(side=tk.LEFT, padx=(0, 10))
        self.save_button.configure(state='disabled')  # 初始禁用
        
        # 右侧按钮
        self.cancel_button = ttk.Button(buttons_container, text="取消", command=self.on_closing, width=8)
        self.cancel_button.pack(side=tk.RIGHT)
    
    def _load_default_values(self):
        """加载默认值"""
        # 可以从配置中加载默认URL或其他设置
        default_url = self.config.get('batch_task.last_main_url', '')
        if default_url:
            self.url_var.set(default_url)
    
    def analyze_main_page(self):
        """分析主页面"""
        url = self.url_var.get().strip()
        if not url:
            messagebox.showerror("错误", "请输入主页面URL")
            return
        
        if not (url.startswith('http://') or url.startswith('https://')):
            messagebox.showerror("错误", "URL必须以http://或https://开头")
            return
        
        if self.is_analyzing:
            # 取消当前分析
            self.batch_creator.cancel_operation()
            return
        
        # 保存URL到配置
        self.config.set('batch_task.last_main_url', url)
        self.config.save()
        
        # 开始分析
        self.is_analyzing = True
        self.analyze_button.configure(text="取消", state='normal')
        self.create_button.configure(state='disabled')
        
        # 清空预览列表
        for item in self.task_tree.get_children():
            self.task_tree.delete(item)
        
        self.stats_var.set("正在分析...")
        self.progress_var.set("")
        
        # 在后台线程中执行分析
        self.analysis_thread = threading.Thread(target=self._analyze_in_background, args=(url,), daemon=True)
        self.analysis_thread.start()
    
    def _analyze_in_background(self, url):
        """在后台线程中分析"""
        try:
            # 创建配置
            batch_config = BatchTaskConfig(
                main_url=url,
                max_pages=self.max_pages_var.get(),
                timeout_seconds=self.timeout_var.get(),
                skip_existing=self.skip_existing_var.get(),
                detect_images=self.detect_images_var.get()
            )
            
            # 执行分析
            result = self.batch_creator.create_batch_tasks(batch_config)
            
            # 在主线程中更新界面
            self.dialog.after(0, self._on_analysis_complete, result)
            
        except Exception as e:
            self.dialog.after(0, self._on_analysis_error, str(e))
    
    def _on_analysis_complete(self, result: BatchCreationResult):
        """分析完成回调"""
        self.is_analyzing = False
        self.analyze_button.configure(text="分析", state='normal')
        
        if result.valid_tasks > 0:
            # 这里需要从 result.created_tasks 创建 preview_tasks
            self.preview_tasks = []
            for task in result.created_tasks:
                preview_info = TaskPreviewInfo(
                    url=task.base_url,
                    estimated_images=getattr(task, 'total_images', 0),
                    estimated_size="未知",
                    directory_name=task.name.split(': ')[-1] if ': ' in task.name else task.name,
                    status="可用",
                    selected=True
                )
                self.preview_tasks.append(preview_info)
            
            self._update_preview_list()
            
            # 更新统计信息
            total = result.total_found
            valid = result.valid_tasks
            skipped = result.duplicate_skipped
            
            self.stats_var.set(f"发现页面: {total}个  有效任务: {valid}个  跳过: {skipped}个")
            
            self.create_button.configure(state='normal')
            self.save_button.configure(state='normal')  # 启用保存按钮
        else:
            # 更新统计信息，即使没有有效任务也要显示
            total = result.total_found
            valid = result.valid_tasks  
            skipped = result.duplicate_skipped
            failed = result.failed_analysis
            
            self.stats_var.set(f"发现页面: {total}个  有效任务: {valid}个  跳过: {skipped}个  失败: {failed}个")
            
            if total == 0:
                messagebox.showwarning("提示", "未在主页面中找到任何子页面")
            elif failed > 0:
                messagebox.showwarning("提示", f"分析完成，但没有找到有效任务。{failed}个页面分析失败")
            else:
                messagebox.showwarning("提示", "分析完成，但所有任务都已存在或无效")
        
        self.progress_var.set("")
    
    def _on_analysis_error(self, error_message: str):
        """分析错误回调"""
        self.is_analyzing = False
        self.analyze_button.configure(text="分析", state='normal')
        self.progress_var.set("")
        
        messagebox.showerror("错误", f"分析过程中发生错误: {error_message}")
    
    def _update_preview_list(self):
        """更新预览列表"""
        # 清空现有项
        for item in self.task_tree.get_children():
            self.task_tree.delete(item)
        
        # 添加新项
        for i, task in enumerate(self.preview_tasks):
            status = task.status
            
            item_id = self.task_tree.insert('', 'end',
                text='☑' if task.selected else '☐',  # 选择状态
                values=(
                    status,
                    task.url[:60] + '...' if len(task.url) > 60 else task.url,
                    task.directory_name,
                    str(task.estimated_images)
                ),
                tags=('selected' if task.selected else 'unselected',)
            )
            
            # 存储任务索引到tags中
            self.task_tree.item(item_id, tags=(f'task_{i}', 'selected' if task.selected else 'unselected'))
        
        # 配置标签样式
        self.task_tree.tag_configure('selected', background='lightblue')
        self.task_tree.tag_configure('unselected', background='lightgray')
    
    def on_tree_click(self, event):
        """处理树形控件点击事件"""
        region = self.task_tree.identify_region(event.x, event.y)
        if region == "tree":
            item = self.task_tree.identify_row(event.y)
            if item:
                # 从 tags 中获取任务索引
                tags = self.task_tree.item(item, 'tags')
                task_index = None
                for tag in tags:
                    if tag.startswith('task_'):
                        task_index = int(tag.split('_')[1])
                        break
                
                if task_index is not None and task_index < len(self.preview_tasks):
                    task = self.preview_tasks[task_index]
                    
                    if task.status == "可用":
                        # 切换选择状态
                        task.selected = not task.selected
                        new_text = '☑' if task.selected else '☐'
                        self.task_tree.item(item, text=new_text)
                        
                        # 更新标签
                        new_tags = [f'task_{task_index}']
                        new_tags.append('selected' if task.selected else 'unselected')
                        self.task_tree.item(item, tags=tuple(new_tags))
    
    def select_all(self):
        """全选"""
        for task in self.preview_tasks:
            if task.status == "可用":
                task.selected = True
        self._update_selection_display()
    
    def select_none(self):
        """全不选"""
        for task in self.preview_tasks:
            task.selected = False
        self._update_selection_display()
    
    def select_inverse(self):
        """反选"""
        for task in self.preview_tasks:
            if task.status == "可用":
                task.selected = not task.selected
        self._update_selection_display()
    
    def on_exec_mode_changed(self):
        """执行模式改变"""
        # 可以根据选择的执行模式更新界面状态
        pass
    
    def create_batch_tasks(self):
        """创建批量任务"""
        selected_tasks = [task for task in self.preview_tasks if task.selected]
        
        if not selected_tasks:
            messagebox.showwarning("提示", "请至少选择一个任务")
            return
        
        exec_mode = self.exec_mode_var.get()
        
        if exec_mode == "scheduled":
            # 计划执行
            schedule_time = f"{self.date_var.get()} {self.time_var.get()}"
            messagebox.showinfo("提示", "计划执行功能尚未实现")
            return
        
        # 禁用按钮，显示正在处理
        self.create_button.configure(state='disabled', text='正在创建...')
        self.save_button.configure(state='disabled')
        self.cancel_button.configure(state='disabled')
        
        # 更新进度显示
        action_text = "立即执行" if exec_mode == "immediate" else "仅创建"
        self.progress_var.set(f"正在{action_text} {len(selected_tasks)} 个任务...")
        
        # 在后台线程中执行创建操作
        self.create_thread = threading.Thread(
            target=self._create_tasks_in_background, 
            args=(selected_tasks, exec_mode), 
            daemon=True
        )
        self.create_thread.start()
    
    def _create_tasks_in_background(self, selected_tasks, exec_mode):
        """在后台线程中创建任务"""
        try:
            created_count = 0
            
            for i, task in enumerate(selected_tasks):
                if getattr(self, '_create_cancelled', False):
                    break
                
                try:
                    # 更新进度
                    progress_msg = f"正在处理任务 {i+1}/{len(selected_tasks)}: {task.directory_name[:30]}..."
                    self.dialog.after(0, lambda msg=progress_msg: self.progress_var.set(msg))
                    
                    if exec_mode == "immediate":
                        # 立即执行：创建任务并调度（但不自动解析，在执行时解析）
                        download_task = self.scheduler.create_task_from_url(
                            url=task.url,
                            name=task.directory_name,
                            max_depth=1,
                            auto_parse=False  # 不自动解析，在执行时再解析
                        )
                        
                        # 调度执行
                        self.scheduler.schedule_task(download_task)
                        
                    else:  # create_only
                        # 仅创建任务（不自动解析，留在执行时解析）
                        download_task = self.scheduler.create_task_from_url(
                            url=task.url,
                            name=task.directory_name,
                            max_depth=1,
                            auto_parse=False  # 不自动解析
                        )
                    
                    created_count += 1
                    
                except Exception as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"创建任务失败 {task.url}: {e}")
                    continue
            
            # 在主线程中更新UI
            self.dialog.after(0, self._on_create_complete, created_count, len(selected_tasks), exec_mode)
            
        except Exception as e:
            self.dialog.after(0, self._on_create_error, str(e))
    
    def _on_create_complete(self, created_count: int, total_count: int, exec_mode: str):
        """创建完成回调"""
        # 恢复按钮状态
        self.create_button.configure(state='normal', text='创建任务')
        self.save_button.configure(state='normal')
        self.cancel_button.configure(state='normal')
        
        self.progress_var.set("")
        
        if exec_mode == "immediate":
            if created_count == total_count:
                messagebox.showinfo("成功", f"已创建 {created_count} 个任务并开始执行")
            else:
                messagebox.showwarning("部分成功", f"已创建 {created_count}/{total_count} 个任务并开始执行")
        else:
            if created_count == total_count:
                messagebox.showinfo("成功", f"已创建 {created_count} 个任务")
            else:
                messagebox.showwarning("部分成功", f"已创建 {created_count}/{total_count} 个任务")
        
        # 设置结果并关闭对话框
        self.result = {
            'status': 'created',
            'created_count': created_count,
            'total_count': total_count,
            'execution_mode': exec_mode
        }
        
        # 延迟关闭，让用户看到成功消息
        self.dialog.after(1000, self.on_closing)
    
    def _on_create_error(self, error_message: str):
        """创建错误回调"""
        # 恢复按钮状态
        self.create_button.configure(state='normal', text='创建任务')
        self.save_button.configure(state='normal')
        self.cancel_button.configure(state='normal')
        
        self.progress_var.set("")
        
        messagebox.showerror("错误", f"创建任务失败: {error_message}")
    
    def save_batch_tasks(self):
        """保存批量任务（仅保存，不执行）"""
        selected_tasks = [task for task in self.preview_tasks if task.selected]
        
        if not selected_tasks:
            messagebox.showwarning("提示", "请至少选择一个任务")
            return
        
        # 禁用按钮，显示正在保存
        self.save_button.configure(state='disabled', text='正在保存...')
        self.create_button.configure(state='disabled')
        self.cancel_button.configure(state='disabled')
        
        # 更新进度显示
        self.progress_var.set(f"正在保存 {len(selected_tasks)} 个任务...")
        
        # 在后台线程中执行保存操作
        self.save_thread = threading.Thread(
            target=self._save_tasks_in_background, 
            args=(selected_tasks,), 
            daemon=True
        )
        self.save_thread.start()
    
    def _save_tasks_in_background(self, selected_tasks):
        """在后台线程中保存任务"""
        try:
            saved_count = 0
            
            for i, task in enumerate(selected_tasks):
                if getattr(self, '_save_cancelled', False):
                    break
                
                try:
                    # 更新进度
                    progress_msg = f"正在保存任务 {i+1}/{len(selected_tasks)}: {task.directory_name[:30]}..."
                    self.dialog.after(0, lambda msg=progress_msg: self.progress_var.set(msg))
                    
                    # 直接使用调度器的方法创建任务（不自动解析）
                    download_task = self.scheduler.create_task_from_url(
                        url=task.url,
                        name=task.directory_name,
                        max_depth=1,
                        auto_parse=False  # 不自动解析，在执行时再解析
                    )
                    
                    saved_count += 1
                    
                except Exception as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"保存任务失败 {task.url}: {e}")
                    continue
            
            # 在主线程中更新UI
            self.dialog.after(0, self._on_save_complete, saved_count, len(selected_tasks))
            
        except Exception as e:
            self.dialog.after(0, self._on_save_error, str(e))

    
    def _on_save_complete(self, saved_count: int, total_count: int):
        """保存完成回调"""
        # 恢复按钮状态
        self.save_button.configure(state='normal', text='保存任务')
        self.create_button.configure(state='normal')
        self.cancel_button.configure(state='normal')
        
        self.progress_var.set("")
        
        if saved_count == total_count:
            messagebox.showinfo("成功", f"已保存 {saved_count} 个任务，可手动开始执行")
        else:
            messagebox.showwarning("部分成功", f"已保存 {saved_count}/{total_count} 个任务")
        
        # 设置结果并关闭对话框
        self.result = {
            'status': 'saved',
            'saved_count': saved_count,
            'total_count': total_count,
            'execution_mode': 'create_only'
        }
        
        # 延迟关闭，让用户看到成功消息
        self.dialog.after(1000, self.on_closing)
    
    def _on_save_error(self, error_message: str):
        """保存错误回调"""
        # 恢复按钮状态
        self.save_button.configure(state='normal', text='保存任务')
        self.create_button.configure(state='normal')
        self.cancel_button.configure(state='normal')
        
        self.progress_var.set("")
        
        messagebox.showerror("错误", f"保存任务失败: {error_message}")
    
    def on_progress_update(self, message: str, progress: Optional[float] = None):
        """进度更新回调"""
        if hasattr(self, 'progress_var'):
            self.progress_var.set(message)
    
    def _update_selection_display(self):
        """更新选择状态显示"""
        for item in self.task_tree.get_children():
            # 从 tags 中获取任务索引
            tags = self.task_tree.item(item, 'tags')
            task_index = None
            for tag in tags:
                if tag.startswith('task_'):
                    task_index = int(tag.split('_')[1])
                    break
            
            if task_index is not None and task_index < len(self.preview_tasks):
                task = self.preview_tasks[task_index]
                
                if task.status == "可用":
                    new_text = '☑' if task.selected else '☐'
                    self.task_tree.item(item, text=new_text)
                    new_tags = [f'task_{task_index}']
                    new_tags.append('selected' if task.selected else 'unselected')
                    self.task_tree.item(item, tags=tuple(new_tags))
    
    def on_closing(self):
        """关闭对话框"""
        # 检查是否有后台任务正在运行
        active_operations = []
        
        if self.is_analyzing:
            active_operations.append("页面分析")
            
        if hasattr(self, 'save_thread') and self.save_thread and self.save_thread.is_alive():
            active_operations.append("任务保存")
            
        if hasattr(self, 'create_thread') and self.create_thread and self.create_thread.is_alive():
            active_operations.append("任务创建")
        
        # 如果有正在进行的操作，询问用户是否确认关闭
        if active_operations:
            operations_text = "、".join(active_operations)
            if messagebox.askyesno("确认", f"正在进行{operations_text}，确定要关闭吗？"):
                # 取消所有后台操作
                if self.is_analyzing:
                    self.batch_creator.cancel_operation()
                
                if hasattr(self, 'save_thread') and self.save_thread and self.save_thread.is_alive():
                    self._save_cancelled = True
                    
                if hasattr(self, 'create_thread') and self.create_thread and self.create_thread.is_alive():
                    self._create_cancelled = True
                
                self.dialog.destroy()
            # 如果用户选择不关闭，则什么也不做
        else:
            # 没有正在进行的操作，直接关闭
            self.dialog.destroy()
    
    def show(self):
        """显示对话框并返回结果"""
        self.dialog.wait_window()
        return self.result