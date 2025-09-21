#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
网页解析器模块 - 重新开发版本
符合Python 3.9+规范，包含完整的类型注解和智能图片过滤系统
"""

import re
import os
import logging
import time
import random
import threading
from typing import List, Dict, Set, Optional, Any, Tuple
from urllib.parse import urljoin, urlparse, parse_qs
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from bs4 import BeautifulSoup

from src.models.data_models import ImageInfo, PageInfo
from src.core.config import Config
from src.utils.url_utils import UrlUtils


class WebPageParser:
    """极速版网页解析器 - 专注于从起始页提取子页面和图片"""
    
    def __init__(self, config: Config):
        """
        初始化解析器
        
        Args:
            config: 应用配置对象
        """
        self.config = config
        self.logger = logging.getLogger(__name__)
        self._init_session()
        
    def _init_session(self) -> None:
        """初始化会话"""
        self.session = requests.Session()
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.8,en-US;q=0.5,en;q=0.3',
            'Accept-Encoding': 'gzip, deflate',
        }
        self.session.headers.update(headers)
        # 超时时间将在具体请求中设置
        
        # 已访问页面集合
        self.visited_pages: Set[str] = set()
        
    def parse_page(self, url: str, max_depth: int = 1) -> PageInfo:
        """
        解析单个页面 - 极速版
        
        Args:
            url: 页面URL
            max_depth: 最大解析深度，默认为1
            
        Returns:
            页面信息对象
        """
        self.logger.info(f"开始解析页面: {url}")
        
        try:
            # 获取页面内容
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # 提取子页面
            sub_pages = self._extract_sub_pages(soup, url)
            
            # 提取图片
            images = self._extract_images(soup, url)
            
            # 创建页面信息
            page_info = PageInfo(
                url=url,
                title=soup.title.string if soup.title else "",
                images=images,
                sub_pages=sub_pages,
                parsed=True
            )
            
            self.logger.info(f"页面解析完成: {url}, 找到 {len(images)} 张图片, {len(sub_pages)} 个子页面")
            return page_info
            
        except Exception as e:
            self.logger.error(f"页面解析失败: {url} - {e}")
            return PageInfo(url=url, parsed=False, error_message=str(e))
        

    
    def _fetch_page_content(self, url: str) -> Optional[str]:
        """
        获取页面内容
        
        Args:
            url: 页面URL
            
        Returns:
            HTML内容或None
        """
        for attempt in range(3):  # 固定重试次数
            try:
                response = self.session.get(
                    url, 
                    timeout=30,
                    allow_redirects=True
                )
                
                # 处理429状态码
                if response.status_code == 429:
                    wait_time = 2 ** attempt + random.uniform(0.5, 1.5)
                    self.logger.info(f"收到429状态码，等待 {wait_time:.2f}秒后重试")
                    time.sleep(wait_time)
                    continue
                
                response.raise_for_status()
                
                # 检测编码
                if response.encoding == 'ISO-8859-1':
                    response.encoding = response.apparent_encoding or 'utf-8'
                
                return response.text
                
            except requests.RequestException as e:
                wait_time = 2 ** attempt + random.uniform(0.5, 1.5)
                self.logger.warning(f"获取页面失败 (尝试 {attempt + 1}/3): {e}")
                
                if attempt < 2:  # 固定重试次数
                    time.sleep(wait_time)
                else:
                    self.logger.error(f"获取页面最终失败: {url}")
        
        return None
    
    def _extract_page_title(self, soup: BeautifulSoup) -> Optional[str]:
        """提取页面标题"""
        title_tag = soup.find('title')
        return title_tag.get_text().strip() if title_tag else None
    
    def _extract_page_description(self, soup: BeautifulSoup) -> Optional[str]:
        """提取页面描述"""
        from bs4 import Tag
        
        # 查找meta描述
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if isinstance(meta_desc, Tag) and meta_desc.has_attr('content'):
            content = meta_desc.get('content')
            if content and isinstance(content, str):
                return content.strip()
        
        # 查找Open Graph描述
        og_desc = soup.find('meta', attrs={'property': 'og:description'})
        if isinstance(og_desc, Tag) and og_desc.has_attr('content'):
            content = og_desc.get('content')
            if content and isinstance(content, str):
                return content.strip()
        
        return None
    
    def _extract_images(self, soup: BeautifulSoup, base_url: str) -> List[ImageInfo]:
        """
        提取页面中的图片
        
        Args:
            soup: BeautifulSoup对象
            base_url: 基础URL
            
        Returns:
            图片信息列表
        """
        images: List[ImageInfo] = []
        seen_urls: Set[str] = set()
        
        # 查找所有img标签
        img_tags = soup.find_all('img')
        self.logger.info(f"找到 {len(img_tags)} 个img标签")
        
        # 调试：记录所有找到的img标签
        for i, img_tag in enumerate(img_tags[:10]):  # 只记录前10个
            src = img_tag.get('src', '')
            data_src = img_tag.get('data-src', '')
            self.logger.debug(f"Img {i+1}: src='{src}', data-src='{data_src}'")
        
        for img_tag in img_tags:
            try:
                # 获取图片URL
                img_url = self._get_image_url(img_tag, base_url)
                if not img_url:
                    continue
                
                if img_url in seen_urls:
                    self.logger.debug(f"跳过重复URL: {img_url}")
                    continue
                
                seen_urls.add(img_url)
                
                # 检查URL有效性
                if not self._is_valid_image_url(img_url):
                    self.logger.debug(f"无效图片URL: {img_url}")
                    continue
                
                # 创建图片信息
                image_info = self._create_image_info(img_url, img_tag)
                if image_info:
                    images.append(image_info)
                    self.logger.debug(f"添加图片: {image_info.filename}")
                else:
                    self.logger.debug(f"创建图片信息失败: {img_url}")
                    
            except Exception as e:
                self.logger.warning(f"处理图片标签失败: {e}")
                continue
        
        self.logger.info(f"提取到 {len(images)} 张原始图片")
        
        # 过滤图片
        filtered_images = self._filter_images(images)
        self.logger.info(f"图片过滤完成: {len(images)} -> {len(filtered_images)}")
        
        return filtered_images
    
    def _get_image_url(self, img_tag: Any, base_url: str) -> Optional[str]:
        """获取图片URL"""
        # 尝试多个可能的属性
        for attr in ['src', 'data-src', 'data-original', 'data-lazy-src']:
            img_url = img_tag.get(attr)
            if img_url:
                # 转换为绝对URL
                absolute_url = urljoin(base_url, img_url)
                if self._is_valid_image_url(absolute_url):
                    return absolute_url
        
        return None
    
    def _is_valid_image_url(self, url: str) -> bool:
        """检查是否为有效的图片URL"""
        try:
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                return False
            
            # 检查文件扩展名
            path = parsed.path.lower()
            allowed_types = ['jpg', 'jpeg', 'png', 'webp', 'gif']
            if allowed_types:
                allowed_exts = [f'.{ext}' for ext in allowed_types]
                if any(path.endswith(ext) for ext in allowed_exts):
                    return True
                
                # 检查URL参数中是否包含图片格式
                if any(ext in url.lower() for ext in allowed_types):
                    return True
            
            # 对于没有扩展名的URL，也允许通过（可能是动态生成的图片）
            # 后续的图片过滤会进一步筛选
            if '.' not in os.path.basename(path):
                return True
            
            return False
            
        except Exception:
            return False
    
    def _create_image_info(self, img_url: str, img_tag: Any) -> Optional[ImageInfo]:
        """创建图片信息对象"""
        try:
            # 提取文件名
            filename = UrlUtils.extract_filename_from_url(img_url)
            if not filename:
                return None
            
            # 获取文件类型
            file_type = filename.split('.')[-1].lower() if '.' in filename else 'jpg'
            
            # 获取尺寸信息
            width = height = None
            try:
                width = int(img_tag.get('width', 0)) or None
                height = int(img_tag.get('height', 0)) or None
            except (ValueError, TypeError):
                pass
            
            return ImageInfo(
                url=img_url,
                filename=filename,
                file_path="",  # 稍后设置
                file_type=file_type,
                width=width,
                height=height
            )
            
        except Exception as e:
            self.logger.warning(f"创建图片信息失败: {img_url} - {e}")
            return None
    
    def _filter_images(self, images: List[ImageInfo]) -> List[ImageInfo]:
        """
        过滤图片 - 三级过滤系统
        
        Args:
            images: 原始图片列表
            
        Returns:
            过滤后的图片列表
        """
        filtered_images: List[ImageInfo] = []
        
        for image in images:
            # 第一级过滤：文件名特征过滤
            if self._passes_filename_filter(image):
                # 第二级过滤：URL模式过滤（区分大图小图）
                if self._is_large_image(image):
                    # 第三级过滤：尺寸过滤
                    if self._passes_size_filter(image):
                        filtered_images.append(image)
                    else:
                        self.logger.debug(f"图片尺寸过滤: {image.filename}")
                else:
                    self.logger.debug(f"图片URL模式过滤（小图）: {image.filename}")
            else:
                self.logger.debug(f"图片文件名过滤: {image.filename}")
        
        return filtered_images
    
    def _is_large_image(self, image: ImageInfo) -> bool:
        """
        判断是否为大型图片（写真大图）
        
        Args:
            image: 图片信息
            
        Returns:
            是否为大型图片
        """
        url = image.url.lower()
        filename = image.filename.lower()
        
        # 大图的特征模式（高优先级）
        large_image_patterns = [
            r'/uploadfile/\d{4,6}/\d{1,4}/', # /uploadfile/2017/04/ 或 /uploadfile/202509/17/ 格式 - 这是大图！
            r'/uploadfile/\d{4,6}/\d{1,4}/[^/]+\.[a-zA-Z]+$', # /uploadfile/202509/17/A010348513.jpg 格式
            r'\.webp$',                    # webp格式通常是大图
            r'\.jpg$',                     # jpg格式
            r'\.jpeg$',                    # jpeg格式
            r'\.png$',                     # png格式
            r'large',                      # 包含large关键词
            r'big',                        # 包含big关键词
            r'original',                   # 包含original关键词
            r'full'                        # 包含full关键词
        ]
        
        # 小图的特征模式（需要排除）
        small_image_patterns = [
            r'\.gif$',                     # gif通常是图标
            r'thumb',                      # 缩略图
            r'small',                      # 小图
            r'icon',                       # 图标
            r'logo',                       # logo
            r'btn',                        # 按钮
            r'button',                     # 按钮
            r'nav',                        # 导航
            r'menu',                       # 菜单
            r'ad',                         # 广告
            r'banner',                     # 横幅
            r'_s\.',                       # _s. 后缀表示小图
            r'_m\.',                       # _m. 后缀表示中图
            r'_t\.',                       # _t. 后缀表示缩略图
            r'mm\d+\.'                     # mm01.jpg, mm02.jpg 等导航图片
        ]
        
        # 特殊规则：/pic/目录下的图片需要进一步判断
        if '/pic/' in url:
            # /pic/目录下的数字文件名可能是大图（如33595.jpg）
            if re.search(r'/pic/\d+\.(jpg|jpeg|png|webp)$', url):
                return True
            return False
        
        # 特殊规则：/uploadfile/目录下的webp图片都是大图
        if '/uploadfile/' in url and url.endswith('.webp'):
            return True
        
        # 检查是否匹配大图模式
        is_large = any(re.search(pattern, url) for pattern in large_image_patterns)
        
        # 检查是否匹配小图模式
        is_small = any(re.search(pattern, url) for pattern in small_image_patterns)
        
        # 调试信息
        if is_large and is_small:
            self.logger.debug(f"图片同时匹配大图和小图模式: {url}")
        
        # 特殊规则：/uploadfile/目录下的图片优先认为是大图
        if '/uploadfile/' in url:
            # 除非明确匹配小图模式（排除ad等误判）
            uploadfile_small_patterns = [
                r'\.gif$',                     # gif通常是图标
                r'thumb',                      # 缩略图
                r'small',                      # 小图
                r'icon',                       # 图标
                r'logo',                       # logo
                r'btn',                        # 按钮
                r'button',                     # 按钮
                r'nav',                        # 导航
                r'menu',                       # 菜单
                r'banner',                     # 横幅
                r'_s\.',                       # _s. 后缀表示小图
                r'_m\.',                       # _m. 后缀表示中图
                r'_t\.',                       # _t. 后缀表示缩略图
                r'mm\d+\.'                     # mm01.jpg, mm02.jpg 等导航图片
            ]
            # 对于/uploadfile/目录，只检查特定的几个小图模式
            is_uploadfile_small = any(re.search(pattern, url) for pattern in uploadfile_small_patterns)
            if not is_uploadfile_small:
                return True
        
        # 优先规则：如果匹配大图模式，除非明确是小图模式，否则认为是大图
        if is_large:
            return not is_small
        
        # 默认情况下，认为是大图（让后续的尺寸过滤来处理）
        return True
    
    def _passes_filename_filter(self, image: ImageInfo) -> bool:
        """第一级过滤：文件名特征过滤"""
        filename = image.filename.lower()
        
        # 检查装饰性模式
        decorative_patterns = ['logo', 'icon', 'btn', 'button', 'nav', 'menu', 'ad', 'banner']
        if decorative_patterns:
            for pattern in decorative_patterns:
                if pattern.lower() in filename:
                    self.logger.debug(f"过滤装饰性图片: {filename} (模式: {pattern})")
                    return False
        
        # 排除常见的小图标和装饰元素
        decorative_keywords = ['logo', 'icon', 'btn', 'button', 'nav', 'menu', 'ad', 'banner']
        if any(keyword in filename for keyword in decorative_keywords):
            self.logger.debug(f"过滤装饰性图片: {filename}")
            return False
        
        return True
    
    def _passes_size_filter(self, image: ImageInfo) -> bool:
        """第二级过滤：尺寸过滤"""
        # 尺寸过滤默认启用
        enable_size_filter = True
        min_width = 800
        min_height = 600
        
        if not enable_size_filter:
            return True
        
        # 如果已有尺寸信息，直接检查
        if image.width and image.height:
            if (image.width < min_width or 
                image.height < min_height):
                return False
        
        # 对于没有尺寸信息的图片，需要获取实际尺寸
        # 这里可以添加HEAD请求获取图片信息，但为了性能考虑，可以留到下载阶段再验证
        return True
    
    def _extract_relative_links(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        """
        专门提取相对路径链接并构建完整URL
        处理类似 /MiStar/MiStar17430.html 这样的相对路径模式
        
        Args:
            soup: BeautifulSoup对象
            base_url: 基础URL
            
        Returns:
            有效的子页面URL列表
        """
        sub_pages: List[str] = []
        seen_urls: Set[str] = set()
        
        # 查找所有相对路径链接
        all_links = soup.find_all('a', href=True)
        
        for link in all_links:
            try:
                href = link.get('href', '')
                if not href:
                    continue
                
                # 只处理相对路径链接（以/开头但不包含协议）
                if href.startswith('/') and not href.startswith('//') and '://' not in href:
                    # 转换为绝对URL
                    full_url = urljoin(base_url, href)
                    
                    # 检查是否为有效的子页面链接
                    if (full_url not in seen_urls and 
                        self._is_valid_subpage_link(full_url) and
                        self._is_container_subpage_link(full_url, base_url)):
                        
                        sub_pages.append(full_url)
                        seen_urls.add(full_url)
                        self.logger.info(f"从相对路径添加子页面: {full_url}")
                        
            except Exception as e:
                self.logger.warning(f"处理相对路径链接失败: {e}")
                continue
        
        self.logger.info(f"从相对路径提取到 {len(sub_pages)} 个有效子页面")
        return sub_pages

    def _extract_sub_pages(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        """
        提取子页面链接 - 优先从container区域提取有效子页面
        
        Args:
            soup: BeautifulSoup对象
            base_url: 基础URL
            
        Returns:
            子页面URL列表
        """
        sub_pages: List[str] = []
        seen_urls: Set[str] = set()
        
        # 1. 首先从container区域提取子页面链接（最高优先级）
        container_sub_pages = self._extract_sub_pages_from_container(soup, base_url)
        for url in container_sub_pages:
            if url not in seen_urls:
                sub_pages.append(url)
                seen_urls.add(url)
        
        # 2. 查找分页区域（次优先级）
        pagination = soup.find('div', class_='pagination')
        if not pagination:
            pagination = soup.find('ul', class_='pagination')
        if not pagination:
            pagination = soup.find('div', id='pagination')
        
        if pagination:
            self.logger.info("找到分页区域，提取分页链接")
            from bs4 import Tag
            if isinstance(pagination, Tag):
                pagination_links = pagination.find_all('a', href=True)
            else:
                pagination_links = []
            for link in pagination_links:
                try:
                    href = link['href']
                    # 跳过当前页和"下一页"链接
                    if 'current' in link.get('class', []) or '下一页' in link.get_text():
                        continue
                    
                    full_url = urljoin(base_url, href)
                    if full_url not in seen_urls and self._is_valid_subpage_link(full_url):
                        sub_pages.append(full_url)
                        seen_urls.add(full_url)
                        self.logger.debug(f"添加分页链接: {full_url}")
                except Exception as e:
                    self.logger.warning(f"处理分页链接失败: {e}")
        
        # 3. 专门提取相对路径链接并构建完整URL
        relative_links_sub_pages = self._extract_relative_links(soup, base_url)
        for url in relative_links_sub_pages:
            if url not in seen_urls:
                sub_pages.append(url)
                seen_urls.add(url)
        
        # 4. 如果链接不足，查找其他可能的子页面链接
        if len(sub_pages) < 5:
            self.logger.info("链接不足，查找其他子页面链接")
            all_links = soup.find_all('a', href=True)
            base_domain = urlparse(base_url).netloc
            
            for link in all_links:
                try:
                    href = link['href']
                    full_url = urljoin(base_url, href)
                    
                    # 检查是否为同域名且未访问过
                    if (self._is_same_domain(full_url, base_domain) and 
                        full_url not in seen_urls and
                        self._is_potential_subpage(full_url, base_url) and
                        self._is_valid_subpage_link(full_url)):
                        
                        sub_pages.append(full_url)
                        seen_urls.add(full_url)
                        
                except Exception as e:
                    self.logger.warning(f"处理链接失败: {e}")
                    continue
        
        # 去重和排序
        unique_sub_pages = list(set(sub_pages))
        unique_sub_pages.sort()
        
        self.logger.info(f"找到 {len(unique_sub_pages)} 个子页面")
        return unique_sub_pages
    
    def _is_same_domain(self, url: str, base_domain: str) -> bool:
        """检查是否为同一域名"""
        try:
            parsed = urlparse(url)
            return parsed.netloc == base_domain
        except Exception:
            return False
    
    def _is_potential_subpage(self, url: str, base_url: str) -> bool:
        """检查是否为潜在的子页面"""
        try:
            # 排除非HTML页面
            if not self._is_html_page(url):
                return False
            
            # 排除当前页面
            if url == base_url:
                return False
            
            # 检查是否为数字序列页面模式
            if self._is_numbered_page(url, base_url):
                return True
            
            # 检查路径相似性
            parsed_base = urlparse(base_url)
            parsed_target = urlparse(url)
            
            base_dir = os.path.dirname(parsed_base.path)
            target_dir = os.path.dirname(parsed_target.path)
            
            # 同目录或子目录
            if target_dir.startswith(base_dir) or base_dir.startswith(target_dir):
                return True
            
            return False
            
        except Exception:
            return False
    
    def _is_potential_subpage(self, url: str, base_url: str) -> bool:
        """
        检查是否为潜在的有效子页面
        
        Args:
            url: 待检查的URL
            base_url: 基础URL
            
        Returns:
            是否为有效的子页面
        """
        try:
            parsed_url = urlparse(url)
            parsed_base = urlparse(base_url)
            
            # 检查域名是否相同
            if parsed_url.netloc != parsed_base.netloc:
                return False
            
            # 检查是否为HTML页面
            if not self._is_html_page(url):
                return False
            
            # 检查路径相似性
            base_path = parsed_base.path
            target_path = parsed_url.path
            
            # 如果是数字序列页面，检查数字是否在合理范围内
            if self._is_numbered_page(url, base_url):
                # 提取数字
                numbers = re.findall(r'\d+', target_path)
                if numbers:
                    last_number = int(numbers[-1])
                    # 只接受2-22范围内的数字（基于用户反馈）
                    if 2 <= last_number <= 22:
                        return True
                    return False
            
            # 检查路径相似性
            base_dir = os.path.dirname(base_path)
            target_dir = os.path.dirname(target_path)
            
            # 同目录或子目录
            if target_dir.startswith(base_dir) or base_dir.startswith(target_dir):
                return True
            
            return False
            
        except Exception:
            return False
    
    def _is_valid_subpage_link(self, url: str) -> bool:
        """
        检查是否为有效的子页面链接
        排除广告链接和非图片页面链接
        
        Args:
            url: 待检查的URL
            
        Returns:
            是否为有效的子页面链接
        """
        try:
            # 排除已知的广告域名和无效链接
            invalid_patterns = [
                # 移除对876512.xyz域名的过滤，因为这是主网站
                r'ad\.',
                r'banner\.',
                r'ads\.',
                r'analytics\.',
                r'tracking\.',
                r'click\.',
                r'redirect\.',
                r'promo\.',
                r'sponsor\.',
                r'affiliate\.',
                r'partner\.'
            ]
            
            # 检查是否匹配无效模式
            for pattern in invalid_patterns:
                if re.search(pattern, url, re.IGNORECASE):
                    # 特殊处理：如果URL包含广告域名但路径是有效的图片页面，仍然允许
                    parsed = urlparse(url)
                    path = parsed.path.lower()
                    
                    # 检查是否为有效的图片页面路径
                    image_patterns = [
                        r'^/xiuren/xiuren\d+\.html$',
                        r'^/xgyw/xgyw\d+\.html$',
                        r'^/legbaby/legbaby\d+\.html$',
                        r'^/huayang/huayang\d+\.html$',
                        r'^/youwu/youwu\d+\.html$',
                        r'^/missleg/missleg\d+\.html$',
                        r'^/tuigirl/tuigirl\d+\.html$',
                        r'^/mistar/mistar\d+\.html$',    # 新增MiStar模式
                        r'^/aiyouwu/aiyouwu\d+\.html$',  # 新增Aiyouwu模式
                        r'/\w+\d+\.html$',
                        r'/\w+\d+_\d+\.html$'
                    ]
                    
                    # 如果路径匹配图片页面模式，即使域名是广告域名也允许
                    if any(re.search(pattern, path) for pattern in image_patterns):
                        self.logger.debug(f"允许广告域名中的有效图片链接: {url}")
                        return True
                    
                    self.logger.debug(f"过滤广告链接: {url}")
                    return False
            
            # 检查是否为HTML页面（只处理HTML页面）
            if not self._is_html_page(url):
                return False
            
            # 检查URL路径，排除非图片相关页面
            parsed = urlparse(url)
            path = parsed.path.lower()
            
            # 排除非图片相关的路径
            non_image_paths = [
                '/ads/', '/ad/', '/banner/', '/sponsor/', '/affiliate/',
                '/analytics/', '/tracking/', '/click/', '/redirect/',
                '/promo/', '/partner/', '/external/', '/out/'
            ]
            
            if any(non_path in path for non_path in non_image_paths):
                return False
            
            # 检查是否为数字序列页面（通常是图片页面）
            if self._is_numbered_page(url, ""):  # 不检查base_url，只检查数字模式
                return True
            
            # 检查路径中是否包含图片相关的关键词
            image_keywords = ['xiuren', 'tuigirl', 'legbaby', 'huayang', 'youwu', 'xgyw', 'missleg', 'mistar', 'aiyouwu']
            if any(keyword in path for keyword in image_keywords):
                return True
            
            # 检查是否为常见的图片页面格式
            image_patterns = [
                r'/\w+\d+\.html$',      # /Xiuren33821.html
                r'/\w+\d+_\d+\.html$',  # /Xiuren33821_1.html
                r'/\w+\d+/$',           # /Xiuren33821/
                r'/\w+\d+_\d+/$',       # /Xiuren33821_1/
                r'/pic/\d+/',           # /pic/33821/
                r'/album/\d+/',         # /album/33821/
                r'/gallery/\d+/',       # /gallery/33821/
                r'/photos/\d+/',        # /photos/33821/
            ]
            
            for pattern in image_patterns:
                if re.search(pattern, path):
                    return True
            
            return False
            
        except Exception:
            return False

    def _is_html_page(self, url: str) -> bool:
        """检查是否为HTML页面"""
        try:
            parsed = urlparse(url)
            path = parsed.path.lower()
            
            # 检查文件扩展名
            html_exts = ['.html', '.htm', '.php', '.asp', '.aspx', '.jsp']
            if any(path.endswith(ext) for ext in html_exts):
                return True
            
            # 没有扩展名或目录形式
            if '.' not in os.path.basename(path) or path.endswith('/'):
                return True
            
            return False
            
        except Exception:
            return False
    
    def _is_numbered_page(self, url: str, base_url: str) -> bool:
        """检查是否为数字序列页面"""
        try:
            parsed_base = urlparse(base_url)
            parsed_target = urlparse(url)
            
            base_path = parsed_base.path
            target_path = parsed_target.path
            
            # 获取基础文件名
            base_name = os.path.splitext(os.path.basename(base_path))[0]
            target_name = os.path.splitext(os.path.basename(target_path))[0]
            
            # 检查数字后缀模式：base_name + "_" + 数字
            if target_name.startswith(base_name + '_'):
                suffix = target_name[len(base_name + '_'):]
                if suffix.isdigit():
                    return True
            
            # 检查直接数字模式：base_name + 数字
            if target_name.startswith(base_name) and len(target_name) > len(base_name):
                suffix = target_name[len(base_name):]
                if suffix.isdigit():
                    return True
            
            return False
            
        except Exception:
            return False
    
    def _extract_sub_pages_from_container(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        """
        从container区域提取子页面链接
        专门处理 <section class="container"> 中的有效子页面
        
        Args:
            soup: BeautifulSoup对象
            base_url: 基础URL
            
        Returns:
            有效的子页面URL列表
        """
        sub_pages: List[str] = []
        seen_urls: Set[str] = set()
        
        # 查找所有container区域
        containers = soup.find_all('section', class_='container')
        if not containers:
            # 也查找其他可能的container类名
            containers = soup.find_all('div', class_='container')
        
        self.logger.info(f"找到 {len(containers)} 个container区域")
        
        for container in containers:
            try:
                # 在container区域内查找所有链接
                links = container.find_all('a', href=True)
                self.logger.info(f"在container中找到 {len(links)} 个链接")
                
                # 调试：记录找到的所有链接
                for i, link in enumerate(links[:10]):  # 只记录前10个
                    href = link.get('href', '')
                    self.logger.debug(f"链接 {i+1}: href='{href}'")
                
                for link in links:
                    try:
                        href = link.get('href', '')
                        if not href:
                            continue
                        
                        # 转换为绝对URL
                        full_url = urljoin(base_url, href)
                        self.logger.debug(f"转换URL: '{href}' -> '{full_url}'")
                        
                        # 检查是否为有效的子页面链接
                        is_valid_subpage = self._is_valid_subpage_link(full_url)
                        is_container_subpage = self._is_container_subpage_link(full_url, base_url)
                        
                        self.logger.debug(f"验证结果: valid_subpage={is_valid_subpage}, container_subpage={is_container_subpage}")
                        
                        if (full_url not in seen_urls and 
                            is_valid_subpage and
                            is_container_subpage):
                            
                            sub_pages.append(full_url)
                            seen_urls.add(full_url)
                            self.logger.info(f"从container添加子页面: {full_url}")
                            
                    except Exception as e:
                        self.logger.warning(f"处理container链接失败: {e}")
                        continue
                        
            except Exception as e:
                self.logger.warning(f"处理container区域失败: {e}")
                continue
        
        self.logger.info(f"从container区域提取到 {len(sub_pages)} 个有效子页面")
        return sub_pages
    
    def _is_container_subpage_link(self, url: str, base_url: str) -> bool:
        """
        检查是否为container区域的有效子页面链接
        专门针对用户提供的HTML结构进行优化
        
        Args:
            url: 待检查的URL（已经是绝对URL）
            base_url: 基础URL
            
        Returns:
            是否为有效的container子页面链接
        """
        try:
            parsed_url = urlparse(url)
            
            # 检查是否为HTML页面
            if not self._is_html_page(url):
                return False
            
            path = parsed_url.path
            
            # 检查是否为有效的图片页面路径模式
            # 匹配类似 /Xiuren/Xiuren33916.html 的格式
            image_page_patterns = [
                r'^/Xiuren/Xiuren\d+\.html$',
                r'^/Xgyw/Xgyw\d+\.html$', 
                r'^/LEGBABY/LEGBABY\d+\.html$',
                r'^/HuaYang/HuaYang\d+\.html$',
                r'^/YouWu/YouWu\d+\.html$',
                r'^/MissLeg/MissLeg\d+\.html$',
                r'^/Tuigirl/Tuigirl\d+\.html$',
                r'^/MiStar/MiStar\d+\.html$',  # 新增MiStar模式
                r'^/Aiyouwu/Aiyouwu\d+\.html$' # 新增Aiyouwu模式
            ]
            
            for pattern in image_page_patterns:
                if re.match(pattern, path):
                    return True
            
            # 检查是否为数字序列页面
            if self._is_numbered_page(url, base_url):
                return True
            
            # 检查路径中是否包含图片相关的关键词
            image_keywords = ['xiuren', 'tuigirl', 'legbaby', 'huayang', 'youwu', 'xgyw', 'missleg', 'mistar', 'aiyouwu']
            path_lower = path.lower()
            if any(keyword in path_lower for keyword in image_keywords):
                # 进一步检查是否为有效的数字格式
                if re.search(r'\d+', path):
                    return True
            
            # 新增：检查是否为相对路径构建的完整URL
            parsed_base = urlparse(base_url)
            if parsed_url.netloc == parsed_base.netloc:
                # 检查路径是否包含常见的图片页面目录结构
                common_image_dirs = ['/Xiuren/', '/Xgyw/', '/LEGBABY/', '/HuaYang/', '/YouWu/', '/MissLeg/', '/Tuigirl/', '/MiStar/', '/Aiyouwu/']
                if any(dir_name in path for dir_name in common_image_dirs):
                    # 检查是否包含数字（通常是图片页面）
                    if re.search(r'\d+', path):
                        return True
            
            return False
            
        except Exception:
            return False
    

    
    def batch_parse_pages(self, urls: List[str], max_workers: int = 5) -> Dict[str, PageInfo]:
        """
        批量解析页面
        
        Args:
            urls: URL列表
            max_workers: 最大并发数
            
        Returns:
            页面信息字典
        """
        results: Dict[str, PageInfo] = {}
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_url = {executor.submit(self.parse_page, url): url for url in urls}
            
            for future in as_completed(future_to_url):
                url = future_to_url[future]
                try:
                    page_info = future.result()
                    results[url] = page_info
                except Exception as e:
                    self.logger.error(f"批量解析页面失败 {url}: {e}")
                    results[url] = PageInfo(url=url, error_message=str(e))
        
        return results
    
    def reset_visited_pages(self) -> None:
        """重置已访问页面集合"""
        self.visited_pages.clear()
        self.logger.debug("已重置页面访问状态")

    def _generate_similar_pages(self, base_url: str, count: int = 20) -> List[str]:
        """
        基于基础URL生成相似的页面URL
        
        Args:
            base_url: 基础URL
            count: 生成的数量
            
        Returns:
            生成的相似页面URL列表
        """
        try:
            parsed = urlparse(base_url)
            path = parsed.path
            
            # 提取基础路径模式
            if '/Xiuren/' in path:
                # Xiuren网站模式：/Xiuren/Xiuren33896_1.html
                pattern_match = re.search(r'/Xiuren/(Xiuren\d+)', path)
                if pattern_match:
                    base_name = pattern_match.group(1)
                    return [f"{parsed.scheme}://{parsed.netloc}/Xiuren/{base_name}_{i}.html" 
                           for i in range(1, count + 1)]
            
            elif '/Xgyw/' in path:
                # Xgyw网站模式
                pattern_match = re.search(r'/Xgyw/(Xgyw\d+)', path)
                if pattern_match:
                    base_name = pattern_match.group(1)
                    return [f"{parsed.scheme}://{parsed.netloc}/Xgyw/{base_name}_{i}.html" 
                           for i in range(1, count + 1)]
            
            elif '/LEGBABY/' in path:
                # LEGBABY网站模式
                pattern_match = re.search(r'/LEGBABY/(LEGBABY\d+)', path)
                if pattern_match:
                    base_name = pattern_match.group(1)
                    return [f"{parsed.scheme}://{parsed.netloc}/LEGBABY/{base_name}_{i}.html" 
                           for i in range(1, count + 1)]
            
            # 通用数字序列模式
            pattern_match = re.search(r'(\d+)(?:\D|$)', path)
            if pattern_match:
                base_number = int(pattern_match.group(1))
                # 替换路径中的数字部分
                base_path = re.sub(r'\d+', str(base_number), path)
                return [f"{parsed.scheme}://{parsed.netloc}{base_path.replace(str(base_number), str(base_number + i))}" 
                       for i in range(count)]
            
            # 如果无法识别模式，返回空列表
            self.logger.warning(f"无法识别URL模式生成相似页面: {base_url}")
            return []
            
        except Exception as e:
            self.logger.error(f"生成相似页面失败: {base_url} - {e}")
            return []


# 单例模式访问
_global_parser: Optional[WebPageParser] = None

def get_global_parser(config: Optional[Config] = None) -> WebPageParser:
    """获取全局解析器实例"""
    global _global_parser
    if _global_parser is None:
        if config is None:
            config = Config()
        _global_parser = WebPageParser(config)
    return _global_parser