"""
图片过滤器
负责根据各种条件过滤图片
"""

import re
from typing import List, Dict, Any, Optional, Set, Tuple
from urllib.parse import urlparse
from pathlib import Path

from .base_parser import BaseParser, ImageInfo, ParseResult, ParserMixin
from .parser_exceptions import FilterError, ValidationError
from .parser_config import ParserConfig


class ImageFilter(BaseParser, ParserMixin):
    """图片过滤器"""
    
    def __init__(self, config: Optional[ParserConfig] = None):
        """
        初始化图片过滤器
        
        Args:
            config: 解析器配置
        """
        super().__init__(config.to_dict() if config else {})
        self.config_obj = config or ParserConfig()
        
        # 默认过滤规则
        self.default_filters = {
            'min_width': 100,
            'min_height': 100,
            'max_width': 10000,
            'max_height': 10000,
            'min_file_size': 1024,  # 1KB
            'max_file_size': 50 * 1024 * 1024,  # 50MB
            'allowed_formats': ['jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp'],
            'blocked_keywords': ['avatar', 'icon', 'logo', 'banner', 'ad', 'advertisement'],
            'blocked_domains': [],
            'required_keywords': [],
            'min_quality_score': 0.5
        }
    
    def parse(self, content: Any, options: Optional[Dict[str, Any]] = None) -> ParseResult:
        """
        过滤图片列表
        
        Args:
            content: 图片列表或ParseResult对象
            options: 过滤选项
            
        Returns:
            过滤后的结果
        """
        result = ParseResult()
        options = options or {}
        
        try:
            # 获取图片列表
            images = self._extract_images(content)
            if not images:
                result.add_error("没有找到要过滤的图片")
                return result
            
            # 合并过滤规则
            filter_rules = self._merge_filter_rules(options)
            
            # 应用过滤规则
            filtered_images = []
            filter_stats = {
                'total': len(images),
                'filtered_out': 0,
                'reasons': {}
            }
            
            for image in images:
                filter_result = self.apply_filters(image, filter_rules)
                if filter_result['passed']:
                    filtered_images.append(image)
                else:
                    filter_stats['filtered_out'] += 1
                    for reason in filter_result['reasons']:
                        filter_stats['reasons'][reason] = filter_stats['reasons'].get(reason, 0) + 1
            
            result.images = filtered_images
            result.metadata['filter_stats'] = filter_stats
            
            self.logger.info(f"图片过滤完成: {len(filtered_images)}/{len(images)} 张图片通过过滤")
            
        except Exception as e:
            error_msg = f"图片过滤失败: {str(e)}"
            result.add_error(error_msg)
            self.handle_error(e, "图片过滤")
        
        return result
    
    def _extract_images(self, content: Any) -> List[ImageInfo]:
        """
        从内容中提取图片列表
        
        Args:
            content: 内容对象
            
        Returns:
            图片列表
        """
        if isinstance(content, ParseResult):
            return content.images
        elif isinstance(content, list):
            return [img for img in content if isinstance(img, ImageInfo)]
        else:
            return []
    
    def _merge_filter_rules(self, options: Dict[str, Any]) -> Dict[str, Any]:
        """
        合并过滤规则
        
        Args:
            options: 用户选项
            
        Returns:
            合并后的过滤规则
        """
        rules = self.default_filters.copy()
        
        # 从配置对象获取规则
        if self.config_obj and self.config_obj.image:
            config_rules = {
                'min_width': self.config_obj.image.min_width,
                'min_height': self.config_obj.image.min_height,
                'max_width': self.config_obj.image.max_width,
                'max_height': self.config_obj.image.max_height,
                'min_file_size': self.config_obj.image.min_file_size,
                'max_file_size': self.config_obj.image.max_file_size,
                'allowed_formats': self.config_obj.image.allowed_formats
            }
            rules.update({k: v for k, v in config_rules.items() if v is not None})
        
        # 应用用户选项
        rules.update(options)
        
        return rules
    
    def apply_filters(self, image: ImageInfo, rules: Dict[str, Any]) -> Dict[str, Any]:
        """
        对单张图片应用过滤规则
        
        Args:
            image: 图片信息
            rules: 过滤规则
            
        Returns:
            过滤结果
        """
        result = {
            'passed': True,
            'reasons': [],
            'score': 1.0
        }
        
        try:
            # 尺寸过滤
            if not self._check_dimensions(image, rules, result):
                result['passed'] = False
            
            # 文件大小过滤
            if not self._check_file_size(image, rules, result):
                result['passed'] = False
            
            # 格式过滤
            if not self._check_format(image, rules, result):
                result['passed'] = False
            
            # 关键词过滤
            if not self._check_keywords(image, rules, result):
                result['passed'] = False
            
            # 域名过滤
            if not self._check_domain(image, rules, result):
                result['passed'] = False
            
            # 质量评分过滤
            if not self._check_quality(image, rules, result):
                result['passed'] = False
            
            # URL有效性检查
            if not self._check_url_validity(image, rules, result):
                result['passed'] = False
            
        except Exception as e:
            result['passed'] = False
            result['reasons'].append(f"过滤器错误: {str(e)}")
            self.logger.warning(f"过滤图片时出错: {str(e)}")
        
        return result
    
    def _check_dimensions(self, image: ImageInfo, rules: Dict[str, Any], result: Dict[str, Any]) -> bool:
        """检查图片尺寸"""
        try:
            width = image.metadata.get('width', 0)
            height = image.metadata.get('height', 0)
            
            # 如果没有尺寸信息，尝试从URL推断
            if not width or not height:
                estimated_size = self._estimate_size_from_url(image.url)
                if estimated_size:
                    width, height = estimated_size
            
            min_width = rules.get('min_width', 0)
            min_height = rules.get('min_height', 0)
            max_width = rules.get('max_width', float('inf'))
            max_height = rules.get('max_height', float('inf'))
            
            if width and width < min_width:
                result['reasons'].append(f"宽度过小: {width} < {min_width}")
                return False
            
            if height and height < min_height:
                result['reasons'].append(f"高度过小: {height} < {min_height}")
                return False
            
            if width and width > max_width:
                result['reasons'].append(f"宽度过大: {width} > {max_width}")
                return False
            
            if height and height > max_height:
                result['reasons'].append(f"高度过大: {height} > {max_height}")
                return False
            
            return True
            
        except Exception:
            return True  # 如果无法检查尺寸，默认通过
    
    def _check_file_size(self, image: ImageInfo, rules: Dict[str, Any], result: Dict[str, Any]) -> bool:
        """检查文件大小"""
        try:
            file_size = image.metadata.get('file_size', 0)
            
            min_size = rules.get('min_file_size', 0)
            max_size = rules.get('max_file_size', float('inf'))
            
            if file_size and file_size < min_size:
                result['reasons'].append(f"文件过小: {file_size} < {min_size}")
                return False
            
            if file_size and file_size > max_size:
                result['reasons'].append(f"文件过大: {file_size} > {max_size}")
                return False
            
            return True
            
        except Exception:
            return True
    
    def _check_format(self, image: ImageInfo, rules: Dict[str, Any], result: Dict[str, Any]) -> bool:
        """检查图片格式"""
        try:
            allowed_formats = rules.get('allowed_formats', [])
            if not allowed_formats:
                return True
            
            # 从URL获取文件扩展名
            file_ext = self.get_file_extension(image.url)
            if not file_ext:
                # 尝试从Content-Type获取
                content_type = image.metadata.get('content_type', '')
                if content_type:
                    file_ext = self._content_type_to_extension(content_type)
            
            if file_ext and file_ext.lower() not in [fmt.lower() for fmt in allowed_formats]:
                result['reasons'].append(f"不支持的格式: {file_ext}")
                return False
            
            return True
            
        except Exception:
            return True
    
    def _check_keywords(self, image: ImageInfo, rules: Dict[str, Any], result: Dict[str, Any]) -> bool:
        """检查关键词"""
        try:
            blocked_keywords = rules.get('blocked_keywords', [])
            required_keywords = rules.get('required_keywords', [])
            
            # 收集所有文本信息
            text_content = ' '.join([
                image.url,
                image.filename,
                image.alt_text,
                image.title,
                str(image.metadata.get('class', '')),
                str(image.metadata.get('id', ''))
            ]).lower()
            
            # 检查阻止的关键词
            for keyword in blocked_keywords:
                if keyword.lower() in text_content:
                    result['reasons'].append(f"包含阻止的关键词: {keyword}")
                    return False
            
            # 检查必需的关键词
            if required_keywords:
                found_required = False
                for keyword in required_keywords:
                    if keyword.lower() in text_content:
                        found_required = True
                        break
                
                if not found_required:
                    result['reasons'].append(f"缺少必需的关键词: {required_keywords}")
                    return False
            
            return True
            
        except Exception:
            return True
    
    def _check_domain(self, image: ImageInfo, rules: Dict[str, Any], result: Dict[str, Any]) -> bool:
        """检查域名"""
        try:
            blocked_domains = rules.get('blocked_domains', [])
            if not blocked_domains:
                return True
            
            parsed_url = urlparse(image.url)
            domain = parsed_url.netloc.lower()
            
            for blocked_domain in blocked_domains:
                if blocked_domain.lower() in domain:
                    result['reasons'].append(f"来自阻止的域名: {blocked_domain}")
                    return False
            
            return True
            
        except Exception:
            return True
    
    def _check_quality(self, image: ImageInfo, rules: Dict[str, Any], result: Dict[str, Any]) -> bool:
        """检查图片质量"""
        try:
            min_quality = rules.get('min_quality_score', 0)
            if min_quality <= 0:
                return True
            
            # 计算质量评分
            quality_score = self._calculate_quality_score(image)
            result['score'] = quality_score
            
            if quality_score < min_quality:
                result['reasons'].append(f"质量评分过低: {quality_score:.2f} < {min_quality}")
                return False
            
            return True
            
        except Exception:
            return True
    
    def _check_url_validity(self, image: ImageInfo, rules: Dict[str, Any], result: Dict[str, Any]) -> bool:
        """检查URL有效性"""
        try:
            if not image.url or not self.is_valid_url(image.url):
                result['reasons'].append("无效的URL")
                return False
            
            # 检查URL长度
            if len(image.url) > 2000:
                result['reasons'].append("URL过长")
                return False
            
            # 检查是否为数据URL
            if image.url.startswith('data:'):
                result['reasons'].append("数据URL")
                return False
            
            return True
            
        except Exception:
            return True
    
    def _calculate_quality_score(self, image: ImageInfo) -> float:
        """
        计算图片质量评分
        
        Args:
            image: 图片信息
            
        Returns:
            质量评分 (0-1)
        """
        score = 0.5  # 基础分数
        
        try:
            # 尺寸评分
            width = image.metadata.get('width', 0)
            height = image.metadata.get('height', 0)
            
            if width and height:
                # 分辨率评分
                resolution = width * height
                if resolution >= 1920 * 1080:  # Full HD
                    score += 0.2
                elif resolution >= 1280 * 720:  # HD
                    score += 0.1
                
                # 宽高比评分
                aspect_ratio = width / height
                if 0.5 <= aspect_ratio <= 2.0:  # 合理的宽高比
                    score += 0.1
            
            # 文件名评分
            filename = image.filename.lower()
            if any(keyword in filename for keyword in ['high', 'hd', 'large', 'big']):
                score += 0.1
            
            # Alt文本评分
            if image.alt_text and len(image.alt_text.strip()) > 5:
                score += 0.1
            
            # URL评分
            url_lower = image.url.lower()
            if any(keyword in url_lower for keyword in ['original', 'full', 'large', 'high']):
                score += 0.1
            
            # 确保评分在0-1范围内
            score = max(0.0, min(1.0, score))
            
        except Exception:
            pass
        
        return score
    
    def _estimate_size_from_url(self, url: str) -> Optional[Tuple[int, int]]:
        """
        从URL推断图片尺寸
        
        Args:
            url: 图片URL
            
        Returns:
            尺寸元组 (width, height) 或 None
        """
        try:
            # 查找URL中的尺寸信息
            size_patterns = [
                r'(\d+)x(\d+)',
                r'(\d+)_(\d+)',
                r'w(\d+)h(\d+)',
                r'(\d+)w(\d+)h'
            ]
            
            for pattern in size_patterns:
                match = re.search(pattern, url, re.IGNORECASE)
                if match:
                    width, height = int(match.group(1)), int(match.group(2))
                    if 10 <= width <= 10000 and 10 <= height <= 10000:
                        return (width, height)
            
            return None
            
        except Exception:
            return None
    
    def _content_type_to_extension(self, content_type: str) -> str:
        """
        将Content-Type转换为文件扩展名
        
        Args:
            content_type: MIME类型
            
        Returns:
            文件扩展名
        """
        mime_to_ext = {
            'image/jpeg': 'jpg',
            'image/jpg': 'jpg',
            'image/png': 'png',
            'image/gif': 'gif',
            'image/webp': 'webp',
            'image/bmp': 'bmp',
            'image/svg+xml': 'svg',
            'image/x-icon': 'ico'
        }
        
        return mime_to_ext.get(content_type.lower(), '')
    
    def get_filter_statistics(self, images: List[ImageInfo], rules: Dict[str, Any]) -> Dict[str, Any]:
        """
        获取过滤统计信息
        
        Args:
            images: 图片列表
            rules: 过滤规则
            
        Returns:
            统计信息
        """
        stats = {
            'total_images': len(images),
            'passed_images': 0,
            'failed_images': 0,
            'failure_reasons': {},
            'quality_distribution': {'high': 0, 'medium': 0, 'low': 0}
        }
        
        for image in images:
            filter_result = self.apply_filters(image, rules)
            
            if filter_result['passed']:
                stats['passed_images'] += 1
            else:
                stats['failed_images'] += 1
                for reason in filter_result['reasons']:
                    stats['failure_reasons'][reason] = stats['failure_reasons'].get(reason, 0) + 1
            
            # 质量分布
            score = filter_result['score']
            if score >= 0.8:
                stats['quality_distribution']['high'] += 1
            elif score >= 0.5:
                stats['quality_distribution']['medium'] += 1
            else:
                stats['quality_distribution']['low'] += 1
        
        return stats