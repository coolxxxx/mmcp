#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
下载管理器模块
负责管理下载任务、速率限制和并发控制
"""

import os
import time
import threading
import requests
import queue
from typing import Dict, List, Any, Optional, Callable, Union
from queue import Queue
from datetime import datetime
from urllib.parse import urlparse

from .rate_limiter import RateLimiter, RateLimitedSession
from ..models.data_models import ImageInfo, DownloadStatus
from ..utils.logger import setup_logger


class DownloadManager:
    """下载管理器，负责管理下载任务和速率限制"""
    
    def __init__(self, config: Dict[str, Any], file_manager: Any):
        """
        初始化下载管理器
        
        Args:
            config: 配置字典
            file_manager: 文件管理器实例
        """
        self.config = config
        self.file_manager = file_manager
        self.logger = setup_logger('downloader')
        
        # 从配置中获取参数
        self.max_threads: int = config.get('max_threads', 5)
        self.timeout: int = config.get('timeout', 30)
        self.retry_times: int = config.get('retry_times', 3)
        self.chunk_size: int = config.get('chunk_size', 8192)
        self.skip_head_check: bool = config.get('skip_head_check', False)
        self.min_retry_delay: int = config.get('min_retry_delay', 1)
        self.max_retry_delay: int = config.get('max_retry_delay', 60)
        
        # 初始化状态变量
        self.is_running: bool = False
        self.stats: Dict[str, Any] = self._create_empty_stats()
        self.download_queue: Queue[ImageInfo] = Queue()
        self.active_downloads: Dict[str, Any] = {}
        self.progress_callbacks: List[Callable[[ImageInfo, int, int], None]] = []
        self.status_lock: threading.Lock = threading.Lock()
        
        # 初始化速率限制器
        from .rate_limiter import RateLimitConfig
        rate_config = RateLimitConfig(
            max_requests_per_second=config.get('base_rate', 5),
            burst_capacity=config.get('max_rate', 15)
        )
        self.rate_limiter: RateLimiter = RateLimiter(rate_config)
        
        # 初始化HTTP会话
        self.session = RateLimitedSession(
            requests.Session(), self.rate_limiter
        )
        
        # 配置会话
        session_config = config.get('session', {})
        if session_config.get('verify_ssl', True):
            self.session.session.verify = True
        else:
            self.session.session.verify = False
            
        # 设置代理
        if 'proxy' in session_config:
            self.session.session.proxies = {'http': session_config['proxy'], 'https': session_config['proxy']}
        
        # 设置请求头
        self.session.session.headers.update({
            'User-Agent': session_config.get('user_agent', 
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
        })
        
        # 初始化线程池执行器
        self.executor: Optional[Any] = None
        self.adaptive_interval: int = config.get('adaptive_interval', 30)
        
        self.logger.info(f"下载管理器初始化完成，最大线程数: {self.max_threads}")

    def _create_empty_stats(self) -> Dict[str, Any]:
        """创建完整的下载统计结构，避免不同入口初始化出不一致字段。"""
        return {
            'total': 0,
            'success': 0,
            'failed': 0,
            'skipped': 0,
            'retry': 0,
            'bytes_downloaded': 0,
            'server_errors': 0
        }

    def add_progress_callback(self, callback: Callable[[ImageInfo, int, int], None]) -> None:
        """添加进度回调函数"""
        self.progress_callbacks.append(callback)

    def start(self) -> None:
        """启动下载管理器"""
        with self.status_lock:
            if self.is_running:
                self.logger.warning("下载管理器已经在运行中")
                return
                
            self.is_running = True
            self.stats = self._create_empty_stats()
            
            # 创建线程池执行器
            try:
                from concurrent.futures import ThreadPoolExecutor
                self.executor = ThreadPoolExecutor(
                    max_workers=self.max_threads,
                    thread_name_prefix='download_worker'
                )
            except ImportError:
                self.logger.error("无法导入 ThreadPoolExecutor，请检查Python版本")
                self.is_running = False
                return
            
            self.logger.info(f"下载管理器启动，线程数: {self.max_threads}")
            
            # 启动工作线程
            for i in range(self.max_threads):
                self.executor.submit(self._download_worker)
            
            # 启动自适应控制
            self._start_adaptive_control()

    def stop(self) -> None:
        """停止下载管理器"""
        with self.status_lock:
            if not self.is_running:
                return
                
            self.is_running = False
            
            # 关闭执行器
            if self.executor:
                self.executor.shutdown(wait=False)
                self.executor = None
            
            # 清空队列
            while not self.download_queue.empty():
                try:
                    self.download_queue.get_nowait()
                except:
                    pass
            
            self.logger.info("下载管理器已停止")

    def add_download_task(self, image_info: ImageInfo) -> None:
        """添加下载任务到队列"""
        self.download_queue.put(image_info)
        with self.status_lock:
            self.stats['total'] += 1

    def get_stats(self) -> Dict[str, Any]:
        """获取下载统计信息"""
        with self.status_lock:
            return self.stats.copy()

    def _download_worker(self) -> None:
        """下载工作线程"""
        while self.is_running:
            try:
                # 从队列获取任务，处理队列空异常
                try:
                    image_info = self.download_queue.get(timeout=1)
                    if image_info is None:
                        continue
                    
                    # 执行下载
                    self._download_image(image_info)
                    
                except queue.Empty:
                    # 队列为空，正常等待
                    continue
                    
            except Exception as e:
                if self.is_running:
                    self.logger.error(f"下载工作线程错误: {e}", exc_info=True)
                time.sleep(1)

    def _download_image(self, image_info: ImageInfo) -> None:
        """下载单个图片"""
        try:
            # 检查文件是否已存在
            file_path = image_info.file_path
            if os.path.exists(file_path):
                file_size = os.path.getsize(file_path)
                if file_size >= image_info.min_file_size:
                    with self.status_lock:
                        self.stats['skipped'] += 1
                    self.logger.info(f"文件已存在，跳过下载: {image_info.filename}")
                    return
            
            # 执行下载
            success = self._download_with_checks(image_info, file_path)
            
            with self.status_lock:
                if success:
                    self.stats['success'] += 1
                else:
                    self.stats['failed'] += 1
                    
        except Exception as e:
            self.logger.error(f"下载图片失败 {image_info.url}: {e}")
            with self.status_lock:
                self.stats['failed'] += 1

    def _should_skip_by_path(self, url: str) -> bool:
        """
        检查是否应该跳过特定路径的文件
        对于包含 'uploadfile/pic/' 的相对路径，当无法获取文件大小时自动跳过
        
        Args:
            url: 文件URL
            
        Returns:
            是否应该跳过该文件
        """
        try:
            from urllib.parse import urlparse
            parsed_url = urlparse(url)
            path = parsed_url.path.lower()
            
            # 检查是否包含需要跳过的路径模式
            skip_patterns = [
                '/uploadfile/pic/',
                '/pic/uploadfile/',
                # 可以添加其他需要跳过的路径模式
            ]
            
            for pattern in skip_patterns:
                if pattern in path:
                    self.logger.debug(f"检测到需要跳过的路径模式: {url} (模式: {pattern})")
                    return True
            
            return False
            
        except Exception as e:
            self.logger.warning(f"路径过滤检查失败 {url}: {e}")
            return False

    def _download_with_checks(self, image_info: ImageInfo, file_path: str) -> bool:
        """带检查的下载实现"""
        for attempt in range(self.retry_times):
            try:
                # 应用速率限制
                self.rate_limiter.acquire()
                
                # 发送HEAD请求获取文件信息（如果启用）
                file_size = 0
                if not self.skip_head_check:
                    try:
                        head_response = self.session.head(
                            image_info.url, 
                            timeout=self.timeout,
                            allow_redirects=True
                        )
                        head_response.raise_for_status()
                        file_size = int(head_response.headers.get('content-length', 0))
                    except Exception as e:
                        self.logger.warning(f"HEAD请求失败 {image_info.url}: {e}")
                
                # 对于特定路径，当无法获取文件大小时自动跳过
                if file_size == 0 and self._should_skip_by_path(image_info.url):
                    self.logger.info(f"无法获取文件大小且路径需要跳过: {image_info.url}")
                    return False
                
                # 执行下载
                response = self.session.get(
                    image_info.url,
                    stream=True,
                    timeout=self.timeout,
                    allow_redirects=True
                )
                response.raise_for_status()
                
                # 获取实际文件大小
                actual_size = int(response.headers.get('content-length', 0))
                if actual_size > 0:
                    file_size = actual_size
                
                # 路径过滤：跳过特定路径下的文件
                if self._should_skip_by_path(image_info.url):
                    self.logger.info(f"跳过特定路径文件: {image_info.url}")
                    return False
                
                # 检查文件大小
                if file_size > 0 and file_size < image_info.min_file_size:
                    self.logger.warning(f"文件大小过小 {image_info.url}: {file_size} < {image_info.min_file_size}")
                    return False
                
                # 创建目录
                os.makedirs(os.path.dirname(file_path), exist_ok=True)
                
                # 下载文件
                downloaded_size = 0
                with open(file_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=self.chunk_size):
                        if chunk:
                            f.write(chunk)
                            downloaded_size += len(chunk)
                            
                            # 通知进度更新（优化回调频率，避免过于频繁）
                            if downloaded_size % max(1024 * 100, self.chunk_size * 10) == 0:  # 每100KB或10个chunk更新一次
                                for callback in self.progress_callbacks:
                                    try:
                                        callback(image_info, downloaded_size, file_size)
                                    except Exception as e:
                                        self.logger.error(f"进度回调错误: {e}")
                
                # 验证下载的文件大小
                actual_downloaded = os.path.getsize(file_path)
                if file_size > 0 and actual_downloaded != file_size:
                    self.logger.warning(f"文件大小不匹配 {image_info.url}: 期望 {file_size}, 实际 {actual_downloaded}")
                    os.remove(file_path)
                    continue
                
                # 更新统计信息
                with self.status_lock:
                    self.stats['bytes_downloaded'] += downloaded_size
                
                self.logger.info(f"下载成功: {image_info.filename} ({downloaded_size} bytes)")
                return True
                
            except requests.exceptions.RequestException as e:
                # 检测502错误和其他服务器错误
                is_server_error = False
                if e.response is not None and hasattr(e.response, 'status_code'):
                    status_code = e.response.status_code
                    if status_code >= 500:
                        is_server_error = True
                        with self.status_lock:
                            self.stats['server_errors'] = self.stats.get('server_errors', 0) + 1
                        self.logger.warning(f"服务器错误 {status_code} {image_info.url} (尝试 {attempt + 1}/{self.retry_times})")
                
                if is_server_error:
                    # 服务器错误时增加重试延迟
                    delay = min(self.min_retry_delay * (2 ** attempt) * 2, self.max_retry_delay * 2)
                else:
                    delay = min(self.min_retry_delay * (2 ** attempt), self.max_retry_delay)
                
                self.logger.error(f"下载失败 {image_info.url} (尝试 {attempt + 1}/{self.retry_times}): {e}")
                
                if attempt < self.retry_times - 1:
                    time.sleep(delay)
                    with self.status_lock:
                        self.stats['retry'] = self.stats.get('retry', 0) + 1
            except Exception as e:
                self.logger.error(f"下载过程中发生错误 {image_info.url}: {e}")
                break
        
        return False

    def _start_adaptive_control(self) -> None:
        """启动自适应控制线程"""
        def control_loop():
            while self.is_running:
                try:
                    time.sleep(self.adaptive_interval)
                    if not self.is_running:
                        break
                        
                    # 计算最优工作线程数
                    optimal_workers = self._calculate_optimal_workers()
                    if optimal_workers != self.max_threads:
                        self._adjust_worker_count(optimal_workers)
                        
                except Exception as e:
                    self.logger.error(f"自适应控制错误: {e}")
                    time.sleep(5)
        
        control_thread = threading.Thread(
            target=control_loop,
            name='adaptive_control',
            daemon=True
        )
        control_thread.start()

    def _calculate_optimal_workers(self) -> int:
        """计算最优工作线程数"""
        # 获取当前统计信息
        stats = self.get_stats()
        total = stats.get('total', 0)
        success = stats.get('success', 0)
        failed = stats.get('failed', 0)
        server_errors = stats.get('server_errors', 0)
        retry_count = stats.get('retry', 0)
        
        if total == 0:
            return self.max_threads
        
        # 计算成功率
        success_rate = success / total if total > 0 else 0
        
        # 计算服务器错误率
        server_error_rate = server_errors / total if total > 0 else 0
        
        # 根据成功率和服务器错误率调整线程数
        if server_error_rate > 0.2:  # 服务器错误率超过20%
            # 服务器错误率高，大幅减少线程数
            new_workers = max(1, self.max_threads // 2)
            self.logger.warning(f"服务器错误率高({server_error_rate:.2f})，大幅减少线程数: {self.max_threads} -> {new_workers}")
        elif success_rate < 0.3:
            # 成功率低，减少线程数
            new_workers = max(1, self.max_threads - 2)
            self.logger.info(f"成功率低({success_rate:.2f})，减少线程数: {self.max_threads} -> {new_workers}")
        elif success_rate < 0.6:
            # 成功率中等，保持当前线程数
            new_workers = self.max_threads
            self.logger.debug(f"成功率中等({success_rate:.2f})，保持线程数: {new_workers}")
        else:
            # 成功率高，谨慎增加线程数
            new_workers = min(self.max_threads + 1, 20)  # 最大20个线程
            self.logger.info(f"成功率高({success_rate:.2f})，增加线程数: {self.max_threads} -> {new_workers}")
        
        return new_workers

    def _adjust_worker_count(self, new_worker_count: int) -> None:
        """调整工作线程数量"""
        if new_worker_count == self.max_threads:
            return
            
        with self.status_lock:
            old_count = self.max_threads
            self.max_threads = new_worker_count
            
            if self.executor:
                # 先关闭旧执行器
                self.executor.shutdown(wait=False)
                
                # 创建新执行器
                from concurrent.futures import ThreadPoolExecutor
                self.executor = ThreadPoolExecutor(
                    max_workers=new_worker_count,
                    thread_name_prefix='download_worker'
                )
                
                # 启动新的工作线程
                for i in range(new_worker_count):
                    self.executor.submit(self._download_worker)
        
        self.logger.info(f"工作线程数已调整: {old_count} -> {new_worker_count}")

    def start_download_batch(self, images: List[ImageInfo]) -> None:
        """
        批量启动下载任务
        
        Args:
            images: 图片信息列表
        """
        self.logger.info(f"开始批量下载 {len(images)} 张图片")
        
        # 确保下载管理器正在运行
        if not self.is_running:
            self.start()
        
        # 添加所有图片到下载队列
        for image_info in images:
            self.add_download_task(image_info)
        
        self.logger.info(f"批量下载任务已添加，总计 {len(images)} 张图片")

    def is_downloading(self) -> bool:
        """
        检查是否正在下载
        
        Returns:
            是否正在下载
        """
        if not self.is_running:
            return False

        with self.status_lock:
            total = self.stats.get('total', 0)
            processed = (
                self.stats.get('success', 0)
                + self.stats.get('failed', 0)
                + self.stats.get('skipped', 0)
            )

        return not self.download_queue.empty() or processed < total

    def get_download_stats(self) -> Dict[str, Any]:
        """
        获取下载统计信息
        
        Returns:
            下载统计信息字典，包含downloaded_images, failed_images, downloaded_size等字段
        """
        stats = self.get_stats()
        return {
            'downloaded_images': stats.get('success', 0),
            'failed_images': stats.get('failed', 0),
            'skipped_images': stats.get('skipped', 0),
            'downloaded_size': stats.get('bytes_downloaded', 0),
            'total_images': stats.get('total', 0)
        }

    def cancel_download(self) -> None:
        """取消当前下载"""
        self.stop()
        self.logger.info("下载已取消")

    def __del__(self) -> None:
        """析构函数，确保资源清理"""
        self.stop()
