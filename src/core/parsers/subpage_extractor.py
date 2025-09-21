"""
子页面提取器
负责从页面中提取子页面链接
"""

import re
from typing import List, Dict, Any, Optional, Set
from urllib.parse import urljoin, urlparse, parse_qs

from .base_parser import BaseParser, SubPageInfo, ParseResult, ParserMixin
from .parser_exceptions import ParseError, ValidationError
from .parser_config import ParserConfig


class SubPageExtractor(BaseParser, ParserMixin):
    """子页面提取器"""
    
    def __init__(self, config: Optional[ParserConfig] = None):
        """
        初始化子页面提取器
        
        Args:
            config: 解析器配置
        """
        super().__init__(config.to_dict() if config else {})
        self.config_obj = config or ParserConfig()
        
        # 分页链接模式
        self.pagination_patterns = [
            r'next',
            r'下一页',
            r'more',
            r'继续',
            r'page\s*\d+',
            r'第\s*\d+\s*页',
            r'>\s*$',
            r'»',
            r'→'
        ]
        
        # 编译正则表达式
        self.compiled_patterns = [re.compile(pattern, re.IGNORECASE) 
                                for pattern in self.pagination_patterns]
    
    def parse(self, content: Any, options: Optional[Dict[str, Any]] = None) -> ParseResult:
        """
        从页面中提取子页面链接
        
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
            
            # 提取子页面链接
            subpages = []
            
            # 提取分页链接
            pagination_links = self.extract_pagination_links(soup, base_url)
            subpages.extend(pagination_links)
            
            # 提取相关页面链接
            related_links = self.extract_related_links(soup, base_url)
            subpages.extend(related_links)
            
            # 提取目录页面链接
            category_links = self.extract_category_links(soup, base_url)
            subpages.extend(category_links)
            
            # 去重和过滤
            unique_subpages = self.deduplicate_and_filter(subpages, base_url)
            
            # 转换为SubPageInfo对象
            for subpage_data in unique_subpages:
                subpage_info = SubPageInfo(
                    url=subpage_data['url'],
                    title=subpage_data.get('title', ''),
                    link_text=subpage_data.get('link_text', ''),
                    page_type=subpage_data.get('page_type', 'unknown'),
                    priority=subpage_data.get('priority', 1),
                    source_page=base_url,
                    metadata=subpage_data.get('metadata', {})
                )
                result.subpages.append(subpage_info)
            
            self.logger.info(f"从页面提取到 {len(result.subpages)} 个子页面链接")
            
        except Exception as e:
            error_msg = f"子页面提取失败: {str(e)}"
            result.add_error(error_msg)
            self.handle_error(e, "子页面提取")
        
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
    
    def extract_pagination_links(self, soup: Any, base_url: str) -> List[Dict[str, Any]]:
        """
        提取分页链接
        
        Args:
            soup: BeautifulSoup对象
            base_url: 基础URL
            
        Returns:
            分页链接列表
        """
        links = []
        
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
                    
                    link_text = a_tag.get_text().strip()
                    title = str(a_tag.get('title', ''))
                    
                    # 检查是否为分页链接
                    if self.is_pagination_link(link_text, title, href):
                        absolute_url = urljoin(base_url, href)
                        
                        if self.is_valid_url(absolute_url) and self.is_same_domain(absolute_url, base_url):
                            links.append({
                                'url': absolute_url,
                                'title': title,
                                'link_text': link_text,
                                'page_type': 'pagination',
                                'priority': self.get_pagination_priority(link_text, title),
                                'original_href': href,
                                'metadata': {
                                    'class': str(a_tag.get('class', '')),
                                    'id': str(a_tag.get('id', ''))
                                }
                            })
                except:
                    continue
                    
        except Exception as e:
            self.logger.warning(f"提取分页链接时出错: {str(e)}")
        
        return links
    
    def extract_related_links(self, soup: Any, base_url: str) -> List[Dict[str, Any]]:
        """
        提取相关页面链接
        
        Args:
            soup: BeautifulSoup对象
            base_url: 基础URL
            
        Returns:
            相关链接列表
        """
        links = []
        
        try:
            # 查找相关内容区域
            related_selectors = [
                '.related',
                '.similar',
                '.recommend',
                '.more',
                '#related',
                '#similar',
                '#recommend',
                '[class*="related"]',
                '[class*="similar"]',
                '[class*="recommend"]'
            ]
            
            for selector in related_selectors:
                try:
                    elements = soup.select(selector)
                    for element in elements:
                        element_links = self.extract_links_from_element(element, base_url, 'related')
                        links.extend(element_links)
                except:
                    continue
                    
        except Exception as e:
            self.logger.warning(f"提取相关链接时出错: {str(e)}")
        
        return links
    
    def extract_category_links(self, soup: Any, base_url: str) -> List[Dict[str, Any]]:
        """
        提取目录页面链接
        
        Args:
            soup: BeautifulSoup对象
            base_url: 基础URL
            
        Returns:
            目录链接列表
        """
        links = []
        
        try:
            # 查找导航和目录区域
            nav_selectors = [
                'nav',
                '.nav',
                '.navigation',
                '.menu',
                '.category',
                '.categories',
                '#nav',
                '#navigation',
                '#menu',
                '[class*="nav"]',
                '[class*="menu"]',
                '[class*="category"]'
            ]
            
            for selector in nav_selectors:
                try:
                    elements = soup.select(selector)
                    for element in elements:
                        element_links = self.extract_links_from_element(element, base_url, 'category')
                        links.extend(element_links)
                except:
                    continue
                    
        except Exception as e:
            self.logger.warning(f"提取目录链接时出错: {str(e)}")
        
        return links
    
    def extract_links_from_element(self, element: Any, base_url: str, page_type: str) -> List[Dict[str, Any]]:
        """
        从元素中提取链接
        
        Args:
            element: HTML元素
            base_url: 基础URL
            page_type: 页面类型
            
        Returns:
            链接列表
        """
        links = []
        
        try:
            a_tags = element.find_all('a', href=True)
            
            for a_tag in a_tags:
                try:
                    href = a_tag.get('href', '')
                    if not href or not isinstance(href, str):
                        continue
                    
                    href = href.strip()
                    if not href:
                        continue
                    
                    link_text = a_tag.get_text().strip()
                    title = str(a_tag.get('title', ''))
                    
                    absolute_url = urljoin(base_url, href)
                    
                    if (self.is_valid_url(absolute_url) and 
                        self.is_same_domain(absolute_url, base_url) and
                        not self.is_current_page(absolute_url, base_url)):
                        
                        links.append({
                            'url': absolute_url,
                            'title': title,
                            'link_text': link_text,
                            'page_type': page_type,
                            'priority': self.get_link_priority(page_type, link_text),
                            'original_href': href,
                            'metadata': {
                                'class': str(a_tag.get('class', '')),
                                'id': str(a_tag.get('id', ''))
                            }
                        })
                except:
                    continue
                    
        except Exception as e:
            self.logger.warning(f"从元素提取链接时出错: {str(e)}")
        
        return links
    
    def is_pagination_link(self, link_text: str, title: str, href: str) -> bool:
        """
        检查是否为分页链接
        
        Args:
            link_text: 链接文本
            title: 标题
            href: 链接地址
            
        Returns:
            是否为分页链接
        """
        # 检查文本内容
        text_to_check = f"{link_text} {title}".lower()
        
        for pattern in self.compiled_patterns:
            if pattern.search(text_to_check):
                return True
        
        # 检查URL参数
        try:
            parsed_url = urlparse(href)
            query_params = parse_qs(parsed_url.query)
            
            # 常见的分页参数
            page_params = ['page', 'p', 'pagenum', 'pageindex', 'offset', 'start']
            for param in page_params:
                if param in query_params:
                    return True
                    
        except:
            pass
        
        return False
    
    def get_pagination_priority(self, link_text: str, title: str) -> int:
        """
        获取分页链接的优先级
        
        Args:
            link_text: 链接文本
            title: 标题
            
        Returns:
            优先级（数字越大优先级越高）
        """
        text_to_check = f"{link_text} {title}".lower()
        
        # 下一页优先级最高
        if any(keyword in text_to_check for keyword in ['next', '下一页', '下一', 'more']):
            return 10
        
        # 数字页码
        if re.search(r'\d+', text_to_check):
            return 5
        
        # 其他分页链接
        return 3
    
    def get_link_priority(self, page_type: str, link_text: str) -> int:
        """
        获取链接优先级
        
        Args:
            page_type: 页面类型
            link_text: 链接文本
            
        Returns:
            优先级
        """
        if page_type == 'pagination':
            return 10
        elif page_type == 'related':
            return 7
        elif page_type == 'category':
            return 5
        else:
            return 1
    
    def deduplicate_and_filter(self, subpages: List[Dict[str, Any]], base_url: str) -> List[Dict[str, Any]]:
        """
        去重和过滤子页面
        
        Args:
            subpages: 子页面列表
            base_url: 基础URL
            
        Returns:
            过滤后的子页面列表
        """
        seen_urls: Set[str] = set()
        unique_subpages = []
        
        # 按优先级排序
        subpages.sort(key=lambda x: x.get('priority', 0), reverse=True)
        
        for subpage in subpages:
            url = subpage.get('url', '')
            if not url:
                continue
            
            # 规范化URL（移除fragment）
            normalized_url = self.normalize_url(url)
            
            if normalized_url not in seen_urls:
                seen_urls.add(normalized_url)
                
                # 应用过滤规则
                if self.should_include_subpage(subpage, base_url):
                    unique_subpages.append(subpage)
        
        return unique_subpages
    
    def should_include_subpage(self, subpage: Dict[str, Any], base_url: str) -> bool:
        """
        检查是否应该包含子页面
        
        Args:
            subpage: 子页面信息
            base_url: 基础URL
            
        Returns:
            是否包含
        """
        url = subpage.get('url', '')
        link_text = subpage.get('link_text', '').lower()
        
        # 排除的链接文本
        excluded_texts = [
            'login', 'logout', 'register', 'signup', 'signin',
            '登录', '注册', '退出', '登出',
            'contact', 'about', 'privacy', 'terms',
            '联系', '关于', '隐私', '条款',
            'rss', 'feed', 'xml',
            'print', '打印',
            'share', '分享',
            'bookmark', '收藏'
        ]
        
        for excluded in excluded_texts:
            if excluded in link_text:
                return False
        
        # 排除的URL模式
        excluded_patterns = [
            r'#',  # 锚点链接
            r'javascript:',  # JavaScript链接
            r'mailto:',  # 邮件链接
            r'tel:',  # 电话链接
            r'\.(pdf|doc|docx|xls|xlsx|zip|rar)$',  # 文档文件
        ]
        
        for pattern in excluded_patterns:
            if re.search(pattern, url, re.IGNORECASE):
                return False
        
        return True
    
    def is_current_page(self, url: str, base_url: str) -> bool:
        """
        检查是否为当前页面
        
        Args:
            url: 要检查的URL
            base_url: 当前页面URL
            
        Returns:
            是否为当前页面
        """
        try:
            normalized_url = self.normalize_url(url)
            normalized_base = self.normalize_url(base_url)
            return normalized_url == normalized_base
        except:
            return False
    
    def normalize_url(self, url: str) -> str:
        """
        规范化URL
        
        Args:
            url: 原始URL
            
        Returns:
            规范化后的URL
        """
        try:
            parsed = urlparse(url)
            # 移除fragment和一些查询参数
            normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
            if parsed.query:
                # 保留重要的查询参数
                query_params = parse_qs(parsed.query)
                important_params = {}
                for key, values in query_params.items():
                    if key.lower() in ['page', 'p', 'id', 'category', 'tag']:
                        important_params[key] = values[0]
                
                if important_params:
                    from urllib.parse import urlencode
                    normalized += '?' + urlencode(important_params)
            
            return normalized
        except:
            return url