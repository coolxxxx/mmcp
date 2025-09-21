#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
文件管理器模块
负责智能目录创建、文件命名和组织
"""

import os
import re
import hashlib
from pathlib import Path
from typing import Optional, Dict, List, Any, TypedDict
from urllib.parse import urlparse
import logging
from datetime import datetime

from ..utils.url_utils import UrlUtils

class FileManager:
    """文件管理器"""
    
    def __init__(self, base_download_path: str):
        """
        初始化文件管理器
        
        Args:
            base_download_path: 基础下载路径
        """
        self.base_path = Path(base_download_path)
        self.logger = logging.getLogger(__name__)
        
        # 确保基础路径存在
        self.base_path.mkdir(parents=True, exist_ok=True)
    
    def create_task_directory(self, url: str, custom_name: Optional[str] = None, reuse_existing: bool = True) -> str:
        """
        为任务创建目录（支持智能复用）
        
        Args:
            url: 任务URL
            custom_name: 自定义目录名
            reuse_existing: 是否复用已存在的同名目录
            
        Returns:
            创建或复用的目录路径
        """
        if custom_name:
            dir_name = UrlUtils.sanitize_filename(custom_name)
        else:
            dir_name = self._extract_directory_name_from_url(url)
        
        # 主目录路径
        task_dir = self.base_path / dir_name
        
        if reuse_existing and task_dir.exists():
            # 复用已存在的目录
            self.logger.info(f"复用已存在的目录: {task_dir}")
            return str(task_dir)
        
        if not reuse_existing:
            # 不复用时，确保目录名唯一
            counter = 1
            original_dir_name = dir_name
            
            while task_dir.exists():
                dir_name = f"{original_dir_name}_{counter}"
                task_dir = self.base_path / dir_name
                counter += 1
        
        # 创建目录
        task_dir.mkdir(parents=True, exist_ok=True)
        
        self.logger.info(f"创建任务目录: {task_dir}")
        return str(task_dir)
    
    def check_existing_downloads(self, directory: str, url: str) -> Dict[str, Any]:
        """
        检查目录中是否已有相关下载文件
        
        Args:
            directory: 目录路径
            url: 任务URL
            
        Returns:
            检查结果字典
        """
        # 定义结果字典的类型
        result: Dict[str, Any] = {
            'has_files': False,
            'file_count': 0,
            'total_size': 0,
            'image_files': [],
            'directory_exists': False
        }
        
        dir_path = Path(directory)
        if not dir_path.exists():
            return result
        
        result['directory_exists'] = True
        
        # 统计目录中的文件
        image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'}
        
        for file_path in dir_path.rglob('*'):
            if file_path.is_file():
                result['file_count'] += 1
                file_size = file_path.stat().st_size
                result['total_size'] += file_size
                
                # 检查是否为图片文件
                if file_path.suffix.lower() in image_extensions:
                    result['image_files'].append({
                        'path': str(file_path),
                        'name': file_path.name,
                        'size': file_size
                    })
        
        result['has_files'] = result['file_count'] > 0
        
        if result['has_files']:
            self.logger.info(f"目录 {directory} 中已有 {result['file_count']} 个文件，其中 {len(result['image_files'])} 张图片")
        
        return result
    
    def create_sub_directory(self, base_dir: str, sub_url: str) -> str:
        """
        创建子目录
        
        Args:
            base_dir: 基础目录
            sub_url: 子页面URL
            
        Returns:
            子目录路径
        """
        sub_name = self._extract_directory_name_from_url(sub_url)
        sub_dir = Path(base_dir) / sub_name
        sub_dir.mkdir(parents=True, exist_ok=True)
        
        return str(sub_dir)
    
    def get_image_file_path(self, directory: str, image_url: str, filename: Optional[str] = None, skip_existing: bool = True) -> str:
        """
        获取图片文件的完整路径
        
        Args:
            directory: 目录路径
            image_url: 图片URL
            filename: 自定义文件名
            skip_existing: 是否跳过已存在的文件（不重复下载）
            
        Returns:
            完整文件路径
        """
        if not filename:
            filename = UrlUtils.extract_filename_from_url(image_url)
        
        if not filename:
            # 如果无法提取文件名，生成一个
            filename = self._generate_filename_from_url(image_url)
        
        # 确保文件名安全
        filename = UrlUtils.sanitize_filename(filename)
        
        # 处理重复文件名
        file_path = Path(directory) / filename
        
        if skip_existing and file_path.exists() and self.is_file_complete(str(file_path)) and self._is_reasonable_file_size(str(file_path)):
            # 如果文件已存在且完整且大小合理，返回特殊标记表示跳过
            self.logger.debug(f"跳过已存在的完整文件: {file_path}")
            return "SKIP_EXISTING"  # 特殊标记
        elif skip_existing and file_path.exists():
            # 文件存在但不完整或大小不合理，删除并重新下载
            self.logger.info(f"删除不完整或大小不合理的文件: {file_path}")
            try:
                file_path.unlink()
            except Exception as e:
                self.logger.warning(f"删除文件失败: {e}")
        
        if not skip_existing:
            # 不跳过时，确保文件名唯一
            counter = 1
            original_filename = filename
            name, ext = os.path.splitext(original_filename)
            
            while file_path.exists():
                filename = f"{name}_{counter}{ext}"
                file_path = Path(directory) / filename
                counter += 1
        
        return str(file_path)
    
    def _is_reasonable_file_size(self, file_path: str) -> bool:
        """
        检查文件大小是否合理
        
        Args:
            file_path: 文件路径
            
        Returns:
            文件大小是否合理
        """
        try:
            file_size = Path(file_path).stat().st_size
            
            # 基本大小检查：不能太小（可能是错误文件）
            if file_size < 100:  # 100字节以下是明显的错误文件
                self.logger.debug(f"文件过小: {file_path} ({file_size} 字节)")
                return False
            
            # 不能过大（可能是损坏文件）
            if file_size > 50 * 1024 * 1024:  # 50MB以上可能有问题
                self.logger.debug(f"文件过大: {file_path} ({file_size} 字节)")
                return False
            
            return True
            
        except Exception as e:
            self.logger.warning(f"检查文件大小失败: {file_path} - {e}")
            return True  # 无法检查时假设合理
    
    def _extract_directory_name_from_url(self, url: str) -> str:
        """
        从URL中提取目录名
        
        Args:
            url: URL字符串
            
        Returns:
            目录名
        """
        try:
            parsed = urlparse(url)
            path = parsed.path
            
            # 尝试从路径中提取有意义的名称
            # 例如：/Xiuren/Xiuren33896_1.html -> Xiuren33896
            
            # 查找路径中的模式
            patterns = [
                r'([A-Za-z]+\d+)',  # 字母+数字组合，如Xiuren33896
                r'(\w+?)(?:_\d+)?(?:\.\w+)?$',  # 文件名模式
                r'/([^/]+?)(?:/[^/]*)?$',  # 路径段
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, path)
                if matches:
                    name = matches[-1]  # 取最后一个匹配
                    if len(name) > 3:  # 确保名称有意义
                        return UrlUtils.sanitize_filename(name)
            
            # 如果无法提取，使用域名
            domain = parsed.netloc
            if domain:
                # 移除www.前缀和顶级域名
                domain = re.sub(r'^www\.', '', domain)
                domain = re.sub(r'\.[^.]+$', '', domain)
                return UrlUtils.sanitize_filename(domain)
            
            # 最后选择：使用URL的哈希值
            return f"task_{hashlib.md5(url.encode()).hexdigest()[:8]}"
            
        except Exception as e:
            self.logger.warning(f"从URL提取目录名失败: {url} - {e}")
            return f"task_{hashlib.md5(url.encode()).hexdigest()[:8]}"
    
    def _generate_filename_from_url(self, url: str) -> str:
        """
        从URL生成文件名
        
        Args:
            url: 图片URL
            
        Returns:
            生成的文件名
        """
        # 使用URL的哈希值生成文件名
        url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
        
        # 尝试确定文件扩展名
        parsed = urlparse(url)
        path = parsed.path.lower()
        
        # 常见图片扩展名
        extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp']
        ext = '.jpg'  # 默认扩展名
        
        for extension in extensions:
            if extension in path or extension in url.lower():
                ext = extension
                break
        
        return f"image_{url_hash}{ext}"
    
    def organize_files_by_type(self, directory: str) -> Dict[str, List[str]]:
        """
        按文件类型组织文件
        
        Args:
            directory: 目录路径
            
        Returns:
            按类型分组的文件字典
        """
        file_groups = {}
        dir_path = Path(directory)
        
        if not dir_path.exists():
            return file_groups
        
        for file_path in dir_path.rglob('*'):
            if file_path.is_file():
                ext = file_path.suffix.lower()
                if ext:
                    if ext not in file_groups:
                        file_groups[ext] = []
                    file_groups[ext].append(str(file_path))
        
        return file_groups
    
    def get_directory_stats(self, directory: str) -> Dict[str, Any]:
        """
        获取目录统计信息
        
        Args:
            directory: 目录路径
            
        Returns:
            统计信息字典
        """
        stats: Dict[str, Any] = {
            'total_files': 0,
            'total_size': 0,
            'file_types': {},
            'largest_file': None,
            'largest_size': 0
        }
        
        dir_path = Path(directory)
        if not dir_path.exists():
            return stats
        
        for file_path in dir_path.rglob('*'):
            if file_path.is_file():
                try:
                    file_size = file_path.stat().st_size
                    # 明确类型转换以确保类型安全
                    total_files = stats['total_files']
                    if isinstance(total_files, int):
                        stats['total_files'] = total_files + 1
                    
                    total_size = stats['total_size']
                    if isinstance(total_size, int):
                        stats['total_size'] = total_size + file_size
                    
                    # 记录最大文件
                    largest_size = stats['largest_size']
                    if isinstance(largest_size, int) and file_size > largest_size:
                        stats['largest_size'] = file_size
                        stats['largest_file'] = str(file_path)
                    
                    # 统计文件类型
                    ext = file_path.suffix.lower()
                    if ext:
                        if ext not in stats['file_types']:
                            stats['file_types'][ext] = {'count': 0, 'size': 0}
                        file_type_stats = stats['file_types'][ext]
                        if isinstance(file_type_stats, dict):
                            count = file_type_stats.get('count', 0)
                            size = file_type_stats.get('size', 0)
                            if isinstance(count, int) and isinstance(size, int):
                                file_type_stats['count'] = count + 1
                                file_type_stats['size'] = size + file_size
                        
                except Exception as e:
                    self.logger.warning(f"获取文件信息失败: {file_path} - {e}")
        
        return stats
    
    def cleanup_empty_directories(self, directory: str) -> int:
        """
        清理空目录
        
        Args:
            directory: 要清理的目录
            
        Returns:
            清理的目录数量
        """
        cleaned_count = 0
        dir_path = Path(directory)
        
        if not dir_path.exists():
            return cleaned_count
        
        # 从深层目录开始清理
        for subdir in sorted(dir_path.rglob('*'), key=lambda p: len(p.parts), reverse=True):
            if subdir.is_dir() and subdir != dir_path:
                try:
                    # 检查目录是否为空
                    if not any(subdir.iterdir()):
                        subdir.rmdir()
                        cleaned_count += 1
                        self.logger.info(f"删除空目录: {subdir}")
                except Exception as e:
                    self.logger.warning(f"删除空目录失败: {subdir} - {e}")
        
        return cleaned_count
    
    def ensure_directory_exists(self, directory: str) -> bool:
        """
        确保目录存在
        
        Args:
            directory: 目录路径
            
        Returns:
            是否成功
        """
        try:
            Path(directory).mkdir(parents=True, exist_ok=True)
            return True
        except Exception as e:
            self.logger.error(f"创建目录失败: {directory} - {e}")
            return False
    
    def is_file_complete(self, file_path: str, expected_size: Optional[int] = None) -> bool:
        """
        检查文件是否完整
        
        Args:
            file_path: 文件路径
            expected_size: 期望的文件大小
            
        Returns:
            文件是否完整
        """
        try:
            path = Path(file_path)
            if not path.exists():
                return False
            
            # 检查文件大小
            actual_size = path.stat().st_size
            
            # 如果文件为空，认为不完整
            if actual_size == 0:
                return False
            
            # 如果有期望大小，比较大小
            if expected_size is not None:
                return actual_size == expected_size
            
            return True
            
        except Exception as e:
            self.logger.warning(f"检查文件完整性失败: {file_path} - {e}")
            return False
    
    def get_free_space(self, directory: str) -> int:
        """
        获取目录所在磁盘的可用空间
        
        Args:
            directory: 目录路径
            
        Returns:
            可用空间（字节）
        """
        try:
            import shutil
            return shutil.disk_usage(directory).free
        except Exception as e:
            self.logger.warning(f"获取磁盘空间失败: {directory} - {e}")
            return 0
    
    def save_page_description(self, directory: str, title: str, description: str, url: str) -> bool:
        """
        保存页面描述信息到文本文件
        
        Args:
            directory: 目录路径
            title: 页面标题（用作文件名）
            description: 页面描述内容
            url: 原始页面URL
            
        Returns:
            是否保存成功
        """
        try:
            if not description or not description.strip():
                self.logger.debug("描述内容为空，跳过保存")
                return False
            
            # 确保目录存在
            if not self.ensure_directory_exists(directory):
                return False
            
            # 生成文件名（使用页面标题）
            filename = self._generate_description_filename(title)
            file_path = Path(directory) / filename
            
            # 准备文件内容
            content_lines = [
                f"页面标题: {title}",
                f"原始链接: {url}",
                f"提取时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                "",
                "—————— 套图描述 ——————",
                "",
                description.strip()
            ]
            
            # 写入文件
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(content_lines))
            
            self.logger.info(f"保存页面描述: {file_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"保存页面描述失败: {e}")
            return False
    
    def _generate_description_filename(self, title: str) -> str:
        """
        生成描述文件的文件名
        
        Args:
            title: 页面标题
            
        Returns:
            清理后的文件名
        """
        if not title or not title.strip():
            return "套图描述.txt"
        
        # 清理标题，移除非法字符
        cleaned_title = UrlUtils.sanitize_filename(title.strip())
        
        # 限制文件名长度
        if len(cleaned_title) > 200:
            cleaned_title = cleaned_title[:200]
        
        # 确保以.txt结尾
        if not cleaned_title.endswith('.txt'):
            cleaned_title += '.txt'
        
        return cleaned_title

    def get_file_path(self, directory: str, filename: str) -> str:
        """
        获取文件的完整路径
        
        Args:
            directory: 目录路径
            filename: 文件名
            
        Returns:
            文件的完整路径
            
        Raises:
            ValueError: 当目录或文件名为空时
            FileNotFoundError: 当文件不存在时（可选）
        """
        if not directory or not directory.strip():
            raise ValueError("目录路径不能为空")
        
        if not filename or not filename.strip():
            raise ValueError("文件名不能为空")
        
        # 使用pathlib确保跨平台路径兼容性
        dir_path = Path(directory)
        file_path = dir_path / filename
        
        # 规范化路径，处理路径分隔符和相对路径
        full_path = file_path.resolve()
        
        # 可选：检查文件是否存在
        if not full_path.exists():
            # 可以选择抛出异常或返回路径
            # raise FileNotFoundError(f"文件不存在: {full_path}")
            self.logger.warning(f"文件不存在: {full_path}")
        
        return str(full_path)