"""
解析器协调器
负责协调各个解析器的工作
"""

from typing import List, Dict, Any, Optional, Union
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

from .base_parser import BaseParser, ParseResult, ImageInfo, SubPageInfo, ParserMixin
from .page_content_parser import PageContentParser
from .image_extractor import ImageExtractor
from .subpage_extractor import SubPageExtractor
from .image_filter import ImageFilter
from .parser_exceptions import ParserError, CoordinatorError
from .parser_config import ParserConfig


class ParserCoordinator(BaseParser, ParserMixin):
    """解析器协调器 - 统一管理所有解析器"""
    
    def __init__(self, config: Optional[ParserConfig] = None):
        """
        初始化解析器协调器
        
        Args:
            config: 解析器配置
        """
        super().__init__(config.to_dict() if config else {})
        self.config_obj = config or ParserConfig()
        
        # 初始化各个解析器
        self.page_parser = PageContentParser(config)
        self.image_extractor = ImageExtractor(config)
        self.subpage_extractor = SubPageExtractor(config)
        self.image_filter = ImageFilter(config)
        
        # 解析器执行顺序
        self.parser_order = [
            'page_content',
            'image_extraction',
            'subpage_extraction',
            'image_filtering'
        ]
        
        # 性能统计
        self.performance_stats = {
            'total_time': 0,
            'parser_times': {},
            'success_count': 0,
            'error_count': 0
        }
    
    def parse(self, content: Any, options: Optional[Dict[str, Any]] = None) -> ParseResult:
        """
        协调执行所有解析器
        
        Args:
            content: 输入内容（URL或HTML字符串）
            options: 解析选项
            
        Returns:
            综合解析结果
        """
        start_time = time.time()
        result = ParseResult()
        options = options or {}
        
        try:
            self.logger.info("开始协调解析过程")
            
            # 第一步：页面内容解析
            page_result = self._execute_page_parsing(content, options)
            if not page_result or page_result.has_errors():
                result.merge_errors(page_result.errors if page_result else ["页面解析失败"])
                return result
            
            # 合并页面解析结果
            result.merge(page_result)
            
            # 第二步：并行执行图片提取和子页面提取
            if page_result.content:
                parallel_results = self._execute_parallel_extraction(
                    page_result.content, 
                    options, 
                    page_result.metadata.get('base_url', options.get('url', ''))
                )
                
                # 合并并行结果
                for parallel_result in parallel_results:
                    if parallel_result:
                        result.merge(parallel_result)
            
            # 第三步：图片过滤
            if result.images:
                filter_result = self._execute_image_filtering(result.images, options)
                if filter_result:
                    result.images = filter_result.images
                    result.metadata.update(filter_result.metadata)
            
            # 更新统计信息
            self.performance_stats['success_count'] += 1
            
            self.logger.info(f"解析完成: 获得 {len(result.images)} 张图片, {len(result.subpages)} 个子页面")
            
        except Exception as e:
            error_msg = f"协调解析失败: {str(e)}"
            result.add_error(error_msg)
            self.performance_stats['error_count'] += 1
            self.handle_error(e, "协调解析")
        
        finally:
            # 记录总时间
            total_time = time.time() - start_time
            self.performance_stats['total_time'] += total_time
            result.metadata['parse_time'] = total_time
        
        return result
    
    def _execute_page_parsing(self, content: Any, options: Dict[str, Any]) -> Optional[ParseResult]:
        """
        执行页面内容解析
        
        Args:
            content: 输入内容
            options: 解析选项
            
        Returns:
            页面解析结果
        """
        start_time = time.time()
        
        try:
            self.logger.debug("开始页面内容解析")
            result = self.page_parser.parse(content, options)
            
            parse_time = time.time() - start_time
            self.performance_stats['parser_times']['page_content'] = parse_time
            
            return result
            
        except Exception as e:
            self.logger.error(f"页面内容解析失败: {str(e)}")
            return None
    
    def _execute_parallel_extraction(self, content: Any, options: Dict[str, Any], base_url: str) -> List[Optional[ParseResult]]:
        """
        并行执行图片提取和子页面提取
        
        Args:
            content: 页面内容
            options: 解析选项
            base_url: 基础URL
            
        Returns:
            并行解析结果列表
        """
        results = []
        
        # 准备并行任务
        tasks = []
        
        # 图片提取任务
        if options.get('extract_images', True):
            image_options = options.copy()
            image_options['base_url'] = base_url
            tasks.append(('image_extraction', self.image_extractor, content, image_options))
        
        # 子页面提取任务
        if options.get('extract_subpages', True):
            subpage_options = options.copy()
            subpage_options['base_url'] = base_url
            tasks.append(('subpage_extraction', self.subpage_extractor, content, subpage_options))
        
        # 执行并行任务
        if tasks:
            max_workers = min(len(tasks), self.config_obj.performance.max_workers)
            
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # 提交任务
                future_to_task = {}
                for task_name, parser, task_content, task_options in tasks:
                    future = executor.submit(self._safe_parse, parser, task_content, task_options)
                    future_to_task[future] = task_name
                
                # 收集结果
                for future in as_completed(future_to_task):
                    task_name = future_to_task[future]
                    start_time = time.time()
                    
                    try:
                        result = future.result(timeout=30)  # 30秒超时
                        results.append(result)
                        
                        parse_time = time.time() - start_time
                        self.performance_stats['parser_times'][task_name] = parse_time
                        
                        self.logger.debug(f"{task_name} 完成，耗时 {parse_time:.2f}s")
                        
                    except Exception as e:
                        self.logger.error(f"{task_name} 执行失败: {str(e)}")
                        results.append(None)
        
        return results
    
    def _execute_image_filtering(self, images: List[ImageInfo], options: Dict[str, Any]) -> Optional[ParseResult]:
        """
        执行图片过滤
        
        Args:
            images: 图片列表
            options: 过滤选项
            
        Returns:
            过滤结果
        """
        start_time = time.time()
        
        try:
            if not options.get('filter_images', True):
                # 如果不需要过滤，直接返回
                result = ParseResult()
                result.images = images
                return result
            
            self.logger.debug(f"开始过滤 {len(images)} 张图片")
            result = self.image_filter.parse(images, options)
            
            parse_time = time.time() - start_time
            self.performance_stats['parser_times']['image_filtering'] = parse_time
            
            return result
            
        except Exception as e:
            self.logger.error(f"图片过滤失败: {str(e)}")
            return None
    
    def _safe_parse(self, parser: BaseParser, content: Any, options: Dict[str, Any]) -> Optional[ParseResult]:
        """
        安全执行解析器
        
        Args:
            parser: 解析器实例
            content: 内容
            options: 选项
            
        Returns:
            解析结果
        """
        try:
            return parser.parse(content, options)
        except Exception as e:
            self.logger.error(f"解析器 {parser.__class__.__name__} 执行失败: {str(e)}")
            return None
    
    def parse_batch(self, urls: List[str], options: Optional[Dict[str, Any]] = None) -> List[ParseResult]:
        """
        批量解析多个URL
        
        Args:
            urls: URL列表
            options: 解析选项
            
        Returns:
            解析结果列表
        """
        results = []
        options = options or {}
        
        max_workers = min(len(urls), self.config_obj.performance.max_workers)
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交任务
            future_to_url = {}
            for url in urls:
                url_options = options.copy()
                url_options['url'] = url
                future = executor.submit(self.parse, url, url_options)
                future_to_url[future] = url
            
            # 收集结果
            for future in as_completed(future_to_url):
                url = future_to_url[future]
                try:
                    result = future.result(timeout=60)  # 60秒超时
                    results.append(result)
                    self.logger.info(f"URL {url} 解析完成")
                except Exception as e:
                    error_result = ParseResult()
                    error_result.add_error(f"URL {url} 解析失败: {str(e)}")
                    results.append(error_result)
                    self.logger.error(f"URL {url} 解析失败: {str(e)}")
        
        return results
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """
        获取性能统计信息
        
        Returns:
            性能统计
        """
        stats = self.performance_stats.copy()
        
        # 计算平均时间
        if stats['success_count'] > 0:
            stats['average_time'] = stats['total_time'] / stats['success_count']
        else:
            stats['average_time'] = 0
        
        # 计算成功率
        total_requests = stats['success_count'] + stats['error_count']
        if total_requests > 0:
            stats['success_rate'] = stats['success_count'] / total_requests
        else:
            stats['success_rate'] = 0
        
        return stats
    
    def reset_stats(self):
        """重置性能统计"""
        self.performance_stats = {
            'total_time': 0,
            'parser_times': {},
            'success_count': 0,
            'error_count': 0
        }
    
    def configure_parser(self, parser_name: str, config: Dict[str, Any]):
        """
        配置特定解析器
        
        Args:
            parser_name: 解析器名称
            config: 配置参数
        """
        parser_map = {
            'page_content': self.page_parser,
            'image_extraction': self.image_extractor,
            'subpage_extraction': self.subpage_extractor,
            'image_filtering': self.image_filter
        }
        
        parser = parser_map.get(parser_name)
        if parser:
            parser.update_config(config)
            self.logger.info(f"已更新 {parser_name} 解析器配置")
        else:
            raise ValueError(f"未知的解析器名称: {parser_name}")
    
    def get_parser_status(self) -> Dict[str, Dict[str, Any]]:
        """
        获取所有解析器状态
        
        Returns:
            解析器状态信息
        """
        return {
            'page_content': {
                'class': self.page_parser.__class__.__name__,
                'config': self.page_parser.config,
                'last_error': getattr(self.page_parser, 'last_error', None)
            },
            'image_extraction': {
                'class': self.image_extractor.__class__.__name__,
                'config': self.image_extractor.config,
                'last_error': getattr(self.image_extractor, 'last_error', None)
            },
            'subpage_extraction': {
                'class': self.subpage_extractor.__class__.__name__,
                'config': self.subpage_extractor.config,
                'last_error': getattr(self.subpage_extractor, 'last_error', None)
            },
            'image_filtering': {
                'class': self.image_filter.__class__.__name__,
                'config': self.image_filter.config,
                'last_error': getattr(self.image_filter, 'last_error', None)
            }
        }