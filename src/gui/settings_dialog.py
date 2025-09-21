#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
设置对话框模块
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from typing import Dict

class SettingsDialog:
    """设置对话框"""
    
    def __init__(self, parent, config):
        """
        初始化设置对话框
        
        Args:
            parent: 父窗口
            config: 配置对象
        """
        self.parent = parent
        self.config = config
        self.result = False
        
        # 创建对话框窗口
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("设置")
        self.dialog.geometry("700x600")  # 调整尺寸
        self.dialog.resizable(True, True)  # 允许调整大小
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # 居中显示
        self.dialog.geometry("+%d+%d" % (
            parent.winfo_rootx() + 100,
            parent.winfo_rooty() + 50
        ))
        
        self._create_widgets()
        self._load_settings()
    
    def _create_widgets(self):
        """创建界面控件"""
        # 主容器
        main_container = ttk.Frame(self.dialog)
        main_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 创建滚动区域
        canvas = tk.Canvas(main_container)
        scrollbar = ttk.Scrollbar(main_container, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # 鼠标滚轮支持
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        
        # 保存事件处理函数引用以便后续解绑
        self._mousewheel_handler = _on_mousewheel
        
        # 布局滚动区域
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # 在滚动区域中创建内容
        content_frame = scrollable_frame
        
        # 下载设置
        download_frame = ttk.LabelFrame(content_frame, text="下载设置", padding=10)
        download_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 默认下载路径
        ttk.Label(download_frame, text="默认下载路径:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.download_path_var = tk.StringVar()
        ttk.Entry(download_frame, textvariable=self.download_path_var, width=40).grid(
            row=0, column=1, sticky=tk.EW, padx=(10, 0), pady=5
        )
        ttk.Button(download_frame, text="浏览", command=self.browse_download_path).grid(
            row=0, column=2, padx=(5, 0), pady=5
        )
        
        # 最大线程数
        ttk.Label(download_frame, text="最大下载线程数:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.max_threads_var = tk.IntVar()
        ttk.Spinbox(download_frame, from_=1, to=10, textvariable=self.max_threads_var, width=10).grid(
            row=1, column=1, sticky=tk.W, padx=(10, 0), pady=5
        )
        
        # 超时时间
        ttk.Label(download_frame, text="连接超时(秒):").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.timeout_var = tk.IntVar()
        ttk.Spinbox(download_frame, from_=5, to=120, textvariable=self.timeout_var, width=10).grid(
            row=2, column=1, sticky=tk.W, padx=(10, 0), pady=5
        )
        
        # 重试次数
        ttk.Label(download_frame, text="重试次数:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.retry_times_var = tk.IntVar()
        ttk.Spinbox(download_frame, from_=0, to=10, textvariable=self.retry_times_var, width=10).grid(
            row=3, column=1, sticky=tk.W, padx=(10, 0), pady=5
        )
        
        download_frame.columnconfigure(1, weight=1)
        
        # 图片过滤设置
        filter_frame = ttk.LabelFrame(content_frame, text="图片过滤", padding=10)
        filter_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 允许的图片类型
        ttk.Label(filter_frame, text="允许的图片类型:").grid(row=0, column=0, sticky=tk.NW, pady=5)
        types_frame = ttk.Frame(filter_frame)
        types_frame.grid(row=0, column=1, sticky=tk.EW, padx=(10, 0), pady=5)
        
        self.image_types_vars = {}
        common_types = ['jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp']
        for i, img_type in enumerate(common_types):
            var = tk.BooleanVar()
            self.image_types_vars[img_type] = var
            ttk.Checkbutton(types_frame, text=img_type.upper(), variable=var).grid(
                row=i//3, column=i%3, sticky=tk.W, padx=5, pady=2
            )
        
        # 最小文件大小
        ttk.Label(filter_frame, text="最小文件大小(KB):").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.min_size_var = tk.IntVar()
        ttk.Spinbox(filter_frame, from_=0, to=51200, textvariable=self.min_size_var, width=10).grid(
            row=1, column=1, sticky=tk.W, padx=(10, 0), pady=5
        )
        
        # 最大文件大小
        ttk.Label(filter_frame, text="最大文件大小(MB):").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.max_size_var = tk.IntVar()
        ttk.Spinbox(filter_frame, from_=1, to=100, textvariable=self.max_size_var, width=10).grid(
            row=2, column=1, sticky=tk.W, padx=(10, 0), pady=5
        )
        
        # 最小分辨率
        ttk.Label(filter_frame, text="最小宽度(像素):").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.min_width_var = tk.IntVar()
        ttk.Spinbox(filter_frame, from_=100, to=4000, textvariable=self.min_width_var, width=10).grid(
            row=3, column=1, sticky=tk.W, padx=(10, 0), pady=5
        )
        
        ttk.Label(filter_frame, text="最小高度(像素):").grid(row=4, column=0, sticky=tk.W, pady=5)
        self.min_height_var = tk.IntVar()
        ttk.Spinbox(filter_frame, from_=100, to=4000, textvariable=self.min_height_var, width=10).grid(
            row=4, column=1, sticky=tk.W, padx=(10, 0), pady=5
        )
        
        filter_frame.columnconfigure(1, weight=1)
        
        # 预过滤性能设置
        performance_frame = ttk.LabelFrame(content_frame, text="预过滤性能设置", padding=10)
        performance_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 启用文件大小过滤
        self.enable_size_filter_var = tk.BooleanVar()
        ttk.Checkbutton(
            performance_frame, 
            text="启用文件大小过滤", 
            variable=self.enable_size_filter_var
        ).grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=2)
        
        # 启用分辨率过滤
        self.enable_resolution_filter_var = tk.BooleanVar()
        ttk.Checkbutton(
            performance_frame, 
            text="启用分辨率过滤 (会降低速度)", 
            variable=self.enable_resolution_filter_var
        ).grid(row=1, column=0, columnspan=2, sticky=tk.W, pady=2)
        
        # 分辨率检查模式
        ttk.Label(performance_frame, text="分辨率检查模式:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.resolution_mode_var = tk.StringVar()
        mode_combo = ttk.Combobox(
            performance_frame, 
            textvariable=self.resolution_mode_var,
            values=[
                "fast - 跳过分辨率检查(最快)",
                "smart - 智能检查(推荐)", 
                "always - 总是检查(最严格)"
            ],
            state="readonly",
            width=35
        )
        mode_combo.grid(row=2, column=1, sticky=tk.W, padx=(10, 0), pady=5)
        
        # 并行过滤
        self.parallel_filter_var = tk.BooleanVar()
        ttk.Checkbutton(
            performance_frame, 
            text="启用并行过滤 (提高速度)", 
            variable=self.parallel_filter_var
        ).grid(row=3, column=0, columnspan=2, sticky=tk.W, pady=2)
        
        # 过滤超时时间
        ttk.Label(performance_frame, text="单个图片超时(秒):").grid(row=4, column=0, sticky=tk.W, pady=5)
        self.filter_timeout_var = tk.IntVar()
        ttk.Spinbox(
            performance_frame, 
            from_=1, 
            to=30, 
            textvariable=self.filter_timeout_var, 
            width=10
        ).grid(row=4, column=1, sticky=tk.W, padx=(10, 0), pady=5)
        
        # 性能提示
        tips_frame = ttk.Frame(performance_frame)
        tips_frame.grid(row=5, column=0, columnspan=2, sticky=tk.EW, pady=(10, 0))
        
        tips_text = (
            "性能提示:\n"
            "• 只用文件大小过滤速度最快\n"
            "• 智能模式提供最佳平衡\n"
            "• 并行过滤可提速3-4倍"
        )
        tips_label = ttk.Label(
            tips_frame, 
            text=tips_text, 
            font=('Arial', 8), 
            foreground='gray',
            justify=tk.LEFT
        )
        tips_label.pack(side=tk.LEFT, fill=tk.X)
        
        performance_frame.columnconfigure(1, weight=1)
        
        # 按钮区域（在主容器中，不在滚动区域内）
        button_frame = ttk.Frame(self.dialog)
        button_frame.pack(fill=tk.X, side=tk.BOTTOM, padx=10, pady=(5, 10))
        
        # 按钮容器
        buttons_container = ttk.Frame(button_frame)
        buttons_container.pack(fill=tk.X)
        
        # 右侧按钮组（确定、取消）
        right_buttons = ttk.Frame(buttons_container)
        right_buttons.pack(side=tk.RIGHT)
        
        ttk.Button(right_buttons, text="确定", command=self.on_ok, width=8).pack(side=tk.LEFT, padx=(5, 0))
        ttk.Button(right_buttons, text="取消", command=self.on_cancel, width=8).pack(side=tk.LEFT, padx=(5, 0))
        
        # 左侧按钮（恢复默认）
        ttk.Button(buttons_container, text="恢复默认", command=self.on_reset_defaults, width=12).pack(side=tk.LEFT)
    
    def _load_settings(self):
        """加载当前设置"""
        self.download_path_var.set(self.config.get('download_path', './downloads'))
        self.max_threads_var.set(self.config.get('max_threads', 5))
        self.timeout_var.set(self.config.get('timeout', 30))
        self.retry_times_var.set(self.config.get('retry_times', 3))
        
        # 图片类型
        allowed_types = self.config.get('image_filters.types', ['jpg', 'jpeg', 'png', 'gif'])
        for img_type, var in self.image_types_vars.items():
            var.set(img_type in allowed_types)
        
        # 图片过滤设置
        self.min_size_var.set(self.config.get('image_filters.min_size', 51200) // 1024)
        self.max_size_var.set(self.config.get('image_filters.max_size', 10485760) // 1048576)  # 转换为MB
        self.min_width_var.set(self.config.get('image_filters.min_width', 800))
        self.min_height_var.set(self.config.get('image_filters.min_height', 600))
        
        # 预过滤性能设置
        self.enable_size_filter_var.set(self.config.get('image_filters.enable_size_filter', True))
        self.enable_resolution_filter_var.set(self.config.get('image_filters.enable_resolution_filter', True))
        
        # 分辨率检查模式
        mode = self.config.get('image_filters.resolution_check_mode', 'smart')
        mode_mapping = {
            'fast': "fast - 跳过分辨率检查(最快)",
            'smart': "smart - 智能检查(推荐)",
            'always': "always - 总是检查(最严格)"
        }
        self.resolution_mode_var.set(mode_mapping.get(mode, mode_mapping['smart']))
        
        self.parallel_filter_var.set(self.config.get('image_filters.parallel_filter', True))
        self.filter_timeout_var.set(self.config.get('image_filters.filter_timeout', 3))
    
    def browse_download_path(self):
        """浏览下载路径"""
        directory = filedialog.askdirectory(
            title="选择默认下载目录",
            initialdir=self.download_path_var.get()
        )
        if directory:
            self.download_path_var.set(directory)
    
    def on_ok(self):
        """确定按钮"""
        try:
            # 保存设置
            self.config.set('download_path', self.download_path_var.get())
            self.config.set('max_threads', self.max_threads_var.get())
            self.config.set('timeout', self.timeout_var.get())
            self.config.set('retry_times', self.retry_times_var.get())
            
            # 保存图片类型设置
            selected_types = []
            for img_type, var in self.image_types_vars.items():
                if var.get():
                    selected_types.append(img_type)
            
            self.config.set('image_filters.types', selected_types)
            self.config.set('image_filters.min_size', self.min_size_var.get() * 1024)
            self.config.set('image_filters.max_size', self.max_size_var.get() * 1048576)  # 转换为字节
            self.config.set('image_filters.min_width', self.min_width_var.get())
            self.config.set('image_filters.min_height', self.min_height_var.get())
            
            # 保存预过滤性能设置
            self.config.set('image_filters.enable_size_filter', self.enable_size_filter_var.get())
            self.config.set('image_filters.enable_resolution_filter', self.enable_resolution_filter_var.get())
            
            # 分辨率检查模式
            mode_text = self.resolution_mode_var.get()
            if 'fast' in mode_text:
                mode = 'fast'
            elif 'smart' in mode_text:
                mode = 'smart'
            else:
                mode = 'always'
            self.config.set('image_filters.resolution_check_mode', mode)
            
            self.config.set('image_filters.parallel_filter', self.parallel_filter_var.get())
            self.config.set('image_filters.filter_timeout', self.filter_timeout_var.get())
            
            # 保存配置文件
            if self.config.save():
                self.result = True
                messagebox.showinfo("成功", "设置已保存\n\n注意:预过滤设置将在下次新建任务时生效")
                self.dialog.destroy()
            else:
                messagebox.showerror("错误", "保存设置失败，请检查文件权限")
                
        except Exception as e:
            messagebox.showerror("错误", f"保存设置时出错: {e}")
    
    def on_cancel(self):
        """取消按钮"""
        self.result = False
        self.dialog.destroy()
    
    def on_reset_defaults(self):
        """恢复默认设置按钮"""
        from tkinter import messagebox
        
        # 确认对话框
        if messagebox.askyesno("确认恢复", "是否要恢复所有设置为默认值？\n\n此操作不可撤销。"):
            try:
                # 加载默认配置
                from ..core.config import Config
                default_config = Config()._load_default_config()
                
                # 设置为默认值
                self.download_path_var.set(default_config.get('download_path', './downloads'))
                self.max_threads_var.set(default_config.get('max_threads', 5))
                self.timeout_var.set(default_config.get('timeout', 30))
                self.retry_times_var.set(default_config.get('retry_times', 3))
                
                # 图片类型默认值
                default_types = default_config.get('image_filters', {}).get('types', ['jpg', 'jpeg', 'png', 'gif'])
                for img_type, var in self.image_types_vars.items():
                    var.set(img_type in default_types)
                
                # 图片过滤默认值
                image_filters = default_config.get('image_filters', {})
                self.min_size_var.set(image_filters.get('min_size', 51200) // 1024)
                self.max_size_var.set(image_filters.get('max_size', 10485760) // 1048576)
                self.min_width_var.set(image_filters.get('min_width', 800))
                self.min_height_var.set(image_filters.get('min_height', 600))
                
                # 预过滤性能默认值
                self.enable_size_filter_var.set(image_filters.get('enable_size_filter', True))
                self.enable_resolution_filter_var.set(image_filters.get('enable_resolution_filter', True))
                
                # 分辨率检查模式默认值
                mode = image_filters.get('resolution_check_mode', 'smart')
                mode_mapping = {
                    'fast': "fast - 跳过分辨率检查(最快)",
                    'smart': "smart - 智能检查(推荐)",
                    'always': "always - 总是检查(最严格)"
                }
                self.resolution_mode_var.set(mode_mapping.get(mode, mode_mapping['smart']))
                
                self.parallel_filter_var.set(image_filters.get('parallel_filter', True))
                self.filter_timeout_var.set(image_filters.get('filter_timeout', 3))
                
                messagebox.showinfo("成功", "所有设置已恢复为默认值\n\n请点击“确定”保存设置")
                
            except Exception as e:
                messagebox.showerror("错误", f"恢复默认设置失败: {e}")
    
    def show(self):
        """显示对话框并返回结果"""
        # 绑定对话框销毁事件来清理鼠标滚轮事件
        self.dialog.protocol("WM_DELETE_WINDOW", self._on_close)
        self.dialog.wait_window()
        return self.result
    
    def _on_close(self):
        """对话框关闭时的清理操作"""
        # 解绑鼠标滚轮事件
        if hasattr(self, '_mousewheel_handler'):
            try:
                self.dialog.unbind_all("<MouseWheel>")
            except:
                pass
        self.dialog.destroy()
