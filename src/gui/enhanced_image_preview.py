#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
增强的图片预览窗口模块
支持网格式多图预览和单图放大查看
"""

import tkinter as tk
from tkinter import ttk, messagebox
import os
from PIL import Image, ImageTk
import logging
from typing import Optional, List, Dict
import threading
import queue
from concurrent.futures import ThreadPoolExecutor
import math
from .theme import center_window, style_button, style_window

class EnhancedImagePreviewWindow:
    """增强的图片预览窗口类，支持网格和单图两种模式"""
    
    def __init__(self, parent, image_paths):
        """
        初始化增强图片预览窗口
        
        Args:
            parent: 父窗口
            image_paths: 图片路径列表
        """
        self.parent = parent
        self.image_paths = [path for path in image_paths if os.path.exists(path)]
        self.current_index = 0
        self.logger = logging.getLogger(__name__)
        
        # 窗口变量
        self.window: Optional[tk.Toplevel] = None
        self.main_frame: Optional[ttk.Frame] = None
        self.content_frame: Optional[ttk.Frame] = None
        self.info_var: Optional[tk.StringVar] = None
        self.mode_var: Optional[tk.StringVar] = None
        
        # 显示模式：'grid' 或 'single'
        self.view_mode = 'grid'
        
        # 网格模式组件
        self.grid_frame: Optional[ttk.Frame] = None
        self.grid_canvas: Optional[tk.Canvas] = None
        self.grid_scrollable_frame: Optional[ttk.Frame] = None
        self.thumbnail_cache: Dict[str, ImageTk.PhotoImage] = {}
        self.grid_columns = 4  # 默认网格列数，将动态调整
        self.thumbnail_size = (180, 180)  # 缩略图尺寸
        self.min_columns = 5  # 最小列数
        self.max_columns = 8  # 最大列数
        
        # 单图模式组件
        self.single_frame: Optional[ttk.Frame] = None
        self.single_canvas: Optional[tk.Canvas] = None
        self.current_image = None
        
        # 单图模式设置
        self.max_display_width = 1200
        self.max_display_height = 900
        self.min_window_width = 1000
        self.min_window_height = 700
        self.window_padding = 150
        
        # 异步加载相关
        self.loading_queue = queue.Queue()
        self.is_loading = False
        self.load_thread = None
    
    def show(self):
        """显示预览窗口"""
        if not self.image_paths:
            messagebox.showinfo("提示", "没有可预览的图片")
            return
        
        self._create_window()
        self._switch_to_grid_mode()
        
        # 显示窗口
        if self.window:
            self.window.transient(self.parent)
            self.window.grab_set()
            self.window.focus_set()
            
            # 开始加载缩略图
            self._start_thumbnail_loading()
            
            self.window.mainloop()
    
    def _create_window(self):
        """创建窗口"""
        self.window = tk.Toplevel(self.parent)
        self.window.title(f"图片预览 - 共 {len(self.image_paths)} 张")
        
        style_window(self.window)
        center_window(self.window, self.parent, width=1200, height=900)
        self.window.minsize(self.min_window_width, self.min_window_height)
        
        # 创建主框架
        self.main_frame = ttk.Frame(self.window, style="App.TFrame")
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 创建工具栏
        self._create_toolbar()
        
        # 创建内容区域
        self.content_frame = ttk.Frame(self.main_frame, style="App.TFrame")
        self.content_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
        
        # 创建状态栏
        self._create_status_bar()
        
        # 绑定键盘事件
        self.window.bind('<Escape>', self._close_window)
        self.window.bind('<F5>', self._refresh_view)
        self.window.bind('<Left>', self._previous_image)
        self.window.bind('<Right>', self._next_image)
        self.window.bind('<Return>', self._toggle_view_mode)
        self.window.focus_set()
        
        # 绑定窗口大小改变事件（用于自适应列数）
        self.window.bind('<Configure>', self._on_window_configure)
        self.window.protocol("WM_DELETE_WINDOW", self.close_window)
        
        # 窗口配置变化的延迟处理
        self.resize_timer = None
        self.last_window_width = None
    
    def _create_toolbar(self):
        """创建工具栏"""
        toolbar = ttk.Frame(self.main_frame, style="Toolbar.TFrame")
        toolbar.pack(fill=tk.X, pady=(0, 10))
        
        # 左侧按钮组
        left_buttons = ttk.Frame(toolbar, style="Toolbar.TFrame")
        left_buttons.pack(side=tk.LEFT)
        
        # 视图模式选择
        self.mode_var = tk.StringVar(value="网格视图")
        mode_combo = ttk.Combobox(left_buttons, textvariable=self.mode_var, 
                                 values=["网格视图", "单图视图"], 
                                 state="readonly", width=10)
        mode_combo.pack(side=tk.LEFT, padx=(0, 10))
        mode_combo.bind('<<ComboboxSelected>>', self._on_mode_change)
        
        # 分隔符
        ttk.Separator(left_buttons, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)
        
        # 导航按钮（单图模式时可用）
        self.nav_frame = ttk.Frame(left_buttons, style="Toolbar.TFrame")
        self.nav_frame.pack(side=tk.LEFT)
        
        self.prev_btn = style_button(ttk.Button(self.nav_frame, text="上一张 (←)",
                                  command=self.previous_image, state=tk.DISABLED), "secondary")
        self.prev_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        self.next_btn = style_button(ttk.Button(self.nav_frame, text="下一张 (→)",
                                  command=self.next_image, state=tk.DISABLED), "secondary")
        self.next_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        # 分隔符
        ttk.Separator(left_buttons, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)
        
        # 操作按钮
        style_button(ttk.Button(left_buttons, text="刷新 (F5)", command=self.refresh_view), "secondary").pack(side=tk.LEFT, padx=(0, 5))
        style_button(ttk.Button(left_buttons, text="打开文件夹", command=self.open_current_folder), "secondary").pack(side=tk.LEFT, padx=(0, 5))
        
        # 右侧按钮组
        right_buttons = ttk.Frame(toolbar, style="Toolbar.TFrame")
        right_buttons.pack(side=tk.RIGHT)
        
        style_button(ttk.Button(right_buttons, text="关闭 (Esc)", command=self.close_window), "ghost").pack(side=tk.RIGHT)
    
    def _create_status_bar(self):
        """创建状态栏"""
        status_frame = ttk.Frame(self.main_frame, style="Status.TFrame", padding=(8, 6))
        status_frame.pack(fill=tk.X, pady=(10, 0))
        
        # 添加分隔线
        ttk.Separator(status_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=(0, 5))
        
        # 信息显示
        info_frame = ttk.Frame(status_frame, style="Status.TFrame")
        info_frame.pack(fill=tk.X)
        
        self.info_var = tk.StringVar(value=f"共 {len(self.image_paths)} 张图片")
        ttk.Label(info_frame, textvariable=self.info_var, style="StatusMuted.TLabel").pack(side=tk.LEFT)
        
        # 加载进度（右对齐）
        self.progress_var = tk.StringVar(value="")
        self.progress_label = ttk.Label(info_frame, textvariable=self.progress_var, style="StatusMuted.TLabel")
        self.progress_label.pack(side=tk.RIGHT)
    
    def _switch_to_grid_mode(self):
        """切换到网格视图模式"""
        self.view_mode = 'grid'
        self._clear_content_frame()
        
        # 禁用导航按钮
        self.prev_btn.config(state=tk.DISABLED)
        self.next_btn.config(state=tk.DISABLED)
        
        # 创建网格视图
        self._create_grid_view()
        
        self.logger.info("切换到网格视图模式")
    
    def _switch_to_single_mode(self, initial_index=0):
        """切换到单图视图模式"""
        self.view_mode = 'single'
        self.current_index = initial_index
        self._clear_content_frame()
        
        # 启用导航按钮
        self.prev_btn.config(state=tk.NORMAL)
        self.next_btn.config(state=tk.NORMAL)
        
        # 创建单图视图
        self._create_single_view()
        self._load_current_image()
        
        self.logger.info(f"切换到单图视图模式，显示第 {initial_index + 1} 张图片")
    
    def _clear_content_frame(self):
        """清空内容框架"""
        if self.content_frame:
            for widget in self.content_frame.winfo_children():
                widget.destroy()
    
    def _create_grid_view(self):
        """创建网格视图"""
        # 创建滚动区域
        canvas = tk.Canvas(self.content_frame, highlightthickness=0, background="#F8FAFC")
        scrollbar = ttk.Scrollbar(self.content_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas, style="Surface.TFrame")
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # 布局
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # 绑定鼠标滚轮
        canvas.bind("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))
        canvas.bind("<Button-4>", lambda e: canvas.yview_scroll(-1, "units"))
        canvas.bind("<Button-5>", lambda e: canvas.yview_scroll(1, "units"))
        
        self.grid_canvas = canvas
        self.grid_scrollable_frame = scrollable_frame
        
        # 创建网格布局占位符
        self._create_grid_placeholders()
    
    def _create_grid_placeholders(self):
        """创建网格布局占位符"""
        if not self.grid_scrollable_frame:
            return
        
        # 根据当前窗口宽度计算列数
        self._update_grid_columns()
        
        rows = math.ceil(len(self.image_paths) / self.grid_columns)
        
        for row in range(rows):
            for col in range(self.grid_columns):
                index = row * self.grid_columns + col
                if index >= len(self.image_paths):
                    break
                
                # 创建图片框架
                img_frame = ttk.Frame(self.grid_scrollable_frame, style="Card.TFrame", padding=6)
                img_frame.grid(row=row, column=col, padx=5, pady=5, sticky="nsew")
                
                # 占位标签
                placeholder = ttk.Label(img_frame, text="加载中...", 
                                      width=20, anchor="center")
                placeholder.pack(expand=True, fill="both")
                
                # 文件名标签
                filename = os.path.basename(self.image_paths[index])
                name_label = ttk.Label(img_frame, text=filename[:20] + "..." if len(filename) > 20 else filename,
                                     anchor="center", font=("TkDefaultFont", 8))
                name_label.pack(pady=(5, 0))
                
        # 配置所有列的权重
        for col in range(self.grid_columns):
            self.grid_scrollable_frame.columnconfigure(col, weight=1)
    
    def _create_single_view(self):
        """创建单图视图"""
        # 创建图片显示区域
        image_frame = ttk.LabelFrame(self.content_frame, text="图片预览", padding=12, style="App.TLabelframe")
        image_frame.pack(fill=tk.BOTH, expand=True)
        
        # 创建画布
        self.single_canvas = tk.Canvas(
            image_frame, 
            bg='#F8FAFC',
            highlightthickness=1,
            highlightbackground='#D8E0EA'
        )
        
        # 添加滚动条
        v_scrollbar = ttk.Scrollbar(image_frame, orient=tk.VERTICAL, command=self.single_canvas.yview)
        h_scrollbar = ttk.Scrollbar(image_frame, orient=tk.HORIZONTAL, command=self.single_canvas.xview)
        
        self.single_canvas.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        # 布局
        self.single_canvas.grid(row=0, column=0, sticky="nsew")
        v_scrollbar.grid(row=0, column=1, sticky="ns")
        h_scrollbar.grid(row=1, column=0, sticky="ew")
        
        # 配置权重
        image_frame.grid_rowconfigure(0, weight=1)
        image_frame.grid_columnconfigure(0, weight=1)
        
        # 绑定鼠标滚轮
        self.single_canvas.bind("<MouseWheel>", self._on_mousewheel)
        self.single_canvas.bind("<Button-4>", self._on_mousewheel)
        self.single_canvas.bind("<Button-5>", self._on_mousewheel)
    
    def _start_thumbnail_loading(self):
        """开始异步加载缩略图"""
        if self.is_loading or self.view_mode != 'grid':
            return
        
        self.is_loading = True
        self.load_thread = threading.Thread(target=self._load_thumbnails_async, daemon=True)
        self.load_thread.start()
    
    def _load_thumbnails_async(self):
        """异步加载缩略图"""
        total_images = len(self.image_paths)
        
        try:
            with ThreadPoolExecutor(max_workers=3) as executor:
                # 提交所有加载任务
                future_to_index = {
                    executor.submit(self._load_single_thumbnail, i, path): i 
                    for i, path in enumerate(self.image_paths)
                }
                
                # 处理完成的任务
                completed = 0
                for future in future_to_index:
                    try:
                        index, thumbnail = future.result(timeout=5)
                        if thumbnail:
                            # 通过队列安全地更新UI
                            self.loading_queue.put(('thumbnail', index, thumbnail))
                        completed += 1
                        
                        # 更新进度
                        progress = f"加载缩略图: {completed}/{total_images}"
                        self.loading_queue.put(('progress', progress))
                        
                    except Exception as e:
                        self.logger.warning(f"加载缩略图失败: {e}")
                        completed += 1
                
                # 加载完成
                self.loading_queue.put(('progress', "加载完成"))
                
        except Exception as e:
            self.logger.error(f"异步加载缩略图失败: {e}")
        finally:
            self.is_loading = False
        
        # 启动UI更新定时器
        if self.window:
            self.window.after(100, self._process_loading_queue)
    
    def _load_single_thumbnail(self, index, image_path):
        """加载单个缩略图"""
        try:
            with Image.open(image_path) as img:
                # 创建缩略图
                img.thumbnail(self.thumbnail_size, Image.Resampling.LANCZOS)
                
                # 创建一个固定尺寸的背景
                background = Image.new('RGB', self.thumbnail_size, (240, 240, 240))
                
                # 计算居中位置
                x = (self.thumbnail_size[0] - img.width) // 2
                y = (self.thumbnail_size[1] - img.height) // 2
                
                # 粘贴缩略图到背景中央
                if img.mode == 'RGBA':
                    background.paste(img, (x, y), img)
                else:
                    background.paste(img, (x, y))
                
                # 转换为PhotoImage
                thumbnail = ImageTk.PhotoImage(background)
                return index, thumbnail
                
        except Exception as e:
            self.logger.warning(f"创建缩略图失败 {image_path}: {e}")
            return index, None
    
    def _process_loading_queue(self):
        """处理加载队列"""
        try:
            while True:
                item_type, *args = self.loading_queue.get_nowait()
                
                if item_type == 'thumbnail':
                    index, thumbnail = args
                    self._update_grid_thumbnail(index, thumbnail)
                elif item_type == 'progress':
                    progress_text = args[0]
                    self.progress_var.set(progress_text)
                    
        except queue.Empty:
            pass
        
        # 如果还在加载，继续检查队列
        if self.is_loading and self.window:
            self.window.after(100, self._process_loading_queue)
        elif self.window:
            # 加载完成，清空进度显示
            self.window.after(2000, lambda: self.progress_var.set(""))
    
    def _update_grid_thumbnail(self, index, thumbnail):
        """更新网格中的缩略图"""
        if not self.grid_scrollable_frame or self.view_mode != 'grid':
            return
        
        row = index // self.grid_columns
        col = index % self.grid_columns
        
        try:
            # 查找对应的框架
            for widget in self.grid_scrollable_frame.grid_slaves(row=row, column=col):
                if isinstance(widget, ttk.Frame):
                    # 清除占位符
                    for child in widget.winfo_children():
                        if isinstance(child, ttk.Label) and child.cget('text') == "加载中...":
                            child.destroy()
                            break
                    
                    # 创建图片标签
                    img_label = ttk.Label(widget, image=thumbnail, cursor="hand2")
                    img_label.pack(expand=True, fill="both", pady=(0, 5))
                    
                    # 绑定点击事件
                    img_label.bind("<Button-1>", lambda e, idx=index: self._on_thumbnail_click(idx))
                    
                    # 缓存缩略图
                    self.thumbnail_cache[str(index)] = thumbnail
                    
                    break
                    
        except Exception as e:
            self.logger.warning(f"更新网格缩略图失败 {index}: {e}")
    
    def _on_thumbnail_click(self, index):
        """缩略图点击事件"""
        if self.mode_var:
            self.mode_var.set("单图视图")
        self._switch_to_single_mode(index)
    
    def _load_current_image(self):
        """加载当前图片（单图模式）"""
        if not self.image_paths or self.current_index >= len(self.image_paths) or not self.single_canvas:
            return
        
        image_path = self.image_paths[self.current_index]
        
        try:
            # 加载图片
            pil_image = Image.open(image_path)
            
            # 获取原始尺寸
            original_width, original_height = pil_image.size
            
            # 计算显示尺寸
            display_width, display_height = self._calculate_display_size(
                original_width, original_height
            )
            
            # 调整图片尺寸
            if (display_width, display_height) != (original_width, original_height):
                pil_image = pil_image.resize((display_width, display_height), Image.Resampling.LANCZOS)
            
            # 转换为 PhotoImage
            self.current_image = ImageTk.PhotoImage(pil_image)
            
            # 清空画布
            self.single_canvas.delete("all")
            
            # 设置画布滚动区域
            self.single_canvas.configure(scrollregion=(0, 0, display_width, display_height))
            
            # 设置画布大小以匹配图片
            canvas_width = min(display_width, self.max_display_width)
            canvas_height = min(display_height, self.max_display_height)
            self.single_canvas.configure(width=canvas_width, height=canvas_height)
            
            # 调整窗口大小以适应图片
            window_width = min(display_width + self.window_padding, self.max_display_width + self.window_padding)
            window_height = min(display_height + self.window_padding, self.max_display_height + self.window_padding)
            
            # 确保窗口不小于最小尺寸
            window_width = max(window_width, self.min_window_width)
            window_height = max(window_height, self.min_window_height)
            
            # 获取屏幕尺寸
            screen_width = self.window.winfo_screenwidth()
            screen_height = self.window.winfo_screenheight()
            
            # 确保窗口不超过屏幕尺寸的90%
            window_width = min(window_width, int(screen_width * 0.9))
            window_height = min(window_height, int(screen_height * 0.9))
            
            # 设置窗口尺寸
            self.window.geometry(f"{window_width}x{window_height}")
            
            # 在画布中央显示图片
            self.single_canvas.create_image(
                display_width // 2, 
                display_height // 2, 
                anchor=tk.CENTER, 
                image=self.current_image
            )
            
            # 更新状态信息
            filename = os.path.basename(image_path)
            file_size = os.path.getsize(image_path)
            file_size_str = self._format_file_size(file_size)
            
            if self.info_var:
                self.info_var.set(
                    f"文件: {filename} | 尺寸: {original_width}×{original_height} | "
                    f"大小: {file_size_str} | {self.current_index + 1}/{len(self.image_paths)}"
                )
            
            # 更新窗口标题
            if self.window:
                self.window.title(f"图片预览 - {filename} ({self.current_index + 1}/{len(self.image_paths)})")
            
            self.logger.info(f"加载图片: {filename}")
            
        except Exception as e:
            self.logger.error(f"加载图片失败: {image_path} - {e}")
            messagebox.showerror("错误", f"加载图片失败: {os.path.basename(image_path)}")
    
    def _calculate_display_size(self, width, height):
        """计算显示尺寸"""
        if width <= self.max_display_width and height <= self.max_display_height:
            return width, height
        
        width_ratio = self.max_display_width / width
        height_ratio = self.max_display_height / height
        scale_ratio = min(width_ratio, height_ratio)
        
        return int(width * scale_ratio), int(height * scale_ratio)
    
    def _format_file_size(self, size_bytes):
        """格式化文件大小"""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"
    
    # 事件处理方法
    def _on_mode_change(self, event=None):
        """视图模式改变事件"""
        if not self.mode_var:
            return
        
        mode = self.mode_var.get()
        if mode == "网格视图" and self.view_mode != 'grid':
            self._switch_to_grid_mode()
            if not self.is_loading:
                self._start_thumbnail_loading()
        elif mode == "单图视图" and self.view_mode != 'single':
            self._switch_to_single_mode(self.current_index)
    
    def _toggle_view_mode(self, event=None):
        """切换视图模式（回车键）"""
        if not self.mode_var:
            return
        
        current_mode = self.mode_var.get()
        if current_mode == "网格视图":
            self.mode_var.set("单图视图")
        else:
            self.mode_var.set("网格视图")
        self._on_mode_change()
    
    def _previous_image(self, event=None):
        """上一张图片"""
        if self.view_mode == 'single':
            self.previous_image()
    
    def _next_image(self, event=None):
        """下一张图片"""
        if self.view_mode == 'single':
            self.next_image()
    
    def _close_window(self, event=None):
        """关闭窗口"""
        self.close_window()
    
    def _refresh_view(self, event=None):
        """刷新视图"""
        self.refresh_view()
    
    def _on_mousewheel(self, event):
        """鼠标滚轮事件"""
        if not self.single_canvas:
            return
        
        if event.delta:
            delta = event.delta / 120
        else:
            if event.num == 4:
                delta = 1
            elif event.num == 5:
                delta = -1
            else:
                return
        
        self.single_canvas.yview_scroll(int(-delta), "units")
    
    def _on_window_configure(self, event=None):
        """窗口配置改变事件处理（用于自适应列数）"""
        if not self.window or not event or event.widget != self.window:
            return
        
        # 只在网格模式下处理
        if self.view_mode != 'grid':
            return
        
        current_width = self.window.winfo_width()
        
        # 避免频繁更新，只在宽度有明显变化时才处理
        if self.last_window_width is None:
            self.last_window_width = current_width
            return
        
        if abs(current_width - self.last_window_width) < 50:  # 50像素的容差
            return
        
        self.last_window_width = current_width
        
        # 取消之前的定时器
        if self.resize_timer:
            self.window.after_cancel(self.resize_timer)
        
        # 延迟执行重新布局，避免频繁更新
        self.resize_timer = self.window.after(300, self._handle_window_resize)
    
    def _handle_window_resize(self):
        """处理窗口大小改变"""
        if self.view_mode == 'grid' and self.grid_scrollable_frame:
            old_columns = self.grid_columns
            self._update_grid_columns()
            
            # 只有当列数真正改变时才重新布局
            if old_columns != self.grid_columns:
                self.logger.info(f"窗口宽度改变，网格列数从 {old_columns} 调整为 {self.grid_columns}")
                self._recreate_grid_layout()
    
    def _calculate_grid_columns(self):
        """根据窗口宽度动态计算列数"""
        if not self.window:
            return self.grid_columns
        
        try:
            # 获取内容区域的有效宽度
            window_width = self.window.winfo_width()
            
            # 减去边距、滚动条等占用的空间
            available_width = window_width - 80  # 预留80像素的边距和滚动条空间
            
            # 每个缩略图的实际宽度（包括边距）
            thumbnail_width = self.thumbnail_size[0] + 20  # 缩略图宽度 + 边距
            
            # 计算可容纳的列数
            calculated_columns = max(1, available_width // thumbnail_width)
            
            # 限制在合理范围内
            columns = max(self.min_columns, min(self.max_columns, calculated_columns))
            
            return columns
            
        except Exception as e:
            self.logger.warning(f"计算网格列数失败: {e}")
            return self.grid_columns  # 返回当前值作为fallback
    
    def _update_grid_columns(self):
        """更新网格列数"""
        new_columns = self._calculate_grid_columns()
        if new_columns != self.grid_columns:
            self.grid_columns = new_columns
            return True
        return False
    
    def _recreate_grid_layout(self):
        """重新创建网格布局"""
        if not self.grid_scrollable_frame or self.view_mode != 'grid':
            return
        
        try:
            # 保存当前缩略图缓存
            current_thumbnails = {}
            
            # 收集现有的缩略图
            for widget in self.grid_scrollable_frame.winfo_children():
                if isinstance(widget, ttk.Frame):
                    # 获取网格位置
                    grid_info = widget.grid_info()
                    if grid_info:
                        old_row = grid_info.get('row', 0)
                        old_col = grid_info.get('column', 0)
                        old_index = old_row * (self.grid_columns if hasattr(self, '_old_columns') else 4) + old_col
                        
                        # 查找图片标签
                        for child in widget.winfo_children():
                            if isinstance(child, ttk.Label):
                                try:
                                    # 检查标签是否有图片
                                    if hasattr(child, '_PhotoImage__photo') and child['image']:
                                        current_thumbnails[old_index] = child['image']
                                        break
                                except:
                                    # 如果无法获取图片，就跳过
                                    continue
            
            # 清空当前网格
            for widget in self.grid_scrollable_frame.winfo_children():
                widget.destroy()
            
            # 重新创建网格布局
            rows = math.ceil(len(self.image_paths) / self.grid_columns)
            
            for row in range(rows):
                for col in range(self.grid_columns):
                    index = row * self.grid_columns + col
                    if index >= len(self.image_paths):
                        break
                    
                    # 创建图片框架
                    img_frame = ttk.Frame(self.grid_scrollable_frame, style="Card.TFrame", padding=6)
                    img_frame.grid(row=row, column=col, padx=5, pady=5, sticky="nsew")
                    
                    # 如果有缓存的缩略图，直接使用
                    if index in current_thumbnails:
                        thumbnail = current_thumbnails[index]
                        img_label = ttk.Label(img_frame, image=thumbnail, cursor="hand2")
                        img_label.pack(expand=True, fill="both", pady=(0, 5))
                        img_label.bind("<Button-1>", lambda e, idx=index: self._on_thumbnail_click(idx))
                        
                        # 更新缓存
                        self.thumbnail_cache[str(index)] = thumbnail
                    else:
                        # 创建占位标签
                        placeholder = ttk.Label(img_frame, text="加载中...", 
                                              width=20, anchor="center")
                        placeholder.pack(expand=True, fill="both")
                    
                    # 文件名标签
                    filename = os.path.basename(self.image_paths[index])
                    name_label = ttk.Label(img_frame, text=filename[:20] + "..." if len(filename) > 20 else filename,
                                         anchor="center", font=("TkDefaultFont", 8))
                    name_label.pack(pady=(5, 0))
            
            # 配置所有列的权重
            for col in range(self.grid_columns):
                self.grid_scrollable_frame.columnconfigure(col, weight=1)
            
            # 更新滚动区域
            if self.grid_canvas:
                self.grid_canvas.configure(scrollregion=self.grid_canvas.bbox("all"))
            
            self.logger.info(f"重新创建网格布局: {self.grid_columns} 列")
            
        except Exception as e:
            self.logger.error(f"重新创建网格布局失败: {e}")
            # 如果失败，尝试重新开始
            self._create_grid_placeholders()
    
    # 公共方法
    def previous_image(self):
        """显示上一张图片"""
        if self.view_mode == 'single' and self.image_paths and self.current_index > 0:
            self.current_index -= 1
            self._load_current_image()
    
    def next_image(self):
        """显示下一张图片"""
        if self.view_mode == 'single' and self.image_paths and self.current_index < len(self.image_paths) - 1:
            self.current_index += 1
            self._load_current_image()
    
    def refresh_view(self):
        """刷新视图"""
        if self.view_mode == 'grid':
            self.thumbnail_cache.clear()
            self._switch_to_grid_mode()
            self._start_thumbnail_loading()
        else:
            self._load_current_image()
    
    def open_current_folder(self):
        """打开当前图片所在文件夹"""
        if not self.image_paths:
            return
        
        if self.view_mode == 'single' and self.current_index < len(self.image_paths):
            image_path = self.image_paths[self.current_index]
        else:
            image_path = self.image_paths[0]
        
        folder_path = os.path.dirname(image_path)
        
        try:
            import platform
            import subprocess
            
            system = platform.system()
            if system == "Windows":
                subprocess.Popen(['explorer', '/select,', image_path])
            elif system == "Darwin":  # macOS
                subprocess.Popen(['open', '-R', image_path])
            elif system == "Linux":
                subprocess.Popen(['xdg-open', folder_path])
            else:
                messagebox.showinfo("提示", f"图片位置: {folder_path}")
                
        except Exception as e:
            self.logger.error(f"打开文件夹失败: {e}")
            messagebox.showerror("错误", f"打开文件夹失败: {e}")
    
    def close_window(self):
        """关闭窗口"""
        # 停止异步加载
        self.is_loading = False
        
        if self.window:
            self.window.destroy()


# 保持向后兼容的别名
ImagePreviewWindow = EnhancedImagePreviewWindow
