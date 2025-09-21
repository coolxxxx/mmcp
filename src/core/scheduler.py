#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
任务调度器模块
实现任务调度、通配符支持和批量任务管理
"""

import re
import threading
import time
import os
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Callable, Pattern, TypedDict, Any, Union
import logging
from queue import Queue, PriorityQueue
import fnmatch
from dataclasses import dataclass, field

from .parser import WebPageParser
from .downloader import DownloadManager
from .file_manager import FileManager
from ..models.data_models import DownloadTask, TaskStatus, PageInfo, ImageInfo
from ..core.config import Config
from ..utils.url_utils import UrlUtils

@dataclass
class ScheduledTask:
    """计划任务"""
    task: DownloadTask
    scheduled_time: datetime
    priority: int = 0
    
    def __lt__(self, other):
        return (self.scheduled_time, self.priority) < (other.scheduled_time, other.priority)

class TaskScheduler:
    """任务调度器"""
    
    def __init__(self, config: Config):
        """
        初始化任务调度器
        
        Args:
            config: 配置对象
        """
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # 组件
        self.parser = WebPageParser(config)
        
        # 获取配置值
        download_path = config.get('download_path', './downloads')
        self.file_manager = FileManager(download_path)
        self.download_manager = DownloadManager(config.get_all(), self.file_manager)
        
        # 任务管理
        self.tasks: Dict[str, DownloadTask] = {}
        self.scheduled_tasks = PriorityQueue()
        self.task_queue = Queue()
        
        # 调度配置
        self.max_concurrent_tasks = config.get('scheduler.max_concurrent_tasks', 3)
        self.check_interval = config.get('scheduler.task_check_interval', 0.5)
        self.check_interval = 0.5  # 设置为0.5秒检查一次，确保快速响应
        
        # 状态管理
        self.is_running = False
        self.running_tasks = set()
        self.scheduler_thread = None
        self.task_callbacks = []  # 任务状态回调
        
        # 线程锁
        self.lock = threading.Lock()
    
    def add_task_callback(self, callback: 'Callable[[DownloadTask, TaskStatus], None]'):
        """
        添加任务状态回调
        
        Args:
            callback: 回调函数，接收(task, old_status)参数
        """
        self.task_callbacks.append(callback)
    
    def create_task_from_url(self, url: str, name: Optional[str] = None, download_path: Optional[str] = None, 
                           max_depth: int = 1, url_patterns: Optional[List[str]] = None,
                           scheduled_time: Optional[datetime] = None, auto_parse: bool = True) -> DownloadTask:
        """
        从URL创建下载任务（增强版）
        
        Args:
            url: 基础URL（支持短链接和相对URL）
            name: 任务名称（可选）
            download_path: 下载路径（可选）
            max_depth: 最大解析深度（默认1）
            url_patterns: URL通配符模式列表（可选）
            scheduled_time: 计划执行时间（可选）
            auto_parse: 是否自动解析URL内容（默认True）
            
        Returns:
            创建的任务对象
            
        Raises:
            ValueError: 当URL无效时抛出
        """
        # URL预处理
        url = self._preprocess_url(url)
        
        # 参数验证
        if not self._is_valid_url(url):
            raise ValueError(f"无效的URL格式: {url}")
        
        # 创建基础任务
        task = DownloadTask(
            name=name or f"下载任务 {datetime.now().strftime('%Y%m%d_%H%M%S')}",
            base_url=url,
            download_path=download_path or str(self.file_manager.base_path),
            max_depth=max_depth,
            url_patterns=url_patterns or [],
            scheduled_time=scheduled_time
        )
        
        # 自动解析（如果需要）
        if auto_parse:
            try:
                page_info = self.parser.parse_page(url)
                if page_info.images:
                    task.pages.append(page_info)
                    task.total_images = len(page_info.images)
            except Exception as e:
                self.logger.warning(f"自动解析URL内容失败: {url} - {e}")
        
        with self.lock:
            self.tasks[task.id] = task
        
        self.logger.info(f"创建任务: {task.name} ({task.id})")
        return task

    def _preprocess_url(self, url: str) -> str:
        """URL预处理"""
        url = url.strip()
        
        # 补全协议
        if not url.startswith(('http://', 'https://')):
            url = f'http://{url}'
            
        # 规范化URL（移除重复参数等）
        parsed = urlparse(url)
        query_params = parse_qs(parsed.query, keep_blank_values=True)
        
        # 去重参数
        clean_params = {}
        for k, v in query_params.items():
            clean_params[k] = v[-1]  # 保留最后一个值
            
        # 重建URL
        new_query = urlencode(clean_params, doseq=True)
        new_parsed = parsed._replace(query=new_query)
        url = urlunparse(new_parsed)
        
        return url

    def _is_valid_url(self, url: str) -> bool:
        """验证URL有效性"""
        try:
            parsed = urlparse(url)
            if not all([parsed.scheme, parsed.netloc]):
                return False
                
            # 检查是否为图片链接
            path = parsed.path.lower()
            img_exts = ('.jpg', '.jpeg', '.png', '.gif', '.webp')
            if any(path.endswith(ext) for ext in img_exts):
                return True
                
            # 检查是否为HTML页面
            html_exts = ('.html', '.htm', '.php', '.asp', '.aspx')
            if any(path.endswith(ext) for ext in html_exts):
                return True
                
            # 没有扩展名的URL也允许（可能是动态生成的）
            return '.' not in os.path.basename(path) or path.endswith('/')
            
        except Exception:
            return False

    
    def create_batch_tasks_from_patterns(self, base_url: str, patterns: List[str], 
                                       name_template: Optional[str] = None, **kwargs) -> List[DownloadTask]:
        """
        根据通配符模式创建批量任务
        
        Args:
            base_url: 基础URL
            patterns: 通配符模式列表
            name_template: 名称模板
            **kwargs: 其他任务参数
            
        Returns:
            创建的任务列表
        """
        tasks = []
        
        for i, pattern in enumerate(patterns):
            try:
                # 展开通配符模式
                urls = self._expand_url_pattern(base_url, pattern)
                
                for j, url in enumerate(urls):
                    name = name_template.format(index=i+1, url_index=j+1) if name_template else None
                    
                    task = self.create_task_from_url(
                        url=url,
                        name=name,
                        **kwargs
                    )
                    tasks.append(task)
                    
            except Exception as e:
                self.logger.error(f"创建批量任务失败 {pattern}: {e}")
        
        return tasks
    
    def schedule_task(self, task: DownloadTask, priority: int = 0):
        """
        调度任务
        
        Args:
            task: 下载任务
            priority: 优先级（数字越小优先级越高）
        """
        if task.scheduled_time:
            # 计划任务
            scheduled_task = ScheduledTask(task, task.scheduled_time, priority)
            self.scheduled_tasks.put(scheduled_task)
            task.status = TaskStatus.SCHEDULED
            self.logger.info(f"任务已调度: {task.name} 执行时间: {task.scheduled_time}")
        else:
            # 立即执行
            self.task_queue.put((priority, task))
            task.status = TaskStatus.PENDING
            self.logger.info(f"任务已排队: {task.name}")
        
        self._notify_task_status_change(task, TaskStatus.PENDING)
    
    def start_scheduler(self):
        """启动调度器"""
        if self.is_running:
            self.logger.warning("调度器已在运行")
            return
        
        self.is_running = True
        self.scheduler_thread = threading.Thread(target=self._scheduler_loop, daemon=True)
        self.scheduler_thread.start()
        
        self.logger.info("任务调度器已启动")
    
    def stop_scheduler(self):
        """停止调度器"""
        self.is_running = False
        if self.scheduler_thread:
            self.scheduler_thread.join(timeout=5)
        
        # 停止所有正在运行的任务
        with self.lock:
            for task_id in list(self.running_tasks):
                task = self.tasks.get(task_id)
                if task:
                    task.status = TaskStatus.CANCELLED
                    self._notify_task_status_change(task, TaskStatus.RUNNING)
        
        self.logger.info("任务调度器已停止")
    
    def _scheduler_loop(self):
        """调度器主循环"""
        self.logger.info("调度器循环开始")
        
        while self.is_running:
            try:
                # 检查计划任务
                self._check_scheduled_tasks()
                
                # 执行排队的任务
                pending_count = self.task_queue.qsize()
                if pending_count > 0:
                    self.logger.info(f"检查到 {pending_count} 个待处理任务")
                
                self._execute_pending_tasks()
                
                # 检查重复任务
                self._check_repeat_tasks()
                
                time.sleep(self.check_interval)
                
            except Exception as e:
                self.logger.error(f"调度器循环异常: {e}")
                time.sleep(5)
    
    def _check_scheduled_tasks(self):
        """检查计划任务"""
        now = datetime.now()
        ready_tasks = []
        
        # 收集到时间的任务
        while not self.scheduled_tasks.empty():
            scheduled_task = self.scheduled_tasks.get()
            
            if scheduled_task.scheduled_time <= now:
                ready_tasks.append(scheduled_task)
            else:
                # 放回队列
                self.scheduled_tasks.put(scheduled_task)
                break
        
        # 将到时间的任务加入执行队列
        for scheduled_task in ready_tasks:
            self.task_queue.put((scheduled_task.priority, scheduled_task.task))
            scheduled_task.task.status = TaskStatus.PENDING
            self._notify_task_status_change(scheduled_task.task, TaskStatus.SCHEDULED)
    
    def _execute_pending_tasks(self):
        """执行待处理任务"""
        running_count = len(self.running_tasks)
        max_tasks = self.max_concurrent_tasks
        queue_size = self.task_queue.qsize()
        
        # 立即执行排队的任务，不等待
        while len(self.running_tasks) < self.max_concurrent_tasks and not self.task_queue.empty():
            try:
                priority, task = self.task_queue.get_nowait()
                
                self.logger.info(f"启动任务: {task.name}")
                
                # 启动任务
                threading.Thread(
                    target=self._execute_task, 
                    args=(task,), 
                    daemon=True
                ).start()
                
            except Exception as e:
                self.logger.error(f"启动任务失败: {e}")
                break
    
    def _execute_task(self, task: DownloadTask):
        """
        执行单个任务
        
        Args:
            task: 下载任务
        """
        try:
            with self.lock:
                self.running_tasks.add(task.id)
            
            old_status = task.status
            task.status = TaskStatus.RUNNING
            task.started_time = datetime.now()
            self._notify_task_status_change(task, old_status)
            
            self.logger.info(f"开始执行任务: {task.name}")
            
            # 创建任务目录（智能复用已存在的同名目录）
            task_dir = self.file_manager.create_task_directory(task.base_url, task.name, reuse_existing=True)
            task.download_path = task_dir
            
            # 检查是否已有下载文件
            existing_check = self.file_manager.check_existing_downloads(task_dir, task.base_url)
            if existing_check['has_files']:
                self.logger.info(f"发现已存在的下载目录，将继续使用: {task_dir}")
                self.logger.info(f"目录中已有 {existing_check['file_count']} 个文件，{len(existing_check['image_files'])} 张图片")
            
            # 解析页面和子页面
            all_images = []
            urls_to_parse = [task.base_url]
            
            # 如果有URL模式，展开它们
            if task.url_patterns:
                for pattern in task.url_patterns:
                    expanded_urls = self._expand_url_pattern(task.base_url, pattern)
                    urls_to_parse.extend(expanded_urls)
            
            # 递归解析所有URL和它们的子页面
            processed_urls = set()
            
            while urls_to_parse:
                current_url = urls_to_parse.pop(0)
                
                if current_url in processed_urls:
                    continue
                    
                processed_urls.add(current_url)
                
                try:
                    self.logger.info(f"正在解析页面: {current_url}")
                    page_info = self.parser.parse_page(current_url)  # 只解析当前页面，不递归
                    task.pages.append(page_info)
                    
                    # 保存页面描述信息（如果有的话）
                    if page_info.description and page_info.title:
                        self.file_manager.save_page_description(
                            task_dir, 
                            page_info.title, 
                            page_info.description, 
                            current_url
                        )
                    
                    # 设置图片文件路径（支持跳过已存在的文件）
                    valid_images = []
                    skipped_count = 0
                    
                    for image in page_info.images:
                        file_path = self.file_manager.get_image_file_path(
                            task_dir, image.url, image.filename, skip_existing=True
                        )
                        
                        if file_path == "SKIP_EXISTING":
                            # 文件已存在，跳过下载
                            skipped_count += 1
                            self.logger.debug(f"跳过已存在的图片: {image.filename}")
                        else:
                            image.file_path = file_path
                            valid_images.append(image)
                    
                    # 更新页面信息中的图片列表
                    page_info.images = valid_images
                    
                    if skipped_count > 0:
                        self.logger.info(f"页面 {current_url} 跳过了 {skipped_count} 张已存在的图片")
                    
                    all_images.extend(page_info.images)
                    self.logger.info(f"页面 {current_url} 找到 {len(page_info.images)} 张图片")
                    
                    # 如果当前深度还允许，添加子页面到解析列表
                    if len(processed_urls) == 1:  # 只有主页面才提取子页面
                        # 重新解析主页面以获取子页面链接
                        main_page_info = self.parser.parse_page(current_url)
                        sub_pages = main_page_info.sub_pages
                        
                        self.logger.info(f"主页面找到 {len(sub_pages)} 个子页面")
                        
                        # 添加子页面到解析队列
                        for sub_page in sub_pages:
                            if sub_page not in processed_urls:
                                urls_to_parse.append(sub_page)
                                self.logger.debug(f"添加子页面到解析队列: {sub_page}")
                    
                except Exception as e:
                    self.logger.error(f"解析页面失败 {current_url}: {e}")
                    continue
            
            self.logger.info(f"总共处理了 {len(processed_urls)} 个页面，找到 {len(all_images)} 张图片")
            
            # 更新任务统计
            task.total_images = len(all_images)
            
            if all_images:
                self.logger.info(f"准备开始下载 {len(all_images)} 张图片")
                
                # 显示前几个图片信息作为调试
                for i, img in enumerate(all_images[:3]):
                    self.logger.info(f"图片 {i+1}: {img.filename} - {img.url}")
                
                # 在下载前进行预过滤，移除不符合要求的图片
                filtered_images = self._pre_filter_images(all_images)
                task.total_images = len(filtered_images)  # 更新总数
                
                if len(filtered_images) != len(all_images):
                    self.logger.info(f"经过预过滤，剩余 {len(filtered_images)} 张图片符合下载条件")
                
                if filtered_images:
                    # 开始下载
                    self.download_manager.start_download_batch(filtered_images)
                    self.logger.info("下载任务已提交给下载管理器")
                    
                    # 等待下载完成
                    self.logger.info("等待下载完成...")
                    download_started = False
                    
                    while self.download_manager.is_downloading():
                        download_started = True
                        time.sleep(2)  # 增加等待间隔，减少日志频率
                        
                        # 更新任务进度
                        stats = self.download_manager.get_download_stats()
                        task.downloaded_images = stats['downloaded_images']
                        task.failed_images = stats['failed_images']
                        task.downloaded_size = stats['downloaded_size']
                        
                        # 记录进度（减少日志频率）
                        total_processed = stats['downloaded_images'] + stats['failed_images']
                        if total_processed > 0 and total_processed % 10 == 0:  # 每10张图片记录一次
                            self.logger.info(f"下载进度: 成功 {stats['downloaded_images']}, 失败 {stats['failed_images']}, 总计 {task.total_images} ({total_processed}/{task.total_images})")
                    
                    # 等待一下确保所有统计信息更新完成
                    if download_started:
                        time.sleep(1)
                    
                    # 获取最终统计
                    final_stats = self.download_manager.get_download_stats()
                    task.downloaded_images = final_stats['downloaded_images']
                    task.failed_images = final_stats['failed_images']
                    task.downloaded_size = final_stats['downloaded_size']
                    
                    self.logger.info(f"下载任务完成，最终统计: 成功 {task.downloaded_images}, 失败 {task.failed_images}")
                else:
                    self.logger.warning("经过预过滤后没有符合条件的图片，跳过下载")
            else:
                self.logger.warning("没有找到任何图片，跳过下载")
            
            # 任务完成判断：只要目录中有图片文件，就认为任务完成
            task.completed_time = datetime.now()
            
            # 检查目录中是否有图片文件
            existing_check = self.file_manager.check_existing_downloads(task_dir, task.base_url)
            has_images = len(existing_check['image_files']) > 0
            
            if has_images:
                task.status = TaskStatus.COMPLETED
                self.logger.info(f"任务完成: {task.name}, 目录中有 {len(existing_check['image_files'])} 张图片，成功下载: {task.downloaded_images}, 失败: {task.failed_images}")
            else:
                task.status = TaskStatus.FAILED
                task.error_message = "目录中没有图片文件"
                self.logger.warning(f"任务失败: {task.name}, 目录中没有图片文件")
            
        except Exception as e:
            self.logger.error(f"任务执行失败 {task.name}: {e}")
            task.status = TaskStatus.FAILED
            task.error_message = str(e)
            task.completed_time = datetime.now()
        
        finally:
            with self.lock:
                self.running_tasks.discard(task.id)
            
            self._notify_task_status_change(task, TaskStatus.RUNNING)
    
    def _check_repeat_tasks(self):
        """检查重复任务"""
        with self.lock:
            for task in self.tasks.values():
                if (task.repeat_interval and 
                    task.status == TaskStatus.COMPLETED and 
                    task.completed_time):
                    
                    # 计算下次执行时间
                    next_time = task.completed_time + timedelta(minutes=task.repeat_interval)
                    
                    if datetime.now() >= next_time:
                        # 创建新的重复任务
                        new_task = DownloadTask(
                            name=f"{task.name} (重复)",
                            base_url=task.base_url,
                            download_path=task.download_path,
                            max_depth=task.max_depth,
                            url_patterns=task.url_patterns.copy(),
                            repeat_interval=task.repeat_interval
                        )
                        
                        self.tasks[new_task.id] = new_task
                        self.schedule_task(new_task)
                        
                        # 重置原任务的重复设置
                        task.repeat_interval = None
    
    def _expand_url_pattern(self, base_url: str, pattern: str) -> List[str]:
        """
        展开URL通配符模式
        
        Args:
            base_url: 基础URL
            pattern: 通配符模式
            
        Returns:
            展开的URL列表
        """
        urls = []
        
        try:
            # 数字范围模式: {1-10}
            range_pattern = r'\{(\d+)-(\d+)\}'
            range_matches = re.findall(range_pattern, pattern)
            
            if range_matches:
                for start_str, end_str in range_matches:
                    start, end = int(start_str), int(end_str)
                    
                    for num in range(start, end + 1):
                        url = re.sub(range_pattern, str(num), pattern, count=1)
                        urls.append(url)
                        
                return urls
            
            # 列表模式: {a,b,c}
            list_pattern = r'\{([^}]+)\}'
            list_match = re.search(list_pattern, pattern)
            
            if list_match:
                items = [item.strip() for item in list_match.group(1).split(',')]
                
                for item in items:
                    url = pattern.replace(list_match.group(0), item)
                    urls.append(url)
                    
                return urls
            
            # 星号通配符: 基于基础URL生成相似URL
            if '*' in pattern:
                # 提取基础URL中的数字
                numbers = UrlUtils.extract_numbers_from_url(base_url)
                
                if numbers:
                    last_num = int(numbers[-1])
                    
                    # 生成前后各5个URL
                    for i in range(max(1, last_num - 5), last_num + 6):
                        url = base_url.replace(numbers[-1], str(i))
                        if fnmatch.fnmatch(url, pattern):
                            urls.append(url)
            
            # 如果没有特殊模式，直接使用pattern作为URL
            if not urls:
                urls.append(pattern)
                
        except Exception as e:
            self.logger.error(f"展开URL模式失败 {pattern}: {e}")
            urls.append(pattern)
        
        return urls
    
    def _pre_filter_images(self, images: List[ImageInfo]) -> List[ImageInfo]:
        """
        在下载前预过滤图片，移除不符合条件的图片
        支持文件大小和图片分辨率双重过滤，并优化性能
        
        Args:
            images: 图片信息列表
            
        Returns:
            过滤后的图片列表
        """
        from PIL import Image
        import requests
        from io import BytesIO
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        if not images:
            return []
        
        # 获取过滤配置
        image_filters = self.config.get('image_filters', {})
        min_size = image_filters.get('min_size', 51200)  # 使用配置值，默认50KB
        max_size = image_filters.get('max_size', 10485760)  # 10MB
        min_width = image_filters.get('min_width', 800)  # 最小宽度
        min_height = image_filters.get('min_height', 600)  # 最小高度
        
        # 新的性能配置
        enable_size_filter = image_filters.get('enable_size_filter', True)
        enable_resolution_filter = image_filters.get('enable_resolution_filter', True)
        resolution_check_mode = image_filters.get('resolution_check_mode', 'smart')  # fast, smart, always
        parallel_filter = image_filters.get('parallel_filter', True)
        filter_timeout = image_filters.get('filter_timeout', 3)
        
        filtered_images = []
        stats = {
            'filtered_size': 0,
            'filtered_resolution': 0,
            'resolution_check_failed': 0,
            'size_check_failed': 0
        }
        
        self.logger.info(f"开始预过滤 {len(images)} 张图片")
        self.logger.info(f"过滤模式: 大小过滤={'ON' if enable_size_filter else 'OFF'}, 分辨率过滤={'ON' if enable_resolution_filter else 'OFF'}")
        
        if enable_size_filter:
            self.logger.info(f"大小过滤条件: {min_size}-{max_size} 字节")
        if enable_resolution_filter:
            self.logger.info(f"分辨率过滤条件: {min_width}x{min_height} 以上, 检查模式: {resolution_check_mode}")
        
        def filter_single_image(image_info):
            """过滤单个图片"""
            try:
                result = {
                    'image': image_info,
                    'passed': True,
                    'reason': '',
                    'file_size': None,
                    'width': None,
                    'height': None
                }
                
                # 步骤1: 文件大小检查
                if enable_size_filter:
                    try:
                        head_response = self.parser.session.head(image_info.url, timeout=filter_timeout)
                        
                        if head_response.status_code == 200:
                            content_length = head_response.headers.get('content-length')
                            
                            if content_length:
                                file_size = int(content_length)
                                result['file_size'] = file_size
                                image_info.size = file_size
                                
                                # 文件大小过滤
                                if file_size < min_size:
                                    result['passed'] = False
                                    result['reason'] = f'文件过小 ({file_size} < {min_size})'
                                    return result
                                
                                if file_size > max_size:
                                    result['passed'] = False
                                    result['reason'] = f'文件过大 ({file_size} > {max_size})'
                                    return result
                                
                                # 设置配置的最小文件大小到ImageInfo对象
                                image_info.min_file_size = min_size
                    except Exception as e:
                        stats['size_check_failed'] += 1
                        # 大小检查失败，但不直接过滤掉
                        pass
                
                # 步骤2: 分辨率检查
                if enable_resolution_filter:
                    # 根据模式决定是否检查分辨率
                    should_check_resolution = False
                    
                    if resolution_check_mode == 'always':
                        should_check_resolution = True
                    elif resolution_check_mode == 'smart':
                        # 智能模式：只有通过大小过滤的才检查分辨率
                        if not enable_size_filter or result['file_size'] is not None:
                            should_check_resolution = True
                    # 'fast' 模式不检查分辨率
                    
                    if should_check_resolution:
                        try:
                            # 使用Range请求只下载前几KB数据来获取图片信息
                            headers = {'Range': 'bytes=0-8192'}  # 只下载前8KB
                            partial_response = self.parser.session.get(image_info.url, headers=headers, timeout=filter_timeout)
                            
                            if partial_response.status_code in (200, 206):  # 206是部分内容响应
                                try:
                                    img = Image.open(BytesIO(partial_response.content))
                                    width, height = img.size
                                    
                                    result['width'] = width
                                    result['height'] = height
                                    image_info.width = width
                                    image_info.height = height
                                    
                                    # 分辨率过滤
                                    if width < min_width or height < min_height:
                                        result['passed'] = False
                                        result['reason'] = f'分辨率过低 ({width}x{height} < {min_width}x{min_height})'
                                        return result
                                    
                                except Exception as e:
                                    # 无法从部分数据获取尺寸，跳过分辨率检查
                                    stats['resolution_check_failed'] += 1
                                    pass
                        except Exception as e:
                            # 分辨率检查失败，但不直接过滤掉
                            stats['resolution_check_failed'] += 1
                            pass
                
                return result
                
            except Exception as e:
                # 全局异常，保留图片
                return {
                    'image': image_info,
                    'passed': True,
                    'reason': f'检查异常: {str(e)}',
                    'file_size': None,
                    'width': None,
                    'height': None
                }
        
        # 执行过滤
        start_time = time.time()
        
        if parallel_filter and len(images) > 10:
            # 并行过滤（适用于大量图片）
            self.logger.info(f"使用并行过滤模式，线程数: 5")
            
            with ThreadPoolExecutor(max_workers=5) as executor:
                # 提交任务
                future_to_image = {executor.submit(filter_single_image, img): img for img in images}
                
                processed = 0
                for future in as_completed(future_to_image):
                    try:
                        result = future.result()
                        processed += 1
                        
                        # 显示进度
                        if processed % 50 == 0 or processed == len(images):
                            self.logger.info(f"预过滤进度: {processed}/{len(images)}")
                        
                        if result['passed']:
                            filtered_images.append(result['image'])
                        else:
                            reason_str = str(result.get('reason', ''))
                            if reason_str and '文件' in reason_str:
                                stats['filtered_size'] += 1
                            elif reason_str and '分辨率' in reason_str:
                                stats['filtered_resolution'] += 1
                            
                            # 安全地访问image对象
                            image_obj = result.get('image')
                            filename = getattr(image_obj, 'filename', '未知图片')
                            self.logger.debug(f"预过滤移除: {filename} - {reason_str}")
                        
                    except Exception as e:
                        self.logger.error(f"过滤任务异常: {e}")
                        # 异常情况下保留图片
                        image = future_to_image[future]
                        filtered_images.append(image)
        else:
            # 串行过滤（适用于少量图片）
            self.logger.info(f"使用串行过滤模式")
            
            for i, image in enumerate(images):
                # 显示进度
                if (i + 1) % 50 == 0 or i == len(images) - 1:
                    self.logger.info(f"预过滤进度: {i + 1}/{len(images)}")
                
                result = filter_single_image(image)
                
                if result['passed']:
                    filtered_images.append(result['image'])
                else:
                    reason_str = str(result.get('reason', ''))
                    if reason_str and '文件' in reason_str:
                        stats['filtered_size'] += 1
                    elif reason_str and '分辨率' in reason_str:
                        stats['filtered_resolution'] += 1
                    
                    # 确保image对象是有效的并且有filename属性
                    image_obj = result.get('image')
                    if image_obj and hasattr(image_obj, 'filename'):
                        filename = getattr(image_obj, 'filename', '未知图片')
                        self.logger.debug(f"预过滤移除: {filename} - {reason_str}")
                    else:
                        self.logger.debug(f"预过滤移除: 未知图片 - {reason_str}")
        
        filter_time = time.time() - start_time
        
        # 输出过滤统计
        total_filtered = stats['filtered_size'] + stats['filtered_resolution']
        self.logger.info(f"预过滤完成，耗时: {filter_time:.2f}秒")
        
        if total_filtered > 0:
            self.logger.info(f"移除 {total_filtered} 张图片 (大小不符: {stats['filtered_size']}, 分辨率不符: {stats['filtered_resolution']})")
        
        if stats['size_check_failed'] > 0 or stats['resolution_check_failed'] > 0:
            self.logger.info(f"检查失败: 大小检查 {stats['size_check_failed']} 张, 分辨率检查 {stats['resolution_check_failed']} 张")
        
        self.logger.info(f"最终保留: {len(filtered_images)}/{len(images)} 张图片")
        
        return filtered_images
    
    def _notify_task_status_change(self, task: DownloadTask, old_status: TaskStatus):
        """
        通知任务状态变化
        
        Args:
            task: 任务对象
            old_status: 旧状态
        """
        for callback in self.task_callbacks:
            try:
                callback(task, old_status)
            except Exception as e:
                self.logger.warning(f"任务状态回调异常: {e}")
    
    def get_task(self, task_id: str) -> Optional[DownloadTask]:
        """
        获取任务
        
        Args:
            task_id: 任务ID
            
        Returns:
            任务对象
        """
        with self.lock:
            return self.tasks.get(task_id)
    
    def get_all_tasks(self) -> List[DownloadTask]:
        """
        获取所有任务
        
        Returns:
            任务列表
        """
        with self.lock:
            return list(self.tasks.values())
    
    def cancel_task(self, task_id: str) -> bool:
        """
        取消任务
        
        Args:
            task_id: 任务ID
            
        Returns:
            是否成功
        """
        with self.lock:
            task = self.tasks.get(task_id)
            if not task:
                return False
            
            old_status = task.status
            
            if task.status == TaskStatus.RUNNING:
                # 停止正在运行的任务
                self.download_manager.cancel_download()
                self.running_tasks.discard(task_id)
            
            task.status = TaskStatus.CANCELLED
            task.completed_time = datetime.now()
            
            self._notify_task_status_change(task, old_status)
            
            self.logger.info(f"任务已取消: {task.name}")
            return True
    
    def delete_task(self, task_id: str) -> bool:
        """
        删除任务
        
        Args:
            task_id: 任务ID
            
        Returns:
            是否成功
        """
        # 先取消任务
        self.cancel_task(task_id)
        
        with self.lock:
            if task_id in self.tasks:
                del self.tasks[task_id]
                self.logger.info(f"任务已删除: {task_id}")
                return True
            
        return False
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        获取调度器统计信息
        
        Returns:
            统计信息字典
        """
        with self.lock:
            stats = {
                'total_tasks': len(self.tasks),
                'running_tasks': len(self.running_tasks),
                'pending_tasks': sum(1 for t in self.tasks.values() if t.status == TaskStatus.PENDING),
                'completed_tasks': sum(1 for t in self.tasks.values() if t.status == TaskStatus.COMPLETED),
                'failed_tasks': sum(1 for t in self.tasks.values() if t.status == TaskStatus.FAILED),
                'scheduled_tasks': self.scheduled_tasks.qsize(),
                'total_images': sum(t.total_images for t in self.tasks.values()),
                'downloaded_images': sum(t.downloaded_images for t in self.tasks.values()),
                'failed_images': sum(t.failed_images for t in self.tasks.values())
            }
        
        return stats
