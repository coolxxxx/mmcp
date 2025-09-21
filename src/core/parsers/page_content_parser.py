"""
页面内容解析器
负责获取和解析网页内容
"""

import requests
import time
from typing import Dict, Any, Optional, Tuple
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import logging

from .base_parser import BaseParser, ParseResult, ParserMixin
from .parser_exceptions import NetworkError, ParseError, TimeoutError
from .parser_config import ParserConfig


class PageContentParser(BaseParser, ParserMixin):
    """页面内容解析器"""
    
    def __init__(self, config: Optional[ParserConfig] = None):
        """
        初始化页面内容解析器
        
        Args:
            config: 解析器配置
        """
        super().__init__(config.to_dict() if config else {})
        self.config_obj = config or ParserConfig()
        self.session = self._create_session()
    
    def _create_session(self) -> requests.Session:
        """创建HTTP会话"""
        session = requests.Session()
        
        # 设置请求头
        session.headers.update(self.config_obj.network.get_headers())
        
        # 设置代理
        if self.config_obj.network.proxies:
            session.proxies.update(self.config_obj.network.proxies)
        
        # 设置SSL验证
        session.verify = self.config_obj.network.verify_ssl
        
        # 设置最大重定向次数
        session.max_redirects = self.config_obj.network.max_redirects
        
        return session
    
    def parse(self, url: str, options: Optional[Dict[str, Any]] = None) -> ParseResult:
        """
        解析页面内容
        
        Args:
            url: 页面URL
            options: 解析选项
            
        Returns:
            解析结果
        """
        result = ParseResult()
        options = options or {}
        
        try:
            # 验证URL
            if not self.is_valid_url(url):
                result.add_error(f"无效的URL: {url}")
                return result
            
            # 获取页面内容
            content, final_url = self.fetch_page_content(url)
            if not content:
                result.add_error(f"无法获取页面内容: {url}")
                return result
            
            # 解析HTML
            soup = self.parse_html(content)
            if not soup:
                result.add_error(f"无法解析HTML内容: {url}")
                return result
            
            # 提取页面信息
            page_info = self.extract_page_info(soup, final_url)
            result.metadata.update(page_info)
            
            # 将解析后的内容添加到结果中
            result.metadata['soup'] = soup
            result.metadata['content'] = content
            result.metadata['final_url'] = final_url
            result.metadata['original_url'] = url
            
            self.logger.info(f"成功解析页面: {url}")
            
        except Exception as e:
            error_msg = f"解析页面失败 {url}: {str(e)}"
            result.add_error(error_msg)
            self.handle_error(e, f"解析页面 {url}")
        
        return result
    
    def fetch_page_content(self, url: str) -> Tuple[Optional[str], Optional[str]]:
        """
        获取页面内容
        
        Args:
            url: 页面URL
            
        Returns:
            (页面内容, 最终URL)
        """
        max_retries = self.config_obj.network.max_retries
        retry_delay = self.config_obj.network.retry_delay
        timeout = self.config_obj.network.request_timeout
        
        for attempt in range(max_retries + 1):
            try:
                self.logger.debug(f"获取页面内容 (尝试 {attempt + 1}/{max_retries + 1}): {url}")
                
                response = self.session.get(
                    url,
                    timeout=timeout,
                    allow_redirects=True
                )
                
                # 检查响应状态
                if response.status_code == 200:
                    # 检测编码
                    response.encoding = response.apparent_encoding or 'utf-8'
                    return response.text, response.url
                
                elif response.status_code in [301, 302, 303, 307, 308]:
                    # 重定向
                    redirect_url = response.headers.get('Location')
                    if redirect_url:
                        url = urljoin(url, redirect_url)
                        continue
                
                elif response.status_code == 429:
                    # 请求过于频繁，等待更长时间
                    wait_time = retry_delay * (2 ** attempt)
                    self.logger.warning(f"请求频率限制，等待 {wait_time} 秒")
                    time.sleep(wait_time)
                    continue
                
                else:
                    raise NetworkError(
                        f"HTTP错误: {response.status_code}",
                        url=url,
                        status_code=response.status_code
                    )
                
            except requests.exceptions.Timeout:
                if attempt < max_retries:
                    self.logger.warning(f"请求超时，重试中... ({attempt + 1}/{max_retries})")
                    time.sleep(retry_delay)
                    continue
                else:
                    raise TimeoutError(f"请求超时: {url}", timeout, "fetch_page_content")
            
            except requests.exceptions.ConnectionError as e:
                if attempt < max_retries:
                    self.logger.warning(f"连接错误，重试中... ({attempt + 1}/{max_retries})")
                    time.sleep(retry_delay)
                    continue
                else:
                    raise NetworkError(f"连接错误: {str(e)}", url=url)
            
            except requests.exceptions.RequestException as e:
                raise NetworkError(f"请求异常: {str(e)}", url=url)
        
        return None, None
    
    def parse_html(self, content: str) -> Optional[BeautifulSoup]:
        """
        解析HTML内容
        
        Args:
            content: HTML内容
            
        Returns:
            BeautifulSoup对象
        """
        try:
            # 使用lxml解析器，如果不可用则使用html.parser
            try:
                soup = BeautifulSoup(content, 'lxml')
            except:
                soup = BeautifulSoup(content, 'html.parser')
            
            return soup
            
        except Exception as e:
            raise ParseError(f"HTML解析失败: {str(e)}", "BeautifulSoup", "text/html")
    
    def extract_page_info(self, soup: BeautifulSoup, url: str) -> Dict[str, Any]:
        """
        提取页面基本信息
        
        Args:
            soup: BeautifulSoup对象
            url: 页面URL
            
        Returns:
            页面信息字典
        """
        info = {
            'url': url,
            'domain': self.extract_domain(url),
            'title': '',
            'description': '',
            'keywords': '',
            'language': '',
            'charset': '',
            'canonical_url': '',
            'og_info': {},
            'meta_info': {}
        }
        
        try:
            # 提取标题
            title_tag = soup.find('title')
            if title_tag:
                info['title'] = title_tag.get_text().strip()
            
            # 提取meta信息
            meta_tags = soup.find_all('meta')
            for meta in meta_tags:
                name = meta.get('name', '').lower()
                property_name = meta.get('property', '').lower()
                content = meta.get('content', '')
                
                if name == 'description':
                    info['description'] = content
                elif name == 'keywords':
                    info['keywords'] = content
                elif name == 'language':
                    info['language'] = content
                elif meta.get('charset'):
                    info['charset'] = meta.get('charset')
                elif meta.get('http-equiv', '').lower() == 'content-type':
                    info['charset'] = self._extract_charset_from_content_type(content)
                
                # Open Graph信息
                if property_name.startswith('og:'):
                    info['og_info'][property_name] = content
                
                # 其他meta信息
                if name:
                    info['meta_info'][name] = content
            
            # 提取canonical URL
            canonical_link = soup.find('link', rel='canonical')
            if canonical_link and canonical_link.get('href'):
                info['canonical_url'] = urljoin(url, canonical_link['href'])
            
            # 提取语言信息
            html_tag = soup.find('html')
            if html_tag and html_tag.get('lang'):
                info['language'] = html_tag['lang']
            
        except Exception as e:
            self.logger.warning(f"提取页面信息时出错: {str(e)}")
        
        return info
    
    def _extract_charset_from_content_type(self, content_type: str) -> str:
        """从content-type中提取字符集"""
        try:
            if 'charset=' in content_type.lower():
                charset = content_type.lower().split('charset=')[1].split(';')[0].strip()
                return charset
        except:
            pass
        return ''
    
    def get_page_links(self, soup: BeautifulSoup, base_url: str) -> list:
        """
        获取页面中的所有链接
        
        Args:
            soup: BeautifulSoup对象
            base_url: 基础URL
            
        Returns:
            链接列表
        """
        links = []
        
        try:
            # 查找所有a标签
            a_tags = soup.find_all('a', href=True)
            
            for a_tag in a_tags:
                href = a_tag['href'].strip()
                if not href or href.startswith('#'):
                    continue
                
                # 转换为绝对URL
                absolute_url = urljoin(base_url, href)
                
                # 提取链接信息
                link_info = {
                    'url': absolute_url,
                    'text': a_tag.get_text().strip(),
                    'title': a_tag.get('title', ''),
                    'rel': a_tag.get('rel', []),
                    'target': a_tag.get('target', ''),
                    'original_href': href
                }
                
                links.append(link_info)
                
        except Exception as e:
            self.logger.warning(f"提取页面链接时出错: {str(e)}")
        
        return links
    
    def get_page_images(self, soup: BeautifulSoup, base_url: str) -> list:
        """
        获取页面中的所有图片
        
        Args:
            soup: BeautifulSoup对象
            base_url: 基础URL
            
        Returns:
            图片信息列表
        """
        images = []
        
        try:
            # 查找img标签
            img_tags = soup.find_all('img')
            
            for img_tag in img_tags:
                src = img_tag.get('src', '').strip()
                if not src:
                    # 检查data-src等懒加载属性
                    src = (img_tag.get('data-src') or 
                           img_tag.get('data-original') or 
                           img_tag.get('data-lazy-src', '')).strip()
                
                if not src:
                    continue
                
                # 转换为绝对URL
                absolute_url = urljoin(base_url, src)
                
                # 提取图片信息
                img_info = {
                    'url': absolute_url,
                    'alt': img_tag.get('alt', ''),
                    'title': img_tag.get('title', ''),
                    'width': self._parse_dimension(img_tag.get('width')),
                    'height': self._parse_dimension(img_tag.get('height')),
                    'class': img_tag.get('class', []),
                    'original_src': src
                }
                
                images.append(img_info)
                
        except Exception as e:
            self.logger.warning(f"提取页面图片时出错: {str(e)}")
        
        return images
    
    def _parse_dimension(self, value: str) -> int:
        """解析尺寸值"""
        if not value:
            return 0
        
        try:
            # 移除px等单位
            value = str(value).lower().replace('px', '').strip()
            return int(float(value))
        except:
            return 0
    
    def close(self):
        """关闭会话"""
        if hasattr(self, 'session'):
            self.session.close()