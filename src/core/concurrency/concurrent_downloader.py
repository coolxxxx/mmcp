"""
并发下载器
提供高性能的并发下载功能
"""

import asyncio
import aiohttp
import aiofiles
import time
import hashlib
from typing import Dict, List, Any, Optional, Callable, Tuple
from dataclasses import dataclass
from enum import Enum
import logging
from pathlib import Path
import ssl
from urllib.parse import urlparse


class DownloadStatus(Enum):
    """下载状态"""
    PENDING = "pending"
    DOWNLOADING = "downloading"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class DownloadTask:
    """下载任务"""
    url: str
    file_path: str
    headers: Optional[Dict[str, str]] = None
    timeout: int = 30
    max_retries: int = 3
    chunk_size: int = 8192
    verify_ssl: bool = True
    
    # 状态信息
    status: DownloadStatus = DownloadStatus.PENDING
    file_size: Optional[int] = None
    downloaded_size: int = 0
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    
    @property
    def progress(self) -> float:
        """下载进度百分比"""
        if not self.file_size or self.file_size == 0:
            return 0.0
        return min(100.0, (self.downloaded_size / self.file_size) * 100)
    
    @property
    def speed(self) -> float:
        """下载速度 (bytes/second)"""
        if not self.start_time or self.downloaded_size == 0:
            return 0.0
        
        elapsed = time.time() - self.start_time
        if elapsed == 0:
            return 0.0
        
        return self.downloaded_size / elapsed
    
    @property
    def eta(self) -> Optional[float]:
        """预计剩余时间 (seconds)"""
        if not self.file_size or self.speed == 0:
            return None
        
        remaining = self.file_size - self.downloaded_size
        return remaining / self.speed


