#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
增强下载管理器模块
提供实时进度回调和精确状态跟踪
"""

import os
import time
import threading
import requests
from typing import Dict, List, Any, Optional, Callable, Union
from datetime import datetime
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed

from .downloader import DownloadManager
from .rate_limiter import RateLimiter, RateLimitedSession, RateLimitConfig
from ..models.data_models import ImageInfo, DownloadStatus
from ..utils.logger import setup_logger


class EnhancedDownloadManager(DownloadManager):
    """增强的下载管理器，提供实时进度跟踪"""
    
    def __init__(self, config: Dict[str, Any], file_manager: Any):
        """初始化增强下载管理器"""
        super().__init__(config, file_manager)
        
        # 实时回调函数
        self.progress_callbacks: List[Callable[[ImageInfo, int, int], None]] = []
        self.status_callbacks: List[Callable[[ImageInfo, DownloadStatus, DownloadStatus], None]] = []
        
        # 实时状态跟踪
        self.download_states: Dict[str, Dict[str, Any]] = {}
        self.state_lock = threading.Lock()
        
        self.logger.info("增强下载管理器初始化完成")
    
    def add_progress_callback(self, callback: Callable[[ImageInfo, int, int], None]) -> None:
        """添加进度回调函数"""
        self.progress_callbacks.append(callback)
        self.logger.debug(f"添加进度回调函数，当前回调数量: {len(self.progress_callbacks)}")
    
    def add_status_callback(self, callback: Callable[[ImageInfo, DownloadStatus, DownloadStatus], None]) -> None:
        """添加状态回调函数"""
        self.status_callbacks.append(callback)
        self.logger.debug(f"添加状态回调函数，当前回调数量: {len(self.status_callbacks)}")
    
    def update_image_status(self, image_info: ImageInfo, new_status: DownloadStatus) -> None:
        """更新图片状态并触发回调"""
        old_status = image_info.status
        image_info.status = new_status
        
        # 更新内部状态跟踪
        with self.state_lock:
            if image_info.url not in self.download_states:
                self.download_states[image_info.url] = {}
            
            self.download_states[image_info.url].update({
                'status': new_status,
                'last_update': datetime.now(),
                'image_info': image_info
            })
        
        # 触发状态回调
        for callback in self.status_callbacks:
            try:
                callback(image_info, old_status, new_status)
            except Exception as e:
                self.logger.error(f"状态回调执行失败: {e}")
    
    def notify_progress(self, image_info: ImageInfo, downloaded: int, total: int) -> None:
        """通知下载进度"""
        # 更新内部状态
        with self.state_lock:
            if image_info.url not in self.download_states:
                self.download_states[image_info.url] = {}
            
            self.download_states[image_info.url].update({
                'downloaded': downloaded,
                'total': total,
                'progress': (downloaded / total * 100) if total > 0 else 0,
                'last_update': datetime.now()
            })
        
        # 触发进度回调
        for callback in self.progress_callbacks:
            try:
                callback(image_info, downloaded, total)
            except Exception as e:
                self.logger.error(f"进度回调执行失败: {e}")
    
    def _resolve_local_path(self, image_info: ImageInfo) -> str:
        """解析本地保存路径，优先使用模型的 file_path 字段"""
        fp = getattr(image_info, 'file_path', None)
        if fp:
            return fp
        filename = getattr(image_info, 'filename', 'unknown_file')
        base_dir = getattr(self.file_manager, 'download_path', None) or getattr(self.file_manager, 'base_path', '.')
        return os.path.join(str(base_dir), filename)

    def download_single_image(self, image_info: ImageInfo) -> bool:
        """下载单个图片（增强版本）"""
        try:
            # 更新状态为下载中
            self.update_image_status(image_info, DownloadStatus.DOWNLOADING)
            
            # 检查文件是否已存在
            local_path = self._resolve_local_path(image_info)
                
            if os.path.exists(local_path):
                file_size = os.path.getsize(local_path)
                if file_size > 0:
                    filename = getattr(image_info, 'filename', 'unknown_file')
                    self.logger.info(f"文件已存在，跳过下载: {filename}")
                    # 标记跳过并实时同步UI为100%
                    self.stats['skipped'] = self.stats.get('skipped', 0) + 1
                    self.update_image_status(image_info, DownloadStatus.COMPLETED)
                    self.notify_progress(image_info, file_size, file_size)
                    return True
            
            # 创建目录
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            
            # 开始下载
            response = self.session.get(
                image_info.url,
                timeout=self.timeout,
                stream=True
            )
            response.raise_for_status()
            
            # 获取文件大小
            total_size = int(response.headers.get('content-length', 0))
            downloaded_size = 0
            
            # 写入文件并实时更新进度
            with open(local_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=self.chunk_size):
                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)
                        
                        # 实时通知进度
                        self.notify_progress(image_info, downloaded_size, total_size)
            
            # 验证下载完整性
            filename = getattr(image_info, 'filename', 'unknown_file')
            if total_size > 0 and downloaded_size != total_size:
                self.logger.warning(f"下载大小不匹配: {filename}, 期望: {total_size}, 实际: {downloaded_size}")
            
            # 更新状态为完成
            self.update_image_status(image_info, DownloadStatus.COMPLETED)
            self.stats['success'] += 1
            self.stats['bytes_downloaded'] += downloaded_size
            
            self.logger.info(f"下载完成: {filename}")
            return True
            
        except requests.exceptions.RequestException as e:
            filename = getattr(image_info, 'filename', 'unknown_file')
            self.logger.error(f"下载失败 {filename}: {e}")
            self.update_image_status(image_info, DownloadStatus.FAILED)
            self.stats['failed'] += 1
            return False
            
        except Exception as e:
            filename = getattr(image_info, 'filename', 'unknown_file')
            self.logger.error(f"下载异常 {filename}: {e}")
            self.update_image_status(image_info, DownloadStatus.FAILED)
            self.stats['failed'] += 1
            return False
    
    def _dedupe_images(self, images: List[ImageInfo]) -> List[ImageInfo]:
        """对图片列表做去重，优先按文件名、其次按URL"""
        seen_names = set()
        seen_urls = set()
        result: List[ImageInfo] = []
        for img in images:
            name = getattr(img, 'filename', None)
            url = getattr(img, 'url', None)
            key_name = name.lower() if isinstance(name, str) else None
            key_url = url
            if key_name:
                if key_name in seen_names:
                    continue
                seen_names.add(key_name)
                result.append(img)
            elif key_url:
                if key_url in seen_urls:
                    continue
                seen_urls.add(key_url)
                result.append(img)
            else:
                # 无法识别，保留以免误删
                result.append(img)
        return result

    def download_images(self, images: List[ImageInfo]) -> Dict[str, Any]:
        """批量下载图片（增强版本）"""
        if not images:
            return self.get_stats()
        
        # 任务级兜底去重（即使调度器未去重）
        original_count = len(images)
        images = self._dedupe_images(images)
        if len(images) != original_count:
            self.logger.info(f"发现重复条目，已从 {original_count} 去重到 {len(images)}")
        
        self.logger.info(f"开始批量下载 {len(images)} 个图片")
        self.is_running = True
        
        # 重置统计
        self.stats.update({
            'total': len(images),
            'success': 0,
            'failed': 0,
            'skipped': 0,
            'bytes_downloaded': 0
        })
        
        # 初始化所有图片状态
        for image in images:
            self.update_image_status(image, DownloadStatus.WAITING)
        
        # 使用线程池下载
        with ThreadPoolExecutor(max_workers=self.max_threads) as executor:
            # 提交所有下载任务（过滤已存在的文件由 download_single_image 内部处理）
            future_to_image = {
                executor.submit(self.download_single_image, image): image 
                for image in images
            }
            
            # 处理完成的任务
            for future in as_completed(future_to_image):
                if not self.is_running:
                    break
                    
                image = future_to_image[future]
                try:
                    success = future.result()
                    if success:
                        self.logger.debug(f"图片下载成功: {image.filename}")
                    else:
                        self.logger.debug(f"图片下载失败: {image.filename}")
                except Exception as e:
                    self.logger.error(f"处理下载结果时出错: {e}")
                    self.update_image_status(image, DownloadStatus.FAILED)
        
        self.is_running = False
        self.logger.info(f"批量下载完成，成功: {self.stats['success']}, 失败: {self.stats['failed']}")
        
        return self.get_stats()
    
    def get_image_state(self, url: str) -> Optional[Dict[str, Any]]:
        """获取图片的实时状态"""
        with self.state_lock:
            return self.download_states.get(url)
    
    def get_all_states(self) -> Dict[str, Dict[str, Any]]:
        """获取所有图片的实时状态"""
        with self.state_lock:
            return self.download_states.copy()
    
    def start_download_batch(self, images: List[ImageInfo]) -> None:
        """与基类兼容的批量启动接口，包含去重与统计"""
        try:
            if not images:
                return
            # 去重
            original = len(images)
            images = self._dedupe_images(images)
            if len(images) != original:
                self.logger.info(f"[batch] 去重: {original} -> {len(images)}")
            # 统计初始化与下载
            self.download_images(images)
        except Exception as e:
            self.logger.error(f"批量下载启动失败: {e}")

    def stop(self) -> None:
        """停止下载管理器"""
        super().stop()
        
        # 清理状态
        with self.state_lock:
            self.download_states.clear()
        
        self.logger.info("增强下载管理器已停止")