#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量任务创建器模块
协调整个批量任务创建流程
"""

import asyncio
import time
import logging
import re
from typing import List, Dict, Optional, Callable, Set, Any
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

from ..models.data_models import (
    BatchTaskConfig, BatchCreationResult, TaskPreviewInfo, 
    ValidationResult, PageAnalysisResult, DownloadTask
)
from ..core.parser import WebPageParser
from ..core.task_validator import TaskValidator
from ..core.file_manager import FileManager
from ..utils.url_utils import UrlUtils

class BatchTaskCreationError(Exception):
    """批量任务创建异常"""
    pass

class NetworkTimeoutError(BatchTaskCreationError):
    """网络超时异常"""
    pass

class PageAnalysisError(BatchTaskCreationError):
    """页面分析异常"""
    pass

class ValidationError(BatchTaskCreationError):
    """验证异常"""
    pass

class BatchTaskCreator:
    """批量任务创建器"""
    
    def __init__(self, config: Dict[str, Any], scheduler, progress_callback: Optional[Callable[[str, Optional[float]], None]] = None) -> None:
        """
        初始化批量任务创建器
        
        Args:
            config: 配置字典
            scheduler: 任务调度器
            progress_callback: 进度回调函数
        """
        self.config = config
        self.scheduler = scheduler
        self.progress_callback = progress_callback
        self.logger = logging.getLogger(__name__)
        
        # 初始化组件
        self.parser = WebPageParser(config)
        self.file_manager = FileManager(config.get('download_path'))
        self.validator = TaskValidator(self.file_manager, scheduler.tasks)
        
        # 状态管理
        self.is_cancelled = False
        self.current_operation = ""
        
        # 结果缓存
        self._analysis_cache = {}
        
    def create_batch_tasks(self, batch_config: BatchTaskConfig) -> BatchCreationResult:
        """
        创建批量任务
        
        Args:
            batch_config: 批量任务配置
            
        Returns:
            批量创建结果
        """
        self.logger.info(f"开始批量任务创建: {batch_config.main_url}")
        start_time = time.time()
        
        result = BatchCreationResult(
            total_found=0,
            valid_tasks=0,
            duplicate_skipped=0, 
            failed_analysis=0,
            created_tasks=[],
            execution_mode="batch"
        )
        
        try:
            # 重置状态
            self.is_cancelled = False
            self._analysis_cache.clear()
            
            # 步骤1: 分析主页面，提取子页面链接
            self._update_progress("正在分析主页面...")
            try:
                sub_page_urls = self.analyze_main_page(batch_config.main_url, batch_config)
            except Exception as e:
                raise PageAnalysisError(f"主页面分析失败: {str(e)}")
            
            if self.is_cancelled:
                return result
            
            result.total_found = len(sub_page_urls)
            self.logger.info(f"发现 {result.total_found} 个潜在页面")
            
            if result.total_found == 0:
                self.logger.warning("未发现任何子页面")
                return result
            
            # 步骤2: 验证任务有效性
            self._update_progress("正在验证任务有效性...")
            try:
                validation_results = self.validate_tasks(sub_page_urls, batch_config)
            except Exception as e:
                raise ValidationError(f"任务验证失败: {str(e)}")
            
            if self.is_cancelled:
                return result
            
            # 统计验证结果
            for url, validation in validation_results.items():
                if validation.is_valid:
                    result.valid_tasks += 1
                elif validation.directory_exists or validation.task_exists:
                    result.duplicate_skipped += 1
                else:
                    result.failed_analysis += 1
                    result.error_pages.append(url)
            
            self.logger.info(f"验证完成: 有效 {result.valid_tasks}, 重复 {result.duplicate_skipped}, 失败 {result.failed_analysis}")
            
            # 步骤3: 创建有效的任务
            self._update_progress("正在创建任务...")
            valid_urls = [url for url, validation in validation_results.items() if validation.is_valid]
            
            try:
                tasks = self._create_download_tasks(valid_urls, batch_config)
                result.created_tasks = tasks
            except Exception as e:
                self.logger.error(f"创建任务失败: {e}")
                # 即使创建部分失败，也返回已创建的任务
                result.created_tasks = getattr(result, 'created_tasks', [])
            
            elapsed_time = time.time() - start_time if start_time else 0.0
            self.logger.info(f"批量任务创建完成: 创建 {len(result.created_tasks)} 个任务，耗时 {elapsed_time:.2f} 秒")
            
        except BatchTaskCreationError:
            # 重新抛出业务异常
            raise
        except Exception as e:
            self.logger.error(f"批量任务创建失败: {e}")
            # 将未知异常包装为业务异常
            raise BatchTaskCreationError(f"未知错误: {str(e)}")
        
        return result
    
    def analyze_main_page(self, main_url: str, config: BatchTaskConfig) -> List[str]:
        """分析主页面（优化版）"""
        self.current_operation = "分析主页面"
        sub_pages = []
        
        try:
            self.logger.info(f"开始分析主页面: {main_url}")
            
            # 使用快速解析模式（如果配置）
            if hasattr(config, 'fast_mode') and config.fast_mode:
                self.parser.config.set('image_filters.quick_parse', True)
            
            # 使用现有的解析器功能
            page_info = self.parser.parse_page(main_url, max_depth=1)
            
            if not page_info.parsed:
                self.logger.error(f"主页面解析失败: {page_info.error_message}")
                return []
            
            # 获取子页面链接
            sub_pages = page_info.sub_pages.copy()
            
            # 如果子页面数量不足，尝试智能生成
            if len(sub_pages) < config.max_pages // 2:
                self.logger.info("子页面数量较少，尝试智能生成更多页面")
                generated_pages = self._generate_smart_adjacent_pages([main_url] + sub_pages[:5])
                
                # 快速验证生成的页面（减少网络请求）
                validated_pages = self._quick_validate_pages(generated_pages, fast_mode=getattr(config, 'fast_mode', False))
                sub_pages.extend(validated_pages)
            
            # 限制页面数量
            if len(sub_pages) > config.max_pages:
                sub_pages = sub_pages[:config.max_pages]
                self.logger.info(f"限制页面数量为 {config.max_pages}")
            
            self.logger.info(f"主页面分析完成: 找到 {len(sub_pages)} 个子页面")
            
        except Exception as e:
            self.logger.error(f"分析主页面失败: {e}")
            raise
        
        return sub_pages
        """
        分析主页面，提取子页面链接
        
        Args:
            main_url: 主页面URL
            config: 配置对象
            
        Returns:
            子页面URL列表
        """
        self.current_operation = "分析主页面"
        sub_pages = []
        
        try:
            self.logger.info(f"开始分析主页面: {main_url}")
            
            # 使用现有的解析器功能
            page_info = self.parser.parse_page(main_url, max_depth=1)
            
            if not page_info.parsed:
                self.logger.error(f"主页面解析失败: {page_info.error_message}")
                return []
            
            # 获取子页面链接
            sub_pages = page_info.sub_pages.copy()
            self.logger.info(f"从页面解析中提取到 {len(sub_pages)} 个子页面")
            
            # 如果子页面数量不足，尝试智能生成（但只在基础URL有效时才进行）
            if len(sub_pages) < config.max_pages // 2:
                # 检查基础URL是否适合用于生成相似页面
                if self._is_valid_base_url_for_generation(main_url):
                    self.logger.info("子页面数量较少，尝试智能生成更多页面")
                    generated_pages = self._generate_smart_adjacent_pages([main_url] + sub_pages[:5])
                    
                    # 验证生成的页面
                    validated_pages = self._quick_validate_pages(generated_pages)
                    sub_pages.extend(validated_pages)
                    self.logger.info(f"智能生成添加了 {len(validated_pages)} 个页面")
                else:
                    self.logger.warning(f"基础URL为广告链接或不适合生成相似页面，跳过智能生成: {main_url}")
                    self.logger.info("建议检查输入的URL是否为有效的图片页面，而非广告链接")
            
            # 限制页面数量
            if len(sub_pages) > config.max_pages:
                sub_pages = sub_pages[:config.max_pages]
                self.logger.info(f"限制页面数量为 {config.max_pages}")
            
            self.logger.info(f"主页面分析完成: 找到 {len(sub_pages)} 个子页面")
            
        except Exception as e:
            self.logger.error(f"分析主页面失败: {e}")
            raise
        
        return sub_pages
    
    def validate_tasks(self, urls: List[str], config: BatchTaskConfig) -> Dict[str, ValidationResult]:
        """
        验证任务列表
        
        Args:
            urls: URL列表
            config: 配置对象
            
        Returns:
            验证结果字典
        """
        self.current_operation = "验证任务"
        
        # 批量验证
        results = self.validator.validate_batch_tasks(urls, config.skip_existing)
        
        # 记录统计信息
        stats = self.validator.get_validation_statistics(results)
        self.logger.info(f"验证统计: {stats}")
        
        return results
    
    def preview_tasks(self, validation_results: Dict[str, ValidationResult]) -> List[TaskPreviewInfo]:
        """
        生成任务预览信息
        
        Args:
            validation_results: 验证结果
            
        Returns:
            预览信息列表
        """
        preview_list = []
        
        for url, validation in validation_results.items():
            # 生成目录名
            directory_name = self.validator._generate_directory_name(url)
            
            # 确定状态
            if validation.is_valid:
                status = "新建"
            elif validation.directory_exists:
                status = "目录已存在"
            elif validation.task_exists:
                status = "任务已存在"
            else:
                status = "无效"
            
            # 预估图片数（简单估算）
            estimated_images = 50 if validation.has_images else 0
            estimated_size = "约50MB" if validation.has_images else "未知"
            
            preview_info = TaskPreviewInfo(
                url=url,
                estimated_images=estimated_images,
                estimated_size=estimated_size,
                directory_name=directory_name,
                status=status,
                selected=validation.is_valid,  # 默认选择有效的任务
                error_message=validation.reason if not validation.is_valid else None
            )
            
            preview_list.append(preview_info)
        
        return preview_list
    
    def _create_download_tasks(self, urls: List[str], config: BatchTaskConfig) -> List[DownloadTask]:
        """
        创建下载任务
        
        Args:
            urls: URL列表
            config: 配置对象
            
        Returns:
            任务列表
        """
        tasks = []
        
        for i, url in enumerate(urls):
            if self.is_cancelled:
                break
                
            try:
                # 使用与单个任务相同的目录命名逻辑
                directory_name = self.validator._generate_directory_name(url)
                
                # 创建任务，使用统一的目录命名（不添加"批量"前缀）
                task = DownloadTask(
                    name=directory_name,  # 直接使用目录名作为任务名
                    base_url=url,
                    download_path=str(self.file_manager.base_path),
                    max_depth=1,  # 批量任务通常使用较浅的深度
                    url_patterns=[],
                    scheduled_time=config.scheduled_time if hasattr(config, 'scheduled_time') else None
                )
                
                tasks.append(task)
                
                # 更新进度
                if self.progress_callback:
                    progress = (i + 1) / len(urls) * 100
                    self.progress_callback(f"创建任务 {i+1}/{len(urls)}", progress)
                    
            except Exception as e:
                self.logger.error(f"创建任务失败 {url}: {e}")
                continue
        
        return tasks
    
    def _generate_smart_adjacent_pages(self, base_pages: List[str]) -> List[str]:
        """
        基于现有页面智能生成相邻页面
        
        Args:
            base_pages: 基础页面列表
            
        Returns:
            生成的页面列表
        """
        generated_pages = []
        seen_urls = set()
        
        for base_url in base_pages[:3]:  # 只基于前3个页面生成
            try:
                # 首先检查URL是否为有效的图片页面URL，避免处理广告链接
                if not self._is_valid_base_url_for_generation(base_url):
                    self.logger.debug(f"跳过无效的基础URL生成: {base_url}")
                    continue
                
                # 使用现有解析器的生成逻辑
                similar_pages = self.parser._generate_similar_pages(base_url, count=20)
                
                for page in similar_pages:
                    if page not in seen_urls:
                        generated_pages.append(page)
                        seen_urls.add(page)
                        
            except Exception as e:
                self.logger.warning(f"生成相邻页面失败 {base_url}: {e}")
                continue
        
        return generated_pages
    
    def _is_valid_base_url_for_generation(self, url: str) -> bool:
        """
        检查URL是否适合用于生成相似页面
        排除广告链接和无效URL
        
        Args:
            url: 待检查的URL
            
        Returns:
            是否为有效的基础URL
        """
        try:
            from urllib.parse import urlparse
            
            parsed = urlparse(url)
            
            # 排除已知的广告域名
            ad_domains = [
                'a1.876512.xyz',
                'a2.876512.xyz', 
                'a3.876512.xyz',
                '876512.xyz',
                'ad.', 'ads.', 'banner.', 'promo.', 'sponsor.'
            ]
            
            if any(ad_domain in parsed.netloc for ad_domain in ad_domains):
                return False
            
            # 检查是否为HTML页面
            path = parsed.path.lower()
            html_exts = ['.html', '.htm', '.php', '.asp', '.aspx', '.jsp']
            if not any(path.endswith(ext) for ext in html_exts):
                return False
            
            # 检查是否为图片相关的页面
            image_keywords = ['xiuren', 'tuigirl', 'legbaby', 'huayang', 'youwu', 'xgyw', 'missleg']
            if any(keyword in path for keyword in image_keywords):
                return True
            
            # 检查是否包含数字（通常是图片页面）
            if re.search(r'\d+', path):
                return True
            
            return False
            
        except Exception:
            return False
    
    def _quick_validate_pages(self, urls: List[str], fast_mode: bool = False) -> List[str]:
        """快速验证页面（优化版）"""
        validated_urls = []
        
        # 限制验证数量，避免过多网络请求
        max_check = 50 if fast_mode else 30
        urls_to_check = urls[:max_check]
        
        def check_single_url(url):
            try:
                # 快速模式：仅检查URL格式
                if fast_mode:
                    return url if UrlUtils.is_valid_url(url) else None
                
                # 正常模式：发送HEAD请求验证
                response = self.parser.session.head(url, timeout=5)
                return url if response.status_code == 200 else None
            except:
                return None
        
        # 并发验证 - 动态调整并发数，确保max_workers至少为1
        import os
        cpu_count = os.cpu_count() or 4
        max_workers = max(1, min(12, len(urls_to_check), cpu_count * 3))
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_url = {executor.submit(check_single_url, url): url for url in urls_to_check}
            
            for future in as_completed(future_to_url):
                result = future.result()
                if result:
                    validated_urls.append(result)
        
        self.logger.info(f"快速验证完成: {len(validated_urls)}/{len(urls_to_check)} 个页面有效")
        
        # 如果验证的页面太少，添加一些未验证的页面
        if len(validated_urls) < 10 and len(urls) > len(urls_to_check):
            remaining_urls = urls[len(urls_to_check):len(urls_to_check) + 20]
            validated_urls.extend(remaining_urls)
        
        return validated_urls
        """
        快速验证页面是否存在
        
        Args:
            urls: URL列表
            
        Returns:
            验证存在的URL列表
        """
        validated_urls = []
        
        # 限制验证数量，避免过多网络请求
        urls_to_check = urls[:30]
        
        def check_single_url(url):
            try:
                response = self.parser.session.head(url, timeout=5)
                return url if response.status_code == 200 else None
            except:
                return None
        
        # 并发验证 - 动态调整并发数
        import os
        cpu_count = os.cpu_count() or 4
        max_workers = min(8, len(urls_to_check), cpu_count * 2)
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_url = {executor.submit(check_single_url, url): url for url in urls_to_check}
            
            for future in as_completed(future_to_url):
                result = future.result()
                if result:
                    validated_urls.append(result)
        
        self.logger.info(f"快速验证完成: {len(validated_urls)}/{len(urls_to_check)} 个页面有效")
        
        # 如果验证的页面太少，添加一些未验证的页面
        if len(validated_urls) < 10 and len(urls) > len(urls_to_check):
            remaining_urls = urls[len(urls_to_check):len(urls_to_check) + 20]
            validated_urls.extend(remaining_urls)
        
        return validated_urls
    
    def _update_progress(self, message: str, progress: Optional[float] = None):
        """
        更新进度
        
        Args:
            message: 进度消息
            progress: 进度百分比
        """
        self.current_operation = message
        self.logger.info(message)
        
        if self.progress_callback:
            self.progress_callback(message, progress)
    
    def cancel_operation(self):
        """取消当前操作"""
        self.is_cancelled = True
        self.logger.info("批量任务创建已取消")
    
    def get_current_status(self) -> Dict[str, Any]:
        """
        获取当前状态
        
        Returns:
            状态字典
        """
        return {
            'current_operation': self.current_operation,
            'is_cancelled': self.is_cancelled,
            'cache_size': len(self._analysis_cache)
        }