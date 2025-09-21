#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
任务对话框模块
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import os

# 导入配置管理模块
from ..core.config import Config

class TaskDialog:
    """任务创建/编辑对话框"""
    
    def __init__(self, parent, title="新建任务", task_data=None):
        """
        初始化对话框
        
        Args:
            parent: 父窗口
            title: 对话框标题
            task_data: 任务数据（编辑模式）
        """
        self.parent = parent
        self.result = None
        self.task_data = task_data or {}
        
        # 初始化配置管理器
        self.config = Config()
        
        # 创建对话框窗口
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(title)
        self.dialog.geometry("650x650")  # 增加窗口高度
        self.dialog.resizable(False, False)
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # 居中显示
        self.dialog.geometry("+%d+%d" % (
            parent.winfo_rootx() + 50,
            parent.winfo_rooty() + 50
        ))
        
        self._create_widgets()
        self._load_data()
    
    def _create_widgets(self):
        """创建界面控件"""
        main_frame = ttk.Frame(self.dialog, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 基本信息
        basic_frame = ttk.LabelFrame(main_frame, text="基本信息", padding=10)
        basic_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 任务名称
        ttk.Label(basic_frame, text="任务名称:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.name_var = tk.StringVar()
        ttk.Entry(basic_frame, textvariable=self.name_var, width=50).grid(
            row=0, column=1, columnspan=2, sticky=tk.EW, padx=(10, 0), pady=5
        )
        
        # 目标URL
        ttk.Label(basic_frame, text="目标URL:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.url_var = tk.StringVar()
        ttk.Entry(basic_frame, textvariable=self.url_var, width=50).grid(
            row=1, column=1, columnspan=2, sticky=tk.EW, padx=(10, 0), pady=5
        )
        
        # 下载目录
        ttk.Label(basic_frame, text="下载目录:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.path_var = tk.StringVar()
        ttk.Entry(basic_frame, textvariable=self.path_var, width=40).grid(
            row=2, column=1, sticky=tk.EW, padx=(10, 0), pady=5
        )
        ttk.Button(basic_frame, text="浏览", command=self.browse_directory).grid(
            row=2, column=2, padx=(5, 0), pady=5
        )
        
        # 配置列权重
        basic_frame.columnconfigure(1, weight=1)
        
        # 高级选项
        advanced_frame = ttk.LabelFrame(main_frame, text="高级选项", padding=10)
        advanced_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 最大深度
        ttk.Label(advanced_frame, text="最大深度:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.depth_var = tk.IntVar(value=1)
        depth_spin = ttk.Spinbox(advanced_frame, from_=1, to=10, textvariable=self.depth_var, width=10)
        depth_spin.grid(row=0, column=1, sticky=tk.W, padx=(10, 0), pady=5)
        
        # URL模式
        ttk.Label(advanced_frame, text="URL模式:").grid(row=1, column=0, sticky=tk.NW, pady=5)
        pattern_frame = ttk.Frame(advanced_frame)
        pattern_frame.grid(row=1, column=1, columnspan=2, sticky=tk.EW, padx=(10, 0), pady=5)
        
        self.pattern_text = tk.Text(pattern_frame, height=3, width=40)  # 减少高度
        pattern_scroll = ttk.Scrollbar(pattern_frame, orient=tk.VERTICAL, command=self.pattern_text.yview)
        self.pattern_text.configure(yscrollcommand=pattern_scroll.set)
        
        self.pattern_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        pattern_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 帮助文本
        help_text = "每行一个模式，支持:\n{1-10} 数字范围\n{a,b,c} 列表\n* 通配符"
        ttk.Label(advanced_frame, text=help_text, font=('Arial', 8), foreground='gray').grid(
            row=2, column=1, columnspan=2, sticky=tk.W, padx=(10, 0), pady=5
        )
        
        # 调度选项
        schedule_frame = ttk.LabelFrame(main_frame, text="计划执行", padding=10)
        schedule_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 立即执行/计划执行
        self.schedule_type_var = tk.StringVar(value="immediate")
        ttk.Radiobutton(
            schedule_frame, 
            text="立即执行", 
            variable=self.schedule_type_var, 
            value="immediate",
            command=self.on_schedule_type_changed
        ).grid(row=0, column=0, sticky=tk.W, pady=2)
        
        ttk.Radiobutton(
            schedule_frame,
            text="计划执行",
            variable=self.schedule_type_var,
            value="scheduled",
            command=self.on_schedule_type_changed
        ).grid(row=1, column=0, sticky=tk.W, pady=2)
        
        # 计划时间
        self.schedule_frame = ttk.Frame(schedule_frame)
        self.schedule_frame.grid(row=1, column=1, sticky=tk.EW, padx=(20, 0))
        
        ttk.Label(self.schedule_frame, text="日期:").grid(row=0, column=0, sticky=tk.W, padx=5)
        self.date_var = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
        ttk.Entry(self.schedule_frame, textvariable=self.date_var, width=12).grid(
            row=0, column=1, padx=5
        )
        
        ttk.Label(self.schedule_frame, text="时间:").grid(row=0, column=2, sticky=tk.W, padx=5)
        self.time_var = tk.StringVar(value="12:00")
        ttk.Entry(self.schedule_frame, textvariable=self.time_var, width=8).grid(
            row=0, column=3, padx=5
        )
        
        # 初始状态
        self.on_schedule_type_changed()
        
        # 按钮区域
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(20, 10))  # 增加间距
        
        # 添加分隔线
        ttk.Separator(button_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=(0, 10))
        
        # 按钮容器
        buttons_container = ttk.Frame(button_frame)
        buttons_container.pack(fill=tk.X)
        
        # 左侧按钮组（保存和立即执行）
        left_button_frame = ttk.Frame(buttons_container)
        left_button_frame.pack(side=tk.LEFT)
        
        self.save_button = ttk.Button(left_button_frame, text="保存任务", command=self.on_save, width=12)
        self.save_button.pack(side=tk.LEFT, padx=(0, 10))
        
        self.execute_button = ttk.Button(left_button_frame, text="立即执行", command=self.on_execute, width=12)
        self.execute_button.pack(side=tk.LEFT, padx=(0, 10))
        
        # 右侧按钮（取消）
        ttk.Button(buttons_container, text="取消", command=self.on_cancel, width=8).pack(side=tk.RIGHT)
    
    def _load_data(self):
        """加载任务数据"""
        if self.task_data:
            self.name_var.set(self.task_data.get('name', ''))
            self.url_var.set(self.task_data.get('base_url', ''))
            self.path_var.set(self.task_data.get('download_path', ''))
            self.depth_var.set(self.task_data.get('max_depth', 1))
            
            # URL模式
            patterns = self.task_data.get('url_patterns', [])
            if patterns:
                self.pattern_text.insert('1.0', '\n'.join(patterns))
            
            # 计划时间
            scheduled_time = self.task_data.get('scheduled_time')
            if scheduled_time:
                self.schedule_type_var.set("scheduled")
                self.date_var.set(scheduled_time.strftime("%Y-%m-%d"))
                self.time_var.set(scheduled_time.strftime("%H:%M"))
                self.on_schedule_type_changed()
        else:
            # 新建任务时，加载上次使用的下载目录
            last_directory = self.config.get('gui.last_download_directory', '')
            if last_directory and os.path.exists(last_directory):
                self.path_var.set(last_directory)
            else:
                # 如果没有保存的目录或目录不存在，使用默认下载目录
                default_path = self.config.get('download_path', './downloads')
                self.path_var.set(default_path)
    
    def on_schedule_type_changed(self):
        """计划类型改变"""
        if self.schedule_type_var.get() == "scheduled":
            # 计划执行模式
            for widget in self.schedule_frame.winfo_children():
                if isinstance(widget, ttk.Entry):
                    widget.configure(state='normal')
            # 禁用立即执行按钮
            if hasattr(self, 'execute_button'):
                self.execute_button.configure(state='disabled')
        else:
            # 立即执行模式
            for widget in self.schedule_frame.winfo_children():
                if isinstance(widget, ttk.Entry):
                    widget.configure(state='disabled')
            # 启用立即执行按钮
            if hasattr(self, 'execute_button'):
                self.execute_button.configure(state='normal')
    
    def browse_directory(self):
        """浏览目录"""
        # 获取初始目录，优先使用当前输入框中的目录
        initial_dir = self.path_var.get().strip()
        if not initial_dir or not os.path.exists(initial_dir):
            # 如果输入框为空或目录不存在，使用上次保存的目录
            initial_dir = self.config.get('gui.last_download_directory', '')
            if not initial_dir or not os.path.exists(initial_dir):
                # 如果都没有，使用默认下载目录
                initial_dir = self.config.get('download_path', './downloads')
        
        directory = filedialog.askdirectory(
            title="选择下载目录",
            initialdir=initial_dir
        )
        if directory:
            self.path_var.set(directory)
            # 保存到配置文件
            self.config.set('gui.last_download_directory', directory)
            self.config.save()
    
    def on_save(self):
        """保存任务按钮"""
        task_data = self._validate_and_get_task_data()
        if task_data:
            # 设置为计划执行，但不设置具体时间
            task_data['scheduled_time'] = None
            task_data['save_only'] = True  # 标记为只保存
            self.result = task_data
            self.dialog.destroy()
    
    def on_execute(self):
        """立即执行按钮"""
        task_data = self._validate_and_get_task_data()
        if task_data:
            # 设置为立即执行
            task_data['scheduled_time'] = None
            task_data['save_only'] = False  # 标记为立即执行
            self.result = task_data
            self.dialog.destroy()
    
    def _validate_and_get_task_data(self) -> Optional[Dict]:
        """验证输入并获取任务数据"""
        # 验证输入
        if not self.name_var.get().strip():
            messagebox.showerror("错误", "请输入任务名称")
            return None
        
        if not self.url_var.get().strip():
            messagebox.showerror("错误", "请输入目标URL")
            return None
        
        # 验证URL格式
        url = self.url_var.get().strip()
        if not (url.startswith('http://') or url.startswith('https://')):
            messagebox.showerror("错误", "URL必须以http://或https://开头")
            return None
        
        # 解析URL模式
        patterns = []
        pattern_text = self.pattern_text.get('1.0', tk.END).strip()
        if pattern_text:
            patterns = [p.strip() for p in pattern_text.split('\n') if p.strip()]
        
        # 解析计划时间
        scheduled_time = None
        if self.schedule_type_var.get() == "scheduled":
            try:
                date_str = self.date_var.get()
                time_str = self.time_var.get()
                datetime_str = f"{date_str} {time_str}"
                scheduled_time = datetime.strptime(datetime_str, "%Y-%m-%d %H:%M")
                
                # 检查时间是否在未来
                if scheduled_time <= datetime.now():
                    messagebox.showerror("错误", "计划时间必须是未来时间")
                    return None
                    
            except ValueError:
                messagebox.showerror("错误", "日期时间格式错误")
                return None
        
        return {
            'name': self.name_var.get().strip(),
            'base_url': url,
            'download_path': self.path_var.get().strip() or None,
            'max_depth': self.depth_var.get(),
            'url_patterns': patterns,
            'scheduled_time': scheduled_time
        }
    
    def on_cancel(self):
        """取消按钮"""
        self.result = None
        self.dialog.destroy()
    
    def show(self):
        """显示对话框并返回结果"""
        self.dialog.wait_window()
        return self.result