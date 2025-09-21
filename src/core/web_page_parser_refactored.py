"""
重构后的WebPageParser类
使用新的解析器架构，替代原来的庞大类
"""

from typing import List, Dict, Any, Optional, Union
import time
from urllib.parse import urljoin

from .parsers import (
    ParserCoordinator, 
    ParserConfig, 
    ParseResult, 
    ImageInfo, 
    SubPageInfo,
    ParserError
)
from ..utils.logger import get_logger


class WebPageParser:
    """
    重构后的网页解析器
    
    这是一个轻量级的包装器，使用新的解析器架构
    保持与原有接口的兼容性，同时提供更好的可维护性
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化网页解析器
        
        Args:
            config: 解析器配置
        """
        self.logger = get_logger(self.__class__.__name__)
        
        # 创建解析器配置
        self.parser_config = ParserConfig()
        if config:
            self._apply_legacy_config(config)
        
        # 创建解析器协调器
        self.coordinator = ParserCoordinator(self.parser_config)
        
        # 兼容性属性
        self.config = config or {}
        self.session = None  # 保持兼容性
        
        # 统计信息
        self.stats = {
            'total_parsed': 0,
            'total_images': 0,
            'total_subpages': 0,
            'total_errors': 0,
            'parse_times': []
        }
        
        self.logger.info("WebPageParser 已初始化（使用重构后的架构）")
    
    def _apply_legacy_config(self, config: Dict[str, Any]):
        """
        应用旧版配置到新的解析器配置
        
        Args:
            config: 旧版配置
        """
        # 映射旧配置到新配置
        if 'timeout' in config:
            self.parser_config.network.timeout = config['timeout']
        
        if 'max_retries' in config:
            self.parser_config.network.max_retries = config['max_retries']
        
        if 'user_agent' in config:
            self.parser_config.network.user_agent = config['user_agent']
        
        if 'headers' in config:
            self.parser_config.network.headers.update(config['headers'])
        
        # 图片配置
        if 'min_image_size' in config:
            self.parser_config.image.min_file_size = config['min_image_size']
        
        if 'max_image_size' in config:
            self.parser_config.image.max_file_size = config['max_image_size']
        
        if 'image_formats' in config:
            self.parser_config.image.allowed_formats = config['image_formats']
        
        # 性能配置
        if 'max_workers' in config:
            self.parser_config.performance.max_workers = config['max_workers']
        
        if 'rate_limit' in config:
            self.parser_config.performance.rate_limit = config['rate_limit']
    
    def parse_page(self, url: str, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        解析单个页面（兼容旧接口）
        
        Args:
            url: 页面URL
            options: 解析选项
            
        Returns:
            解析结果字典
        """
        start_time = time.time()
        
        try:
            self.logger.info(f"开始解析页面: {url}")
            
            # 使用新的解析器协调器
            parse_options = options or {}
            parse_options['url'] = url
            
            result = self.coordinator.parse(url, parse_options)
            
            # 转换为旧格式
            legacy_result = self._convert_to_legacy_format(result, url)
            
            # 更新统计信息
            parse_time = time.time() - start_time
            self._update_stats(result, parse_time)
            
            self.logger.info(f"页面解析完成: {len(legacy_result.get('images', []))} 张图片, "
                           f"{len(legacy_result.get('subpages', []))} 个子页面, 耗时 {parse_time:.2f}s")
            
            return legacy_result
            
        except Exception as e:
            self.stats['total_errors'] += 1
            error_msg = f"解析页面失败 {url}: {str(e)}"
            self.logger.error(error_msg)
            
            return {
                'url': url,
                'images': [],
                'subpages': [],
                'metadata': {},
                'errors': [error_msg],
                'success': False,
                'parse_time': time.time() - start_time
            }
    
    def parse_pages(self, urls: List[str], options: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        批量解析多个页面（兼容旧接口）
        
        Args:
            urls: URL列表
            options: 解析选项
            
        Returns:
            解析结果列表
        """
        self.logger.info(f"开始批量解析 {len(urls)} 个页面")
        
        # 使用新的批量解析功能
        results = self.coordinator.parse_batch(urls, options)
        
        # 转换为旧格式
        legacy_results = []
        for i, result in enumerate(results):
            url = urls[i] if i < len(urls) else "unknown"
            legacy_result = self._convert_to_legacy_format(result, url)
            legacy_results.append(legacy_result)
        
        self.logger.info(f"批量解析完成: {len(legacy_results)} 个页面")
        return legacy_results
    
    def _convert_to_legacy_format(self, result: ParseResult, url: str) -> Dict[str, Any]:
        """
        将新格式的解析结果转换为旧格式
        
        Args:
            result: 新格式解析结果
            url: 页面URL
            
        Returns:
            旧格式结果字典
        """
        # 转换图片信息
        images = []
        for img in result.images:
            images.append({
                'url': img.url,
                'filename': img.filename,
                'size': img.size,
                'width': img.width,
                'height': img.height,
                'format': img.format,
                'alt_text': img.alt_text,
                'title': img.title,
                'source_page': img.source_page,
                'metadata': img.metadata
            })
        
        # 转换子页面信息
        subpages = []
        for subpage in result.subpages:
            subpages.append({
                'url': subpage.url,
                'title': subpage.title,
                'description': subpage.description,
                'depth': subpage.depth,
                'parent_url': subpage.parent_url,
                'link_text': subpage.link_text,
                'page_type': subpage.page_type,
                'priority': subpage.priority,
                'source_page': subpage.source_page,
                'metadata': subpage.metadata
            })
        
        return {
            'url': url,
            'images': images,
            'subpages': subpages,
            'metadata': result.metadata,
            'errors': result.errors,
            'warnings': result.warnings,
            'success': result.success,
            'parse_time': result.metadata.get('parse_time', 0)
        }
    
    def _update_stats(self, result: ParseResult, parse_time: float):
        """
        更新统计信息
        
        Args:
            result: 解析结果
            parse_time: 解析时间
        """
        self.stats['total_parsed'] += 1
        self.stats['total_images'] += len(result.images)
        self.stats['total_subpages'] += len(result.subpages)
        if result.errors:
            self.stats['total_errors'] += 1
        self.stats['parse_times'].append(parse_time)
        
        # 保持最近100次的解析时间
        if len(self.stats['parse_times']) > 100:
            self.stats['parse_times'] = self.stats['parse_times'][-100:]
    
    def get_images(self, url: str, options: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        仅获取图片（兼容旧接口）
        
        Args:
            url: 页面URL
            options: 解析选项
            
        Returns:
            图片列表
        """
        parse_options = options or {}
        parse_options['extract_subpages'] = False  # 只提取图片
        
        result = self.parse_page(url, parse_options)
        return result.get('images', [])
    
    def get_subpages(self, url: str, options: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        仅获取子页面（兼容旧接口）
        
        Args:
            url: 页面URL
            options: 解析选项
            
        Returns:
            子页面列表
        """
        parse_options = options or {}
        parse_options['extract_images'] = False  # 只提取子页面
        
        result = self.parse_page(url, parse_options)
        return result.get('subpages', [])
    
    def filter_images(self, images: List[Dict[str, Any]], filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        过滤图片（兼容旧接口）
        
        Args:
            images: 图片列表
            filters: 过滤条件
            
        Returns:
            过滤后的图片列表
        """
        # 转换为新格式
        image_infos = []
        for img in images:
            image_info = ImageInfo(
                url=img.get('url', ''),
                filename=img.get('filename', ''),
                size=img.get('size', 0),
                width=img.get('width', 0),
                height=img.get('height', 0),
                format=img.get('format', ''),
                alt_text=img.get('alt_text', ''),
                title=img.get('title', ''),
                source_page=img.get('source_page', ''),
                metadata=img.get('metadata', {})
            )
            image_infos.append(image_info)
        
        # 使用新的过滤器
        filter_result = self.coordinator.image_filter.parse(image_infos, filters)
        
        # 转换回旧格式
        filtered_images = []
        for img in filter_result.images:
            filtered_images.append({
                'url': img.url,
                'filename': img.filename,
                'size': img.size,
                'width': img.width,
                'height': img.height,
                'format': img.format,
                'alt_text': img.alt_text,
                'title': img.title,
                'source_page': img.source_page,
                'metadata': img.metadata
            })
        
        return filtered_images
    
    def get_stats(self) -> Dict[str, Any]:
        """
        获取统计信息
        
        Returns:
            统计信息字典
        """
        stats = self.stats.copy()
        
        # 计算平均解析时间
        if stats['parse_times']:
            stats['average_parse_time'] = sum(stats['parse_times']) / len(stats['parse_times'])
            stats['min_parse_time'] = min(stats['parse_times'])
            stats['max_parse_time'] = max(stats['parse_times'])
        else:
            stats['average_parse_time'] = 0
            stats['min_parse_time'] = 0
            stats['max_parse_time'] = 0
        
        # 添加解析器性能统计
        coordinator_stats = self.coordinator.get_performance_stats()
        stats['coordinator_stats'] = coordinator_stats
        
        return stats
    
    def reset_stats(self):
        """重置统计信息"""
        self.stats = {
            'total_parsed': 0,
            'total_images': 0,
            'total_subpages': 0,
            'total_errors': 0,
            'parse_times': []
        }
        self.coordinator.reset_stats()
    
    def configure(self, config: Dict[str, Any]):
        """
        更新配置（兼容旧接口）
        
        Args:
            config: 新配置
        """
        self.config.update(config)
        self._apply_legacy_config(config)
        
        # 重新创建协调器
        self.coordinator = ParserCoordinator(self.parser_config)
        
        self.logger.info("配置已更新")
    
    def get_parser_status(self) -> Dict[str, Any]:
        """
        获取解析器状态
        
        Returns:
            解析器状态信息
        """
        return {
            'version': '2.0.0-refactored',
            'architecture': 'modular',
            'parsers': self.coordinator.get_parser_status(),
            'stats': self.get_stats(),
            'config': {
                'network': {
                    'timeout': self.parser_config.network.timeout,
                    'max_retries': self.parser_config.network.max_retries,
                    'user_agent': self.parser_config.network.user_agent
                },
                'image': {
                    'min_file_size': self.parser_config.image.min_file_size,
                    'max_file_size': self.parser_config.image.max_file_size,
                    'allowed_formats': self.parser_config.image.allowed_formats
                },
                'performance': {
                    'max_workers': self.parser_config.performance.max_workers,
                    'rate_limit': self.parser_config.performance.rate_limit
                }
            }
        }
    
    # 兼容性方法
    def close(self):
        """关闭解析器（兼容性方法）"""
        self.logger.info("WebPageParser 已关闭")
    
    def __enter__(self):
        """上下文管理器入口"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.close()


# 为了完全兼容，创建一个别名
WebPageParserRefactored = WebPageParser