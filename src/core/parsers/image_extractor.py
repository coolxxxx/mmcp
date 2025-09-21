"""
简化版图片提取器
负责从页面中提取图片链接和元数据
"""

import re
from typing import List, Dict, Any, Optional, Set, Union
from urllib.parse import urljoin, urlparse

from .base_parser import BaseParser, ImageInfo, ParseResult, ParserMixin
from .parser_exceptions import ParseError, ValidationError
from .parser_config import ParserConfig


class ImageExtractor(BaseParser, ParserMixin):
    """图片提取器"""
    
    def __init__(self, config: Optional[ParserConfig] = None):
        """
        初始化图片提取器
        
        Args:
            config: 解析器配置
        """
        super().__init__(config.to_dict() if config else {})
        self.config_obj = config or ParserConfig()
        
        # 图片URL模式
        self.image_url_patterns = [
            r'\.(jpg|jpeg|png|gif|webp|bmp|svg|ico)(\?[^?\s]*)?$',
            r'/images?/',
            r'/img/',
            r'/photos?/',
            r'/pics?/',
            r'/gallery/',
            r'/media/',
        ]
        
        # 编译正则表达式
        self.compiled_patterns = [re.compile(pattern, re.IGNORECASE) 
                                for pattern in self.image_url_patterns]
    
    def parse(self, content: Any, options: Optional[Dict[str, Any]] = None) -> ParseResult:
        """
        从页面中提取图片
        
        Args:
            content: BeautifulSoup对象或HTML字符串
            options: 解析选项，包含base_url等
            
        Returns:
            解析结果
        """
        result = ParseResult()
        options = options or {}
        base_url = options.get('base_url', '')
        
        try:
            # 处理输入内容
            soup = self._prepare_soup(content)
            if not soup:
                result.add_error("无法解析输入内容")
                return result
            
            if not base_url:
                result.add_error("缺少base_url参数")
                return result
            
            # 提取图片
            images = []
            
            # 从img标签提取
            img_images = self.extract_from_img_tags(soup, base_url)
            images.extend(img_images)
            
            # 从CSS背景图片提取
            css_images = self.extract_from_css_backgrounds(soup, base_url)
            images.extend(css_images)
            
            # 从链接中提取图片URL
            link_images = self.extract_from_links(soup, base_url)
            images.extend(link_images)
            
            # 去重
            unique_images = self.deduplicate_images(images)
            
            # 转换为ImageInfo对象
            for img_data in unique_images:
                image_info = ImageInfo(
                    url=img_data['url'],
                    filename=img_data.get('filename', ''),
                    alt_text=img_data.get('alt', ''),
                    title=img_data.get('title', ''),
                    source_page=base_url,
                    metadata=img_data.get('metadata', {})
                )
                result.images.append(image_info)
            
            self.logger.info(f"从页面提取到 {len(result.images)} 张图片")
            
        except Exception as e:
            error_msg = f"图片提取失败: {str(e)}"
            result.add_error(error_msg)
            self.handle_error(e, "图片提取")
        
        return result
    
    def _prepare_soup(self, content: Any) -> Optional[Any]:
        """准备BeautifulSoup对象"""
        try:
            # 如果已经是BeautifulSoup对象
            if hasattr(content, 'find_all'):
                return content
            
            # 如果是字符串，创建BeautifulSoup对象
            if isinstance(content, str):
                from bs4 import BeautifulSoup
                return BeautifulSoup(content, 'html.parser')
            
            return None
        except Exception:
            return None
    
    def extract_from_img_tags(self, soup: Any, base_url: str) -> List[Dict[str, Any]]:
        """
        从img标签提取图片
        
        Args:
            soup: BeautifulSoup对象
            base_url: 基础URL
            
        Returns:
            图片信息列表
        """
        images = []
        
        try:
            img_tags = soup.find_all('img')
            
            for img_tag in img_tags:
                img_data = self.extract_img_tag_data(img_tag, base_url)
                if img_data:
                    images.append(img_data)
                    
        except Exception as e:
            self.logger.warning(f"从img标签提取图片时出错: {str(e)}")
        
        return images
    
    def extract_img_tag_data(self, img_tag: Any, base_url: str) -> Optional[Dict[str, Any]]:
        """
        从单个img标签提取数据
        
        Args:
            img_tag: img标签
            base_url: 基础URL
            
        Returns:
            图片数据字典
        """
        try:
            # 获取图片URL
            src = self.get_img_src(img_tag)
            if not src:
                return None
            
            # 转换为绝对URL
            absolute_url = urljoin(base_url, src)
            
            # 验证URL
            if not self.is_valid_image_url(absolute_url):
                return None
            
            # 安全地获取属性
            def safe_get(tag, attr, default=''):
                try:
                    value = tag.get(attr, default)
                    if isinstance(value, list):
                        return ' '.join(str(v) for v in value)
                    return str(value) if value else default
                except:
                    return default
            
            # 提取其他属性
            img_data = {
                'url': absolute_url,
                'alt': safe_get(img_tag, 'alt').strip(),
                'title': safe_get(img_tag, 'title').strip(),
                'width': self._parse_dimension(safe_get(img_tag, 'width')),
                'height': self._parse_dimension(safe_get(img_tag, 'height')),
                'class': safe_get(img_tag, 'class'),
                'id': safe_get(img_tag, 'id'),
                'original_src': src,
                'source_type': 'img_tag',
                'metadata': {
                    'loading': safe_get(img_tag, 'loading'),
                    'decoding': safe_get(img_tag, 'decoding'),
                    'sizes': safe_get(img_tag, 'sizes'),
                    'srcset': safe_get(img_tag, 'srcset')
                }
            }
            
            return img_data
            
        except Exception as e:
            self.logger.warning(f"提取img标签数据时出错: {str(e)}")
            return None
    
    def get_img_src(self, img_tag: Any) -> str:
        """
        获取img标签的src属性，支持懒加载
        
        Args:
            img_tag: img标签
            
        Returns:
            图片URL
        """
        # 常见的src属性
        src_attrs = [
            'src',
            'data-src',
            'data-original',
            'data-lazy-src',
            'data-lazy',
            'data-url',
            'data-img-src',
            'data-image-src'
        ]
        
        for attr in src_attrs:
            try:
                src = img_tag.get(attr, '')
                if isinstance(src, str) and src.strip() and not src.startswith('data:'):
                    return src.strip()
            except:
                continue
        
        return ''
    
    def extract_from_css_backgrounds(self, soup: Any, base_url: str) -> List[Dict[str, Any]]:
        """
        从CSS背景图片提取
        
        Args:
            soup: BeautifulSoup对象
            base_url: 基础URL
            
        Returns:
            图片信息列表
        """
        images = []
        
        try:
            # 查找style标签
            style_tags = soup.find_all('style')
            for style_tag in style_tags:
                try:
                    css_content = style_tag.get_text()
                    if css_content:
                        css_images = self.extract_urls_from_css(css_content, base_url)
                        images.extend(css_images)
                except:
                    continue
            
            # 查找带有style属性的元素
            elements_with_style = soup.find_all(attrs={'style': True})
            for element in elements_with_style:
                try:
                    style_content = element.get('style', '')
                    if style_content:
                        css_images = self.extract_urls_from_css(str(style_content), base_url)
                        images.extend(css_images)
                except:
                    continue
                
        except Exception as e:
            self.logger.warning(f"从CSS背景提取图片时出错: {str(e)}")
        
        return images
    
    def extract_urls_from_css(self, css_content: str, base_url: str) -> List[Dict[str, Any]]:
        """
        从CSS内容中提取图片URL
        
        Args:
            css_content: CSS内容
            base_url: 基础URL
            
        Returns:
            图片信息列表
        """
        images = []
        
        try:
            # 匹配background-image: url(...)
            url_pattern = r'url\s*\(\s*["\']?([^"\')\s]+)["\']?\s*\)'
            matches = re.findall(url_pattern, css_content, re.IGNORECASE)
            
            for match in matches:
                url = match.strip()
                if not url or url.startswith('data:'):
                    continue
                
                absolute_url = urljoin(base_url, url)
                
                if self.is_valid_image_url(absolute_url):
                    images.append({
                        'url': absolute_url,
                        'source_type': 'css_background',
                        'original_url': url,
                        'metadata': {}
                    })
                    
        except Exception as e:
            self.logger.warning(f"从CSS提取URL时出错: {str(e)}")
        
        return images
    
    def extract_from_links(self, soup: Any, base_url: str) -> List[Dict[str, Any]]:
        """
        从链接中提取图片URL
        
        Args:
            soup: BeautifulSoup对象
            base_url: 基础URL
            
        Returns:
            图片信息列表
        """
        images = []
        
        try:
            # 查找所有链接
            a_tags = soup.find_all('a', href=True)
            
            for a_tag in a_tags:
                try:
                    href = a_tag.get('href', '')
                    if not href or not isinstance(href, str):
                        continue
                    
                    href = href.strip()
                    if not href:
                        continue
                    
                    absolute_url = urljoin(base_url, href)
                    
                    # 检查是否为图片URL
                    if self.is_valid_image_url(absolute_url):
                        images.append({
                            'url': absolute_url,
                            'source_type': 'link',
                            'link_text': a_tag.get_text().strip(),
                            'title': str(a_tag.get('title', '')),
                            'original_href': href,
                            'metadata': {}
                        })
                except:
                    continue
                    
        except Exception as e:
            self.logger.warning(f"从链接提取图片时出错: {str(e)}")
        
        return images
    
    def is_valid_image_url(self, url: str) -> bool:
        """
        检查URL是否为有效的图片URL
        
        Args:
            url: URL
            
        Returns:
            是否为有效图片URL
        """
        if not url or not self.is_valid_url(url):
            return False
        
        # 检查文件扩展名
        ext = self.get_file_extension(url)
        if ext and self.config_obj.image.is_supported_format(ext):
            return True
        
        # 检查URL模式
        for pattern in self.compiled_patterns:
            if pattern.search(url):
                return True
        
        return False
    
    def deduplicate_images(self, images: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        去除重复的图片
        
        Args:
            images: 图片列表
            
        Returns:
            去重后的图片列表
        """
        seen_urls: Set[str] = set()
        unique_images = []
        
        for img in images:
            url = img.get('url', '')
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique_images.append(img)
        
        return unique_images
    
    def _parse_dimension(self, value: Union[str, int, None]) -> int:
        """解析尺寸值"""
        if not value:
            return 0
        
        try:
            # 移除px等单位
            value_str = str(value).lower().replace('px', '').strip()
            return int(float(value_str))
        except:
            return 0