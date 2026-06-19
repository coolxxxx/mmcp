#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
图片预览窗口模块
支持网格式多图预览和单图放大查看
"""

import tkinter as tk
from tkinter import ttk, messagebox
import os
from PIL import Image, ImageTk
import logging
from typing import Optional, Union
import queue
from typing import List, Dict, Any  # 向后兼容
from .theme import center_window, style_button, style_window

class ImagePreviewWindow:
    """增强的图片预览窗口类，支持网格和单图两种模式"""
    
    def __init__(self, parent: tk.Tk, image_paths: List[str]):
        """
        初始化图片预览窗口
        
        Args:
            parent: 父窗口
            image_paths: 图片路径列表
        """
        self.parent: tk.Tk = parent
        self.image_paths: List[str] = [path for path in image_paths if os.path.exists(path)]
        self.current_index: int = 0
        self.logger: logging.Logger = logging.getLogger(__name__)
        
        # 初始化所有实例变量
        self.canvas: Optional[tk.Canvas] = None
        self.progress_var: Optional[tk.StringVar] = None
        
        # 窗口变量
        self.window: Optional[tk.Toplevel] = None
        self.main_frame: Optional[ttk.Frame] = None
        self.current_image = None
        self.info_var: Optional[tk.StringVar] = None
        self.scrollable_frame: Optional[ttk.Frame] = None
        self.progress_var: Optional[tk.StringVar] = None
        
        # 显示模式：'grid' 或 'single'
        self.view_mode = 'grid'
        
        # 网格模式组件
        self.grid_frame: Optional[ttk.Frame] = None
        self.grid_canvas: Optional[tk.Canvas] = None
        self.grid_scrollable_frame: Optional[ttk.Frame] = None
        self.thumbnail_cache: Dict[str, ImageTk.PhotoImage] = {}  # 缩略图缓存
        self.grid_columns = 5  # 网格列数增加到5
        self.thumbnail_size = (200, 200)  # 缩略图尺寸增大到200x200
        self.padding = 10  # 图片间距
        
        # 单图模式组件
        self.single_frame: Optional[ttk.Frame] = None
        self.single_canvas: Optional[tk.Canvas] = None
        
        # 单图模式设置
        self.max_display_width = 1200
        self.max_display_height = 900
        self.min_window_width = 800    # 增加最小窗口宽度以适应网格
        self.min_window_height = 600   # 增加最小窗口高度
        self.window_padding = 150
        
        # 异步加载相关
        self.loading_queue = queue.Queue()
        self.is_loading = False
    
    def show(self):
        """显示预览窗口"""
        if not self.image_paths:
            messagebox.showinfo("提示", "没有可预览的图片")
            return
        
        self._create_window()
        self._load_current_image()
        
        # 显示窗口
        if self.window:
            self.window.transient(self.parent)
            self.window.grab_set()
            self.window.focus_set()
            self.window.mainloop()
    
    def _create_window(self):
        """创建窗口"""
        self.window = tk.Toplevel(self.parent)
        self.window.title(f"图片预览 - 共 {len(self.image_paths)} 张")
        
        style_window(self.window)
        center_window(self.window, self.parent, width=900, height=700)
        
        # 设置最小窗口大小
        self.window.minsize(self.min_window_width, self.min_window_height)
        
        # 创建主框架
        main_frame = ttk.Frame(self.window, style="App.TFrame")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 工具栏
        self._create_toolbar(main_frame)
        
        # 图片显示区域
        self._create_image_area(main_frame)
        
        # 状态栏
        self._create_status_bar(main_frame)
        
        # 绑定键盘事件
        self.window.bind('<Left>', self._previous_image)
        self.window.bind('<Right>', self._next_image)
        self.window.bind('<Delete>', self._delete_current_image)
        self.window.bind('<Escape>', self._close_window)
        self.window.focus_set()
    
    def _create_toolbar(self, parent):
        """创建工具栏"""
        toolbar = ttk.Frame(parent, style="Toolbar.TFrame")
        toolbar.pack(fill=tk.X, pady=(0, 10))
        
        # 导航按钮
        style_button(ttk.Button(toolbar, text="上一张 (←)", command=self.previous_image), "secondary").pack(side=tk.LEFT, padx=(0, 5))
        style_button(ttk.Button(toolbar, text="下一张 (→)", command=self.next_image), "secondary").pack(side=tk.LEFT, padx=(0, 5))
        
        # 分隔符
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)
        
        # 操作按钮
        style_button(ttk.Button(toolbar, text="删除图片 (Del)", command=self.delete_current_image), "danger").pack(side=tk.LEFT, padx=(0, 5))
        style_button(ttk.Button(toolbar, text="打开文件夹", command=self.open_image_folder), "secondary").pack(side=tk.LEFT, padx=(0, 5))
        
        # 关闭按钮（右对齐）
        style_button(ttk.Button(toolbar, text="关闭 (Esc)", command=self.close_window), "ghost").pack(side=tk.RIGHT)
    
    def _create_image_area(self, parent):
        """创建图片显示区域"""
        # 创建框架
        image_frame = ttk.LabelFrame(parent, text="图片预览", padding=12, style="App.TLabelframe")
        image_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # 创建画布和滚动区域
        self.canvas = tk.Canvas(
            image_frame, 
            bg='#F8FAFC',
            highlightthickness=1,
            highlightbackground='#D8E0EA'
        )
        
        # 创建可滚动的内部框架
        self.scrollable_frame = ttk.Frame(self.canvas, style="Surface.TFrame")
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self._configure_canvas_scroll()
        )
        
        # 将内部框架添加到画布
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        
        # 添加滚动条
        v_scrollbar = ttk.Scrollbar(image_frame, orient=tk.VERTICAL, command=self.canvas.yview)
        h_scrollbar = ttk.Scrollbar(image_frame, orient=tk.HORIZONTAL, command=self.canvas.xview)
        
        self.canvas.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        # 布局
        self.canvas.grid(row=0, column=0, sticky="nsew")
        v_scrollbar.grid(row=0, column=1, sticky="ns")
        h_scrollbar.grid(row=1, column=0, sticky="ew")
        
        # 配置权重
        image_frame.grid_rowconfigure(0, weight=1)
        image_frame.grid_columnconfigure(0, weight=1)
        
        # 绑定鼠标滚轮
        self.canvas.bind("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind("<Button-4>", self._on_mousewheel)
        self.canvas.bind("<Button-5>", self._on_mousewheel)
        
        # 初始加载网格视图
        self._load_grid_view()
    
    def _create_status_bar(self, parent):
        """创建状态栏"""
        status_frame = ttk.Frame(parent, style="Status.TFrame", padding=(8, 6))
        status_frame.pack(fill=tk.X)
        
        # 信息显示
        self.info_var = tk.StringVar()
        ttk.Label(status_frame, textvariable=self.info_var, style="StatusMuted.TLabel").pack(side=tk.LEFT)
        
        # 进度显示
        progress_frame = ttk.Frame(status_frame, style="Status.TFrame")
        progress_frame.pack(side=tk.RIGHT)
        
        self.progress_var = tk.StringVar()
        ttk.Label(progress_frame, textvariable=self.progress_var, style="StatusMuted.TLabel").pack(side=tk.LEFT)
    
    def _load_grid_view(self):
        """加载网格视图"""
        if not self.image_paths or not self.scrollable_frame:
            return
        
        # 清空现有内容
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
        
        # 计算每行显示的图片数
        columns = self.grid_columns
        row, col = 0, 0
        
        for idx, image_path in enumerate(self.image_paths):
            try:
                # 从缓存获取或加载缩略图
                if image_path in self.thumbnail_cache:
                    thumbnail = self.thumbnail_cache[image_path]
                else:
                    pil_image = Image.open(image_path)
                    pil_image.thumbnail(self.thumbnail_size, Image.Resampling.LANCZOS)
                    thumbnail = ImageTk.PhotoImage(pil_image)
                    self.thumbnail_cache[image_path] = thumbnail
                
                # 创建图片标签
                img_label = ttk.Label(
                    self.scrollable_frame,
                    image=thumbnail,
                    cursor="hand2"
                )
                img_label.grid(
                    row=row,
                    column=col,
                    padx=self.padding,
                    pady=self.padding
                )
                
                # 绑定点击事件
                img_label.bind(
                    "<Button-1>",
                    lambda e, i=idx: self._show_single_image(i)
                )
                
                # 更新行列位置
                col += 1
                if col >= columns:
                    col = 0
                    row += 1
                    
            except Exception as e:
                self.logger.error(f"加载缩略图失败: {image_path} - {e}")
    
    def _show_single_image(self, index):
        """显示单张图片"""
        self.current_index = index
        self._load_current_image()
    
    def _load_current_image(self):
        """加载当前图片"""
        if not self.image_paths or self.current_index >= len(self.image_paths) or not self.canvas:
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
            
            # 调整窗口大小以适应图片
            self._adjust_window_size(display_width, display_height)
            
            # 调整图片尺寸
            if (display_width, display_height) != (original_width, original_height):
                pil_image = pil_image.resize((display_width, display_height), Image.Resampling.LANCZOS)
            
            # 转换为 PhotoImage
            self.current_image = ImageTk.PhotoImage(pil_image)
            
            # 清空画布
            self.canvas.delete("all")
            
            # 设置画布滚动区域
            self.canvas.configure(scrollregion=(0, 0, display_width, display_height))
            
            # 设置画布大小以匹配图片
            self.canvas.configure(width=display_width, height=display_height)
            
            # 在画布中央显示图片
            self.canvas.create_image(
                display_width // 2, 
                display_height // 2, 
                anchor=tk.CENTER, 
                image=self.current_image
            )
            
            # 更新窗口标题
            filename = os.path.basename(image_path)
            if self.window:
                self.window.title(f"图片预览 - {filename} ({self.current_index + 1}/{len(self.image_paths)})")
            
            # 更新状态信息
            file_size = os.path.getsize(image_path)
            file_size_str = self._format_file_size(file_size)
            
            if self.info_var:
                self.info_var.set(
                    f"文件: {filename} | 尺寸: {original_width}×{original_height} | 大小: {file_size_str}"
                )
            if self.progress_var:
                self.progress_var.set(f"{self.current_index + 1} / {len(self.image_paths)}")
            
            self.logger.info(f"加载图片: {filename} (原始尺寸: {original_width}x{original_height}, 显示尺寸: {display_width}x{display_height})")
            
        except Exception as e:
            self.logger.error(f"加载图片失败: {image_path} - {e}")
            messagebox.showerror("错误", f"加载图片失败: {os.path.basename(image_path)}")
            
            # 尝试加载下一张图片
            if self.current_index < len(self.image_paths) - 1:
                self.current_index += 1
                self._load_current_image()
    
    def _calculate_display_size(self, width, height):
        """计算显示尺寸"""
        # 如果图片比最大显示尺寸小，保持原尺寸
        if width <= self.max_display_width and height <= self.max_display_height:
            return width, height
        
        # 计算缩放比例
        width_ratio = self.max_display_width / width
        height_ratio = self.max_display_height / height
        scale_ratio = min(width_ratio, height_ratio)
        
        # 计算新尺寸
        new_width = int(width * scale_ratio)
        new_height = int(height * scale_ratio)
        
        return new_width, new_height
    
    def _adjust_window_size(self, image_width, image_height):
        """
        根据图片尺寸调整窗口大小
        
        Args:
            image_width: 图片宽度
            image_height: 图片高度
        """
        if not self.window:
            return
        
        # 计算需要的窗口尺寸（加上边距）
        needed_width = image_width + self.window_padding
        needed_height = image_height + self.window_padding
        
        # 应用最小限制
        window_width = max(needed_width, self.min_window_width)
        window_height = max(needed_height, self.min_window_height)
        
        # 获取屏幕尺寸限制
        screen_width = self.window.winfo_screenwidth()
        screen_height = self.window.winfo_screenheight()
        
        # 限制窗口尺寸不超过屏幕的90%
        max_window_width = int(screen_width * 0.9)
        max_window_height = int(screen_height * 0.9)
        
        window_width = min(window_width, max_window_width)
        window_height = min(window_height, max_window_height)
        
        # 获取当前窗口位置
        current_geometry = self.window.geometry()
        if '+' in current_geometry:
            # 提取当前位置
            parts = current_geometry.split('+')
            if len(parts) >= 3:
                x_pos = parts[1]
                y_pos = parts[2]
            else:
                x_pos = y_pos = None
        else:
            x_pos = y_pos = None
        
        # 计算窗口位置（屏幕中央）
        if x_pos is None or y_pos is None:
            x_pos = (screen_width - window_width) // 2
            y_pos = (screen_height - window_height) // 2
        
        # 设置窗口尺寸和位置
        self.window.geometry(f"{window_width}x{window_height}+{x_pos}+{y_pos}")
        
        # 强制更新窗口，确保尺寸生效
        self.window.update_idletasks()
        
        self.logger.debug(f"调整窗口尺寸: {window_width}x{window_height} (图片: {image_width}x{image_height})")
    
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
    
    def previous_image(self):
        """显示上一张图片"""
        if self.image_paths and self.current_index > 0:
            self.current_index -= 1
            self._load_current_image()
    
    def next_image(self):
        """显示下一张图片"""
        if self.image_paths and self.current_index < len(self.image_paths) - 1:
            self.current_index += 1
            self._load_current_image()
    
    def delete_current_image(self):
        """删除当前图片"""
        if not self.image_paths or self.current_index >= len(self.image_paths):
            return
        
        image_path = self.image_paths[self.current_index]
        filename = os.path.basename(image_path)
        
        result = messagebox.askyesno(
            "确认删除",
            f"确定要删除图片 '{filename}' 吗？\n\n此操作无法撤销！",
            icon='warning'
        )
        
        if result:
            try:
                os.remove(image_path)
                self.logger.info(f"已删除图片: {filename}")
                
                # 从列表中移除
                self.image_paths.pop(self.current_index)
                
                # 更新显示
                if not self.image_paths:
                    messagebox.showinfo("提示", "所有图片已删除")
                    self.close_window()
                    return
                
                # 调整当前索引
                if self.current_index >= len(self.image_paths):
                    self.current_index = len(self.image_paths) - 1
                
                # 加载新的当前图片
                self._load_current_image()
                
            except Exception as e:
                self.logger.error(f"删除图片失败: {filename} - {e}")
                messagebox.showerror("错误", f"删除图片失败: {e}")
    
    def open_image_folder(self):
        """打开当前图片所在文件夹"""
        if not self.image_paths or self.current_index >= len(self.image_paths):
            return
        
        image_path = self.image_paths[self.current_index]
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
        if self.window:
            self.window.destroy()
    
    # 事件处理方法
    def _previous_image(self, event):
        """键盘事件：上一张"""
        self.previous_image()
    
    def _next_image(self, event):
        """键盘事件：下一张"""
        self.next_image()
    
    def _delete_current_image(self, event):
        """键盘事件：删除"""
        self.delete_current_image()
    
    def _close_window(self, event):
        """键盘事件：关闭"""
        self.close_window()
    
    def _toggle_fullscreen(self, event):
        """键盘事件：切换全屏"""
        if self.window:
            # 切换全屏状态
            is_fullscreen = self.window.attributes('-fullscreen')
            self.window.attributes('-fullscreen', not is_fullscreen)
    
    def _on_mousewheel(self, event):
        """鼠标滚轮事件"""
        if not self.canvas:
            return
            
        if event.delta:
            # Windows
            delta = event.delta / 120
        else:
            # Linux
            if event.num == 4:
                delta = 1
            elif event.num == 5:
                delta = -1
            else:
                return
        
        # 垂直滚动
        if self.canvas:
            self.canvas.yview_scroll(int(-delta), "units")

    def _configure_canvas_scroll(self):
        """安全配置canvas滚动区域"""
        if self.canvas:
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))
