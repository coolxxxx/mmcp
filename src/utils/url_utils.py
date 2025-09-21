#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
URL处理工具模块
"""

import re
import os
from urllib.parse import urlparse, unquote
from typing import Optional

class UrlUtils:
    """URL处理工具类"""
    
    @staticmethod
    def extract_filename_from_url(url: str) -> Optional[str]:
        """
        从URL中提取文件名
        
        Args:
            url: URL字符串
            
        Returns:
            文件名，如果无法提取则返回None
        """
        try:
            # 解析URL
            parsed = urlparse(url)
            path = unquote(parsed.path)
            
            # 获取路径的最后一部分作为文件名
            filename = os.path.basename(path)
            
            # 如果没有文件名或文件名没有扩展名，尝试从查询参数中获取
            if not filename or '.' not in filename:
                # 检查查询参数中是否有文件名
                query = parsed.query
                if query:
                    # 查找可能的文件名参数
                    filename_match = re.search(r'(?:file|filename|name)=([^&]+)', query, re.IGNORECASE)
                    if filename_match:
                        potential_filename = unquote(filename_match.group(1))
                        if '.' in potential_filename:
                            filename = potential_filename
            
            # 清理文件名，移除不安全的字符
            if filename:
                filename = UrlUtils.sanitize_filename(filename)
            
            return filename if filename and '.' in filename else None
            
        except Exception:
            return None
    
    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """
        清理文件名，移除不安全的字符
        
        Args:
            filename: 原始文件名
            
        Returns:
            安全的文件名
        """
        # 移除或替换不安全的字符
        unsafe_chars = r'[<>:"/\\|?*]'
        filename = re.sub(unsafe_chars, '_', filename)
        
        # 移除控制字符
        filename = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', filename)
        
        # 限制文件名长度
        name, ext = os.path.splitext(filename)
        if len(name) > 200:
            name = name[:200]
        filename = name + ext
        
        # 确保不是保留名称
        reserved_names = {
            'CON', 'PRN', 'AUX', 'NUL',
            'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', 'COM9',
            'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'
        }
        
        name_without_ext = os.path.splitext(filename)[0].upper()
        if name_without_ext in reserved_names:
            filename = f"_{filename}"
        
        return filename.strip()
    
    @staticmethod
    def is_valid_url(url: str) -> bool:
        """
        检查URL是否有效
        
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
    
    @staticmethod
    def get_domain(url: str) -> Optional[str]:
        """
        获取URL的域名
        
        Args:
            url: URL字符串
            
        Returns:
            域名
        """
        try:
            parsed = urlparse(url)
            return parsed.netloc
        except Exception:
            return None
    
    @staticmethod
    def normalize_url(url: str) -> str:
        """
        标准化URL
        
        Args:
            url: 原始URL
            
        Returns:
            标准化后的URL
        """
        try:
            parsed = urlparse(url)
            
            # 移除片段标识符
            normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
            
            if parsed.query:
                normalized += f"?{parsed.query}"
            
            return normalized
            
        except Exception:
            return url
    
    @staticmethod
    def extract_numbers_from_url(url: str) -> list:
        """
        从URL中提取所有数字
        
        Args:
            url: URL字符串
            
        Returns:
            数字列表
        """
        return re.findall(r'\d+', url)
    
    @staticmethod
    def generate_similar_urls(base_url: str, number_range: range) -> list:
        """
        基于基础URL生成相似的URL列表
        
        Args:
            base_url: 基础URL
            number_range: 数字范围
            
        Returns:
            URL列表
        """
        urls = []
        
        # 查找URL中的数字模式
        numbers = UrlUtils.extract_numbers_from_url(base_url)
        
        if not numbers:
            return [base_url]
        
        # 假设最后一个数字是序号
        last_number = numbers[-1]
        
        for num in number_range:
            new_url = base_url.replace(last_number, str(num), 1)
            urls.append(new_url)
        
        return urls