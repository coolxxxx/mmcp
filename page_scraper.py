#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
页面爬取与分析工具
功能：
1. 提取指定页面的所有子页面链接
2. 过滤出所有图片资源链接
3. 对提取结果进行有效性验证
"""

import requests
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import re
from typing import List, Dict, Tuple
import logging
from dataclasses import dataclass
import time

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class ScrapeResult:
    """爬取结果数据结构"""
    base_url: str
    subpages: List[str]
    images: List[str]
    validation: Dict[str, Dict[str, bool]]
    stats: Dict[str, int]
    errors: List[str]

class PageScraper:
    """页面爬取与分析工具"""
    
    def __init__(self, user_agent: str = None, timeout: int = 30):
        """
        初始化爬虫
        
        Args:
            user_agent: 自定义User-Agent
            timeout: 请求超时时间(秒)
        """
        self.session = requests.Session()
        self.timeout = timeout
        self.headers = {
            'User-Agent': user_agent or 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        # 图片扩展名白名单
        self.image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'}
        
        # 子页面URL模式
        self.subpage_patterns = [
            r'/\d+\.html$',  # 数字结尾的HTML页面
            r'page-\d+',     # 分页模式
            r'/\d+/?'        # 数字目录
        ]
        self.subpage_regex = [re.compile(p, re.IGNORECASE) for p in self.subpage_patterns]
    
    def scrape_page(self, url: str) -> ScrapeResult:
        """
        爬取并分析指定页面
        
        Args:
            url: 目标URL
            
        Returns:
            ScrapeResult: 包含所有结果的dataclass
        """
        result = ScrapeResult(
            base_url=url,
            subpages=[],
            images=[],
            validation={'subpages': {}, 'images': {}},
            stats={'subpages': 0, 'images': 0, 'valid_subpages': 0, 'valid_images': 0},
            errors=[]
        )
        
        try:
            # 获取页面内容
            soup = self._fetch_page(url)
            if not soup:
                result.errors.append("无法获取页面内容")
                return result
            
            # 提取子页面
            result.subpages = self._extract_subpages(soup, url)
            result.stats['subpages'] = len(result.subpages)
            
            # 提取图片
            result.images = self._extract_images(soup, url)
            result.stats['images'] = len(result.images)
            
            # 验证子页面
            for subpage in result.subpages:
                result.validation['subpages'][subpage] = self._validate_url(subpage)
                if result.validation['subpages'][subpage]:
                    result.stats['valid_subpages'] += 1
            
            # 验证图片
            for img in result.images:
                result.validation['images'][img] = self._validate_image_url(img)
                if result.validation['images'][img]:
                    result.stats['valid_images'] += 1
                    
        except Exception as e:
            logger.error(f"爬取过程中发生错误: {e}")
            result.errors.append(str(e))
        
        return result
    
    def _fetch_page(self, url: str) -> BeautifulSoup:
        """获取页面并返回BeautifulSoup对象"""
        try:
            response = self.session.get(url, headers=self.headers, timeout=self.timeout)
            response.raise_for_status()
            
            # 检查内容类型
            content_type = response.headers.get('Content-Type', '')
            if 'text/html' not in content_type:
                logger.warning(f"非HTML内容: {content_type}")
                return None
                
            return BeautifulSoup(response.text, 'html.parser')
            
        except requests.RequestException as e:
            logger.error(f"请求失败: {e}")
            return None
    
    def _extract_subpages(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        """提取子页面链接"""
        subpages = set()  # 使用集合避免重复
        
        for link in soup.find_all('a', href=True):
            href = link['href'].strip()
            if not href or href.startswith('#'):
                continue
                
            # 构建完整URL
            full_url = urljoin(base_url, href)
            
            # 标准化URL
            normalized_url = self._normalize_url(full_url)
            
            # 检查是否为子页面
            if self._is_potential_subpage(normalized_url, base_url):
                subpages.add(normalized_url)
                
        return sorted(subpages)
    
    def _extract_images(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        """提取图片链接"""
        images = set()
        
        # 从img标签提取
        for img in soup.find_all('img', src=True):
            src = img['src'].strip()
            if src:
                full_url = urljoin(base_url, src)
                if self._is_image_url(full_url):
                    images.add(full_url)
        
        # 从CSS背景提取
        for tag in soup.find_all(style=True):
            style = tag['style']
            urls = re.findall(r'url\(["\']?(.*?)["\']?\)', style)
            for url in urls:
                full_url = urljoin(base_url, url.strip())
                if self._is_image_url(full_url):
                    images.add(full_url)
                    
        return sorted(images)
    
    def _normalize_url(self, url: str) -> str:
        """标准化URL"""
        parsed = urlparse(url)
        
        # 移除查询参数和片段
        clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        
        # 移除末尾的/
        if clean_url.endswith('/'):
            clean_url = clean_url[:-1]
            
        return clean_url.lower()  # 统一小写
    
    def _is_potential_subpage(self, url: str, base_url: str) -> bool:
        """检查是否为潜在的子页面"""
        # 排除非HTTP链接
        if not url.startswith(('http://', 'https://')):
            return False
            
        # 排除非本站链接
        if urlparse(url).netloc != urlparse(base_url).netloc:
            return False
            
        # 检查URL模式
        for pattern in self.subpage_regex:
            if pattern.search(url):
                return True
                
        return False
    
    def _is_image_url(self, url: str) -> bool:
        """检查是否为图片URL"""
        parsed = urlparse(url)
        path = parsed.path.lower()
        
        # 检查扩展名
        if any(path.endswith(ext) for ext in self.image_extensions):
            return True
            
        # 检查常见图片路径模式
        if '/images/' in path or '/img/' in path or '/photo/' in path:
            return True
            
        return False
    
    def _validate_url(self, url: str) -> bool:
        """验证URL有效性"""
        try:
            # 只发送HEAD请求检查
            response = self.session.head(
                url, 
                headers=self.headers,
                timeout=self.timeout,
                allow_redirects=True
            )
            return response.status_code == 200
        except:
            return False
    
    def _validate_image_url(self, url: str) -> bool:
        """验证图片URL有效性"""
        if not self._validate_url(url):
            return False
            
        try:
            # 获取内容类型
            response = self.session.head(
                url,
                headers=self.headers,
                timeout=self.timeout,
                allow_redirects=True
            )
            content_type = response.headers.get('Content-Type', '').lower()
            return any(img_type in content_type for img_type in ['image/jpeg', 'image/png', 'image/gif', 'image/webp'])
        except:
            return False

def generate_report(result: ScrapeResult) -> str:
    """生成结构化报告"""
    report = []
    
    # 基本信息
    report.append(f"=== 页面爬取报告 ===")
    report.append(f"目标URL: {result.base_url}")
    report.append(f"爬取时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 子页面部分
    report.append("\n=== 子页面 ===")
    report.append(f"发现子页面: {result.stats['subpages']} 个")
    report.append(f"有效子页面: {result.stats['valid_subpages']} 个")
    
    if result.subpages:
        report.append("\n子页面列表:")
        for i, subpage in enumerate(result.subpages, 1):
            status = "有效" if result.validation['subpages'].get(subpage, False) else "无效"
            report.append(f"{i}. {subpage} [{status}]")
    
    # 图片部分
    report.append("\n=== 图片资源 ===")
    report.append(f"发现图片: {result.stats['images']} 个")
    report.append(f"有效图片: {result.stats['valid_images']} 个")
    
    if result.images:
        report.append("\n图片列表:")
        for i, img in enumerate(result.images, 1):
            status = "有效" if result.validation['images'].get(img, False) else "无效"
            report.append(f"{i}. {img} [{status}]")
    
    # 错误信息
    if result.errors:
        report.append("\n=== 错误 ===")
        for error in result.errors:
            report.append(f"- {error}")
    
    # 统计信息
    report.append("\n=== 统计 ===")
    report.append(f"子页面有效率: {result.stats['valid_subpages']/result.stats['subpages']*100:.1f}%" if result.stats['subpages'] > 0 else "子页面有效率: N/A")
    report.append(f"图片有效率: {result.stats['valid_images']/result.stats['images']*100:.1f}%" if result.stats['images'] > 0 else "图片有效率: N/A")
    
    return "\n".join(report)

if __name__ == "__main__":
    # 测试目标URL
    TEST_URL = "http://a1.876512.xyz/Xiuren/Xiuren33915.html"
    
    # 创建爬虫实例
    scraper = PageScraper(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        timeout=10
    )
    
    # 执行爬取
    logger.info(f"开始爬取目标页面: {TEST_URL}")
    scrape_result = scraper.scrape_page(TEST_URL)
    
    # 生成并输出报告
    report = generate_report(scrape_result)
    print(report)
    
    # 保存报告到文件
    with open("scrape_report.txt", "w", encoding="utf-8") as f:
        f.write(report)
    
    logger.info("爬取完成，报告已保存到 scrape_report.txt")