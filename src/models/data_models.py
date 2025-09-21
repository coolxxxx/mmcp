#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据模型定义
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum
from datetime import datetime
import uuid

class TaskStatus(Enum):
    """任务状态枚举"""
    PENDING = "pending"
    RUNNING = "running" 
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    SCHEDULED = "scheduled"

class DownloadStatus(Enum):
    """下载状态枚举"""
    WAITING = "waiting"
    DOWNLOADING = "downloading"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

@dataclass
class ImageInfo:
    """图片信息"""
    url: str
    filename: str
    file_path: str
    size: Optional[int] = None
    width: Optional[int] = None
    height: Optional[int] = None
    file_type: Optional[str] = None
    min_file_size: int = 0  # 最小文件大小，由配置决定
    status: DownloadStatus = DownloadStatus.WAITING
    progress: float = 0.0
    error_message: Optional[str] = None
    retry_count: int = 0
    
    def __post_init__(self):
        """后初始化处理"""
        if not self.file_type and self.filename:
            self.file_type = self.filename.split('.')[-1].lower()

@dataclass 
class PageInfo:
    """页面信息"""
    url: str
    title: Optional[str] = None
    description: Optional[str] = None  # 新增：页面描述信息
    images: List[ImageInfo] = field(default_factory=list)
    sub_pages: List[str] = field(default_factory=list)
    parsed: bool = False
    error_message: Optional[str] = None

@dataclass
class DownloadTask:
    """下载任务"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    base_url: str = ""
    download_path: str = ""
    status: TaskStatus = TaskStatus.PENDING
    created_time: datetime = field(default_factory=datetime.now)
    started_time: Optional[datetime] = None
    completed_time: Optional[datetime] = None
    
    # 任务配置
    max_depth: int = 1  # 子页面深度
    image_filters: Dict[str, Any] = field(default_factory=dict)
    url_patterns: List[str] = field(default_factory=list)  # 通配符模式
    
    # 任务状态
    pages: List[PageInfo] = field(default_factory=list)
    total_images: int = 0
    downloaded_images: int = 0
    failed_images: int = 0
    total_size: int = 0
    downloaded_size: int = 0
    
    # 调度设置
    scheduled_time: Optional[datetime] = None
    repeat_interval: Optional[int] = None  # 重复间隔（分钟）
    
    # 错误信息
    error_message: Optional[str] = None
    
    # 状态消息（用于显示详细进度）
    status_message: Optional[str] = None
    
    @property
    def progress(self) -> float:
        """计算总体进度"""
        if self.total_images == 0:
            return 0.0
        return (self.downloaded_images / self.total_images) * 100
    
    @property
    def is_finished(self) -> bool:
        """是否已完成"""
        return self.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]
    
    @property
    def duration(self) -> Optional[float]:
        """任务持续时间（秒）"""
        if self.started_time:
            end_time = self.completed_time or datetime.now()
            return (end_time - self.started_time).total_seconds()
        return None

@dataclass
class DownloadStats:
    """下载统计信息"""
    total_tasks: int = 0
    running_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    total_images: int = 0
    downloaded_images: int = 0
    failed_images: int = 0
    total_size: int = 0
    downloaded_size: int = 0
    download_speed: float = 0.0  # bytes/s
    
    @property
    def success_rate(self) -> float:
        """成功率"""
        if self.total_images == 0:
            return 0.0
        return (self.downloaded_images / self.total_images) * 100
    
    @property
    def total_progress(self) -> float:
        """总体进度"""
        if self.total_images == 0:
            return 0.0
        return (self.downloaded_images / self.total_images) * 100

@dataclass
class BatchTaskConfig:
    """批量任务创建配置"""
    main_url: str                           # 主页面URL
    max_pages: int = 100                    # 最大页面数
    timeout_seconds: int = 30               # 超时设置
    skip_existing: bool = True              # 跳过已存在目录
    detect_images: bool = True              # 检测图片内容
    url_patterns: List[str] = field(default_factory=list)  # URL过滤模式
    concurrent_analysis: int = 5            # 并发分析数
    fast_mode: bool = False                 # 快速模式（跳过部分验证）
    scheduled_time: Optional[datetime] = None  # 计划执行时间
    
@dataclass
class BatchCreationResult:
    """批量创建结果"""
    total_found: int                        # 发现的页面总数
    valid_tasks: int                        # 有效任务数
    duplicate_skipped: int                  # 跳过的重复任务
    failed_analysis: int                    # 分析失败的页面
    created_tasks: List[DownloadTask]       # 创建的任务列表
    execution_mode: str                     # 执行模式
    scheduled_time: Optional[datetime] = None  # 计划执行时间
    error_pages: List[str] = field(default_factory=list)  # 分析失败的页面
    
@dataclass
class TaskPreviewInfo:
    """任务预览信息"""
    url: str                                # 页面URL
    estimated_images: int                   # 预估图片数
    estimated_size: str                     # 预估大小
    directory_name: str                     # 目录名
    status: str                             # 状态（新建/重复/错误）
    selected: bool = True                   # 是否选中
    error_message: Optional[str] = None     # 错误信息
    
@dataclass
class ValidationResult:
    """验证结果"""
    is_valid: bool                          # 是否有效
    reason: str = ""                        # 原因
    directory_exists: bool = False          # 目录是否存在
    task_exists: bool = False               # 任务是否存在
    network_accessible: bool = True         # 网络是否可达
    has_images: bool = False                # 是否包含图片
    
@dataclass
class PageAnalysisResult:
    """页面分析结果"""
    url: str                                # 页面URL
    success: bool = False                   # 分析是否成功
    image_count: int = 0                    # 图片数量
    sub_page_count: int = 0                 # 子页面数量
    title: Optional[str] = None             # 页面标题
    error_message: Optional[str] = None     # 错误信息
    analysis_time: float = 0.0              # 分析耗时（秒）
    
@dataclass
class Config:
    """全局配置"""
    download_path: str = "./downloads"
    max_concurrent_tasks: int = 5
    max_retries: int = 3
    timeout: int = 30
    proxy: Optional[str] = None
    user_agent: str = "Mozilla/5.0"
    save_logs: bool = True
    log_level: str = "INFO"
    auto_update: bool = True
    
@dataclass
class Config:
    """全局配置"""
    download_path: str = "./downloads"
    max_concurrent_tasks: int = 5
    max_retries: int = 3
    timeout: int = 30
    proxy: Optional[str] = None
    user_agent: str = "Mozilla/5.0"
    save_logs: bool = True
    log_level: str = "INFO"
    auto_update: bool = True
    
@dataclass
class AppSettings:
    """应用设置"""
    theme: str = "default"
    language: str = "zh_CN"
    auto_start_download: bool = False
    show_notifications: bool = True
    minimize_to_tray: bool = False
    max_concurrent_downloads: int = 5
    default_download_path: str = "./downloads"
    
    # 图片过滤默认设置
    default_image_types: List[str] = field(default_factory=lambda: ["jpg", "jpeg", "png", "gif"])
    default_min_size: int = 51200  # 50KB
    default_max_size: int = 10485760  # 10MB