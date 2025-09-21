#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
任务验证器模块
用于验证任务合法性，防止重复创建
"""

import os
import hashlib
import logging
from typing import Dict, List, Optional, Set
from urllib.parse import urlparse, parse_qs
import requests
import time

from ..models.data_models import ValidationResult, DownloadTask, TaskStatus
from ..core.file_manager import FileManager
from ..utils.url_utils import UrlUtils
from ..core.rate_limiter import RateLimitedSession, get_global_rate_limiter

class TaskValidator:
    """任务验证器"""
    
    def __init__(self, file_manager: FileManager, existing_tasks: Dict[str, DownloadTask]):
        """
        初始化验证器
        
        Args:
            file_manager: 文件管理器
            existing_tasks: 现有任务字典
        """
        self.file_manager = file_manager
        self.existing_tasks = existing_tasks
        self.logger = logging.getLogger(__name__)
        
        # 创建基础HTTP会话
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        # 使用全局速率限制器包装会话
        rate_limiter = get_global_rate_limiter()
        self.session = RateLimitedSession(self.session, rate_limiter)
        
        # 验证配置
        self.timeout = 10
        self.retry_times = 2
        
    def validate_task(self, url: str, name: Optional[str] = None) -> ValidationResult:
        """
        验证任务合法性
        
        Args:
            url: 任务URL
            name: 任务名称
            
        Returns:
            验证结果
        """
        result = ValidationResult(is_valid=True)
        
        try:
            # 1. 检查URL格式
            if not self._is_valid_url(url):
                result.is_valid = False
                result.reason = "无效的URL格式"
                return result
            
            # 2. 检查网络可达性
            if not self._check_network_accessibility(url):
                result.network_accessible = False
                result.reason = "网络不可达或页面不存在"
                # 网络问题不直接标记为无效，允许用户决定
            
            # 3. 检查目录重复
            directory_name = self._generate_directory_name(url, name)
            if self._check_existing_directory(directory_name):
                result.directory_exists = True
                result.reason = f"目录已存在: {directory_name}"
                
            # 4. 检查任务重复
            if self._check_duplicate_task(url):
                result.task_exists = True
                result.reason = "相同URL的任务已存在"
                
            # 5. 检查页面是否包含图片（可选，耗时较长）
            if result.network_accessible:
                has_images = self._quick_check_images(url)
                result.has_images = has_images
                if not has_images:
                    result.reason = "页面可能不包含图片内容"
            
            # 综合判断
            if result.directory_exists or result.task_exists:
                result.is_valid = False
            elif not result.network_accessible and not result.has_images:
                result.is_valid = False
                result.reason = "页面无法访问且可能不包含图片"
                
        except Exception as e:
            self.logger.error(f"验证任务失败 {url}: {e}")
            result.is_valid = False
            result.reason = f"验证异常: {str(e)}"
        
        return result
    
    def _is_valid_url(self, url: str) -> bool:
        """
        检查URL格式是否有效
        
        Args:
            url: URL字符串
            
        Returns:
            是否有效
        """
        try:
            parsed = urlparse(url)
            return bool(parsed.scheme and parsed.netloc)
        except Exception:
            return False
    
    def _check_network_accessibility(self, url: str) -> bool:
        """
        检查网络可达性
        
        Args:
            url: URL字符串
            
        Returns:
            是否可达
        """
        # 先检查URL格式
        if not self._is_valid_url(url):
            return False
            
        # 对于已知的域名，可以跳过部分检查
        parsed = urlparse(url)
        if parsed.netloc in ('www.example.com', 'example.org'):
            return True
            
        # 使用GET请求代替HEAD，因为有些服务器会拒绝HEAD
        for attempt in range(self.retry_times):
            try:
                response = self.session.get(
                    url, 
                    timeout=self.timeout,
                    stream=True  # 不下载内容
                )
                response.close()  # 立即关闭连接
                return response.status_code < 400
                
            except requests.RequestException as e:
                self.logger.debug(f"网络检查失败 (尝试 {attempt + 1}/{self.retry_times}): {url} - {e}")
                if attempt < self.retry_times - 1:
                    time.sleep(min(2 ** attempt, 5))  # 指数退避，最多5秒
        return False
    
    def _generate_directory_name(self, url: str, name: Optional[str] = None) -> str:
        """
        生成目录名称
        
        Args:
            url: URL字符串
            name: 任务名称
            
        Returns:
            目录名称
        """
        if name:
            return UrlUtils.sanitize_filename(name)
        
        # 从URL提取目录名
        parsed = urlparse(url)
        path = parsed.path.strip('/')
        
        if path:
            # 提取文件名（不带扩展名）
            filename = os.path.splitext(os.path.basename(path))[0]
            if filename:
                return UrlUtils.sanitize_filename(filename)
        
        # 使用域名 + 哈希
        domain = parsed.netloc
        url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
        return f"{domain}_{url_hash}"
    
    def _check_existing_directory(self, directory_name: str) -> bool:
        """
        检查目录是否已存在
        
        Args:
            directory_name: 目录名称
            
        Returns:
            是否存在
        """
        try:
            # 使用pathlib替代os.path，性能更好
            full_path = self.file_manager.base_path / directory_name
            return full_path.is_dir()
        except Exception as e:
            self.logger.debug(f"检查目录失败 {directory_name}: {e}")
            return False
    
    def _check_duplicate_task(self, url: str) -> bool:
        """
        检查是否有重复任务
        
        Args:
            url: URL字符串
            
        Returns:
            是否重复
        """
        # 精确匹配
        for task in self.existing_tasks.values():
            if task.base_url == url:
                return True
        
        # 相似度匹配
        similarity_threshold = 0.9
        for task in self.existing_tasks.values():
            if self._calculate_url_similarity(url, task.base_url) > similarity_threshold:
                return True
        
        return False
    
    def _calculate_url_similarity(self, url1: str, url2: str) -> float:
        """
        计算URL相似度
        
        Args:
            url1: URL1
            url2: URL2
            
        Returns:
            相似度 (0-1)
        """
        try:
            parsed1 = urlparse(url1)
            parsed2 = urlparse(url2)
            
            # 域名必须相同
            if parsed1.netloc != parsed2.netloc:
                return 0.0
            
            path1 = parsed1.path.strip('/')
            path2 = parsed2.path.strip('/')
            
            # 计算路径相似度
            if not path1 or not path2:
                return 0.5
            
            # 简单的字符串相似度
            longer = max(len(path1), len(path2))
            if longer == 0:
                return 1.0
            
            # 计算编辑距离
            distance = self._levenshtein_distance(path1, path2)
            similarity = (longer - distance) / longer
            
            return similarity
            
        except Exception:
            return 0.0
    
    def _levenshtein_distance(self, s1: str, s2: str) -> int:
        """
        计算编辑距离
        
        Args:
            s1: 字符串1
            s2: 字符串2
            
        Returns:
            编辑距离
        """
        if len(s1) < len(s2):
            return self._levenshtein_distance(s2, s1)
        
        if len(s2) == 0:
            return len(s1)
        
        prev_row = range(len(s2) + 1)
        for i, c1 in enumerate(s1):
            curr_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = prev_row[j + 1] + 1
                deletions = curr_row[j] + 1
                substitutions = prev_row[j] + (c1 != c2)
                curr_row.append(min(insertions, deletions, substitutions))
            prev_row = curr_row
        
        return prev_row[-1]
    
    def _quick_check_images(self, url: str) -> bool:
        """
        快速检查页面是否包含图片
        
        Args:
            url: URL字符串
            
        Returns:
            是否包含图片
        """
        try:
            response = self.session.get(url, timeout=self.timeout)
            if response.status_code != 200:
                return False
            
            content = response.text.lower()
            
            # 简单的关键词检查
            image_indicators = [
                '<img',
                '.jpg',
                '.jpeg', 
                '.png',
                '.gif',
                'image/',
                'background-image',
                'src=',
                'data-src='
            ]
            
            found_indicators = sum(1 for indicator in image_indicators if indicator in content)
            return found_indicators >= 2  # 至少包含2个图片相关指标
            
        except Exception as e:
            self.logger.debug(f"快速图片检查失败 {url}: {e}")
            return False
    
    def validate_batch_tasks(self, urls: List[str], 
                           skip_existing: bool = True) -> Dict[str, ValidationResult]:
        """
        批量验证任务
        
        Args:
            urls: URL列表
            skip_existing: 是否跳过已存在的任务
            
        Returns:
            验证结果字典
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed
        import os
        
        results = {}
        url_set = set(urls)  # 去重
        
        # 动态调整线程池大小
        max_workers = min(10, len(url_set), (os.cpu_count() or 1) * 2)
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_url = {
                executor.submit(self.validate_task, url): url 
                for url in url_set
            }
            
            for future in as_completed(future_to_url):
                url = future_to_url[future]
                try:
                    result = future.result()
                    
                    # 根据配置决定是否跳过已存在的任务
                    if skip_existing and (result.directory_exists or result.task_exists):
                        result.is_valid = False
                        result.reason = "跳过已存在的任务"
                    
                    results[url] = result
                except Exception as e:
                    self.logger.error(f"验证任务失败 {url}: {e}")
                    results[url] = ValidationResult(
                        is_valid=False,
                        reason=f"验证异常: {str(e)}"
                    )
        
        return results
    
    def get_validation_statistics(self, results: Dict[str, ValidationResult]) -> Dict:
        """
        获取验证统计信息
        
        Args:
            results: 验证结果字典
            
        Returns:
            统计信息
        """
        total = len(results)
        valid = sum(1 for r in results.values() if r.is_valid)
        duplicate = sum(1 for r in results.values() if r.directory_exists or r.task_exists)
        network_issues = sum(1 for r in results.values() if not r.network_accessible)
        no_images = sum(1 for r in results.values() if not r.has_images)
        
        return {
            'total': total,
            'valid': valid,
            'invalid': total - valid,
            'duplicate': duplicate,
            'network_issues': network_issues,
            'no_images': no_images,
            'validation_rate': valid / total if total > 0 else 0.0
        }