class ConcurrentDownloader:
    """并发下载器"""
    
    def __init__(self, max_concurrent: int = 10, max_connections: int = 100,
                 connector_limit: int = 30, timeout: int = 30):
        """
        初始化并发下载器
        
        Args:
            max_concurrent: 最大并发下载数
            max_connections: 最大连接数
            connector_limit: 连接器限制
            timeout: 超时时间
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self.max_concurrent = max_concurrent
        self.timeout = timeout
        
        # 创建SSL上下文
        self.ssl_context = ssl.create_default_context()
        self.ssl_context.check_hostname = False
        self.ssl_context.verify_mode = ssl.CERT_NONE
        
        # 创建连接器
        self.connector = aiohttp.TCPConnector(
            limit=max_connections,
            limit_per_host=connector_limit,
            ssl=self.ssl_context,
            enable_cleanup_closed=True
        )
        
        # HTTP会话
        self.session: Optional[aiohttp.ClientSession] = None
        
        # 任务管理
        self.tasks: Dict[str, DownloadTask] = {}
        self.active_downloads: Dict[str, asyncio.Task] = {}
        
        # 信号量控制并发
        self.semaphore = asyncio.Semaphore(max_concurrent)
        
        # 统计信息
        self.stats = {
            'total_downloads': 0,
            'successful_downloads': 0,
            'failed_downloads': 0,
            'total_bytes': 0,
            'total_time': 0.0,
            'average_speed': 0.0
        }
        
        # 回调函数
        self.progress_callbacks: List[Callable[[str, DownloadTask], None]] = []
        self.completion_callbacks: List[Callable[[str, DownloadTask], None]] = []
        self.error_callbacks: List[Callable[[str, DownloadTask, Exception], None]] = []
        
        self.logger.info(f"并发下载器初始化完成，最大并发数: {max_concurrent}")
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self._ensure_session()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.close()
    
    async def _ensure_session(self):
        """确保HTTP会话存在"""
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            self.session = aiohttp.ClientSession(
                connector=self.connector,
                timeout=timeout,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
            )
    
    def add_progress_callback(self, callback: Callable[[str, DownloadTask], None]):
        """添加进度回调"""
        self.progress_callbacks.append(callback)
    
    def add_completion_callback(self, callback: Callable[[str, DownloadTask], None]):
        """添加完成回调"""
        self.completion_callbacks.append(callback)
    
    def add_error_callback(self, callback: Callable[[str, DownloadTask, Exception], None]):
        """添加错误回调"""
        self.error_callbacks.append(callback)
    
    async def download(self, url: str, file_path: str, **kwargs) -> str:
        """
        下载单个文件
        
        Args:
            url: 下载URL
            file_path: 保存路径
            **kwargs: 其他参数
            
        Returns:
            任务ID
        """
        # 生成任务ID
        task_id = hashlib.md5(f"{url}_{file_path}_{time.time()}".encode()).hexdigest()
        
        # 创建下载任务
        task = DownloadTask(url=url, file_path=file_path, **kwargs)
        self.tasks[task_id] = task
        
        # 启动下载
        download_coro = self._download_file(task_id, task)
        self.active_downloads[task_id] = asyncio.create_task(download_coro)
        
        return task_id
    
    async def download_batch(self, downloads: List[Tuple[str, str]], **kwargs) -> List[str]:
        """
        批量下载文件
        
        Args:
            downloads: (url, file_path) 元组列表
            **kwargs: 其他参数
            
        Returns:
            任务ID列表
        """
        task_ids = []
        
        for url, file_path in downloads:
            task_id = await self.download(url, file_path, **kwargs)
            task_ids.append(task_id)
        
        return task_ids
    
    async def _download_file(self, task_id: str, task: DownloadTask):
        """
        下载文件的核心逻辑
        
        Args:
            task_id: 任务ID
            task: 下载任务
        """
        async with self.semaphore:
            await self._ensure_session()
            
            task.status = DownloadStatus.DOWNLOADING
            task.start_time = time.time()
            
            try:
                # 创建目录
                Path(task.file_path).parent.mkdir(parents=True, exist_ok=True)
                
                # 执行下载
                await self._perform_download(task)
                
                # 下载完成
                task.status = DownloadStatus.COMPLETED
                task.end_time = time.time()
                
                # 更新统计
                self.stats['successful_downloads'] += 1
                self.stats['total_bytes'] += task.downloaded_size
                if task.start_time and task.end_time:
                    self.stats['total_time'] += task.end_time - task.start_time
                
                # 触发完成回调
                for callback in self.completion_callbacks:
                    try:
                        callback(task_id, task)
                    except Exception as e:
                        self.logger.warning(f"完成回调执行失败: {str(e)}")
                
                self.logger.info(f"文件下载完成: {task.file_path}")
                
            except Exception as e:
                task.status = DownloadStatus.FAILED
                task.error_message = str(e)
                task.end_time = time.time()
                
                self.stats['failed_downloads'] += 1
                
                # 触发错误回调
                for callback in self.error_callbacks:
                    try:
                        callback(task_id, task, e)
                    except Exception as callback_error:
                        self.logger.warning(f"错误回调执行失败: {str(callback_error)}")
                
                self.logger.error(f"文件下载失败: {task.file_path}, 错误: {str(e)}")
                raise
            
            finally:
                # 清理活动下载
                if task_id in self.active_downloads:
                    del self.active_downloads[task_id]
                
                # 更新总下载数
                self.stats['total_downloads'] += 1
                
                # 计算平均速度
                if self.stats['total_time'] > 0:
                    self.stats['average_speed'] = self.stats['total_bytes'] / self.stats['total_time']
    
    async def _perform_download(self, task: DownloadTask):
        """
        执行下载
        
        Args:
            task: 下载任务
        """
        for attempt in range(task.max_retries + 1):
            try:
                task.retry_count = attempt
                
                # 发送HTTP请求
                headers = task.headers or {}
                
                async with self.session.get(task.url, headers=headers) as response:
                    response.raise_for_status()
                    
                    # 获取文件大小
                    task.file_size = int(response.headers.get('content-length', 0))
                    
                    # 下载文件
                    async with aiofiles.open(task.file_path, 'wb') as file:
                        async for chunk in response.content.iter_chunked(task.chunk_size):
                            await file.write(chunk)
                            task.downloaded_size += len(chunk)
                            
                            # 触发进度回调
                            for callback in self.progress_callbacks:
                                try:
                                    callback(task.url, task)
                                except Exception as e:
                                    self.logger.warning(f"进度回调执行失败: {str(e)}")
                
                # 下载成功，退出重试循环
                break
                
            except Exception as e:
                if attempt == task.max_retries:
                    # 最后一次重试失败
                    raise e
                
                # 等待后重试
                wait_time = 2 ** attempt  # 指数退避
                self.logger.warning(f"下载失败，{wait_time}秒后重试 (第{attempt + 1}次): {str(e)}")
                await asyncio.sleep(wait_time)
                
                # 重置下载大小
                task.downloaded_size = 0
    
    async def wait_for_completion(self, task_ids: Optional[List[str]] = None):
        """
        等待下载完成
        
        Args:
            task_ids: 要等待的任务ID列表，None表示等待所有任务
        """
        if task_ids is None:
            tasks_to_wait = list(self.active_downloads.values())
        else:
            tasks_to_wait = [self.active_downloads[tid] for tid in task_ids 
                           if tid in self.active_downloads]
        
        if tasks_to_wait:
            await asyncio.gather(*tasks_to_wait, return_exceptions=True)
    
    def cancel_download(self, task_id: str) -> bool:
        """
        取消下载
        
        Args:
            task_id: 任务ID
            
        Returns:
            是否成功取消
        """
        if task_id in self.active_downloads:
            task = self.active_downloads[task_id]
            task.cancel()
            
            if task_id in self.tasks:
                self.tasks[task_id].status = DownloadStatus.CANCELLED
            
            return True
        
        return False
    
    def cancel_all_downloads(self):
        """取消所有下载"""
        for task_id in list(self.active_downloads.keys()):
            self.cancel_download(task_id)
    
    def get_task_status(self, task_id: str) -> Optional[DownloadTask]:
        """
        获取任务状态
        
        Args:
            task_id: 任务ID
            
        Returns:
            下载任务对象
        """
        return self.tasks.get(task_id)
    
    def get_all_tasks(self) -> Dict[str, DownloadTask]:
        """获取所有任务"""
        return self.tasks.copy()
    
    def get_active_downloads(self) -> List[str]:
        """获取活动下载列表"""
        return list(self.active_downloads.keys())
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        stats = self.stats.copy()
        stats.update({
            'active_downloads': len(self.active_downloads),
            'total_tasks': len(self.tasks),
            'success_rate': (
                self.stats['successful_downloads'] / max(1, self.stats['total_downloads'])
            ) * 100
        })
        return stats
    
    def clear_completed_tasks(self):
        """清理已完成的任务"""
        completed_tasks = [
            task_id for task_id, task in self.tasks.items()
            if task.status in [DownloadStatus.COMPLETED, DownloadStatus.FAILED, DownloadStatus.CANCELLED]
            and task_id not in self.active_downloads
        ]
        
        for task_id in completed_tasks:
            del self.tasks[task_id]
        
        self.logger.info(f"清理了 {len(completed_tasks)} 个已完成的任务")
    
    async def close(self):
        """关闭下载器"""
        # 取消所有活动下载
        self.cancel_all_downloads()
        
        # 等待所有任务完成
        if self.active_downloads:
            await asyncio.gather(*self.active_downloads.values(), return_exceptions=True)
        
        # 关闭HTTP会话
        if self.session and not self.session.closed:
            await self.session.close()
        
        # 关闭连接器
        if self.connector and not self.connector.closed:
            await self.connector.close()
        
        self.logger.info("并发下载器已关闭")


# 便捷函数
async def download_files(downloads: List[Tuple[str, str]], max_concurrent: int = 10, **kwargs) -> Dict[str, DownloadTask]:
    """
    便捷的批量下载函数
    
    Args:
        downloads: (url, file_path) 元组列表
        max_concurrent: 最大并发数
        **kwargs: 其他参数
        
    Returns:
        任务结果字典
    """
    async with ConcurrentDownloader(max_concurrent=max_concurrent) as downloader:
        task_ids = await downloader.download_batch(downloads, **kwargs)
        await downloader.wait_for_completion(task_ids)
        
        return {task_id: downloader.get_task_status(task_id) for task_id in task_ids}