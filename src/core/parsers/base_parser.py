"""
基础解析器抽象类和数据结构
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass, field
from datetime import datetime
import logging


@dataclass
class ImageInfo:
    """图片信息数据类"""
    url: str
    filename: str = ""
    size: int = 0
    width: int = 0
    height: int = 0
    format: str = ""
    alt_text: str = ""
    title: str = ""
    source_page: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """初始化后处理"""
        if not self.filename and self.url:
            # 从URL提取文件名
            self.filename = self.url.split('/')[-1].split('?')[0]
        
        if not self.format and self.filename:
            # 从文件名提取格式
            ext = self.filename.split('.')[-1].lower()
            if ext in ['jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp']:
                self.format = ext


@dataclass
class SubPageInfo:
    """子页面信息数据类"""
    url: str
    title: str = ""
    description: str = ""
    depth: int = 0
    parent_url: str = ""
    link_text: str = ""
    page_type: str = "unknown"
    priority: int = 1
    source_page: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ParseResult:
    """解析结果数据类"""
    images: List[ImageInfo] = field(default_factory=list)
    subpages: List[SubPageInfo] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    parse_time: datetime = field(default_factory=datetime.now)
    success: bool = True
    
    def add_error(self, error: str):
        """添加错误信息"""
        self.errors.append(error)
        self.success = False
    
    def add_warning(self, warning: str):
        """添加警告信息"""
        self.warnings.append(warning)
    
    def merge(self, other: 'ParseResult'):
        """合并另一个解析结果"""
        self.images.extend(other.images)
        self.subpages.extend(other.subpages)
        self.metadata.update(other.metadata)
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)
        if not other.success:
            self.success = False
    
    def merge_errors(self, errors: List[str]):
        """合并错误列表"""
        self.errors.extend(errors)
        if errors:
            self.success = False
    
    def has_errors(self) -> bool:
        """检查是否有错误"""
        return len(self.errors) > 0


class BaseParser(ABC):
    """基础解析器抽象类"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化解析器
        
        Args:
            config: 解析器配置
        """
        self.config = config or {}
        self.logger = logging.getLogger(self.__class__.__name__)
        self._setup_logging()
    
    def _setup_logging(self):
        """设置日志"""
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)
    
    @abstractmethod
    def parse(self, content: Any, options: Optional[Dict[str, Any]] = None) -> Any:
        """
        解析内容的抽象方法
        
        Args:
            content: 要解析的内容
            options: 解析选项
            
        Returns:
            解析结果
        """
        pass
    
    def validate_input(self, content: Any) -> bool:
        """
        验证输入内容
        
        Args:
            content: 输入内容
            
        Returns:
            是否有效
        """
        return content is not None
    
    def handle_error(self, error: Exception, context: str = "") -> None:
        """
        处理错误
        
        Args:
            error: 异常对象
            context: 错误上下文
        """
        error_msg = f"{context}: {str(error)}" if context else str(error)
        self.logger.error(error_msg, exc_info=True)
    
    def get_config_value(self, key: str, default: Any = None) -> Any:
        """
        获取配置值
        
        Args:
            key: 配置键
            default: 默认值
            
        Returns:
            配置值
        """
        return self.config.get(key, default)


class ParserMixin:
    """解析器混入类，提供通用功能"""
    
    def clean_url(self, url: str) -> str:
        """
        清理URL
        
        Args:
            url: 原始URL
            
        Returns:
            清理后的URL
        """
        if not url:
            return ""
    
    def is_same_domain(self, url1: str, url2: str) -> bool:
        """
        检查两个URL是否属于同一域名
        
        Args:
            url1: 第一个URL
            url2: 第二个URL
            
        Returns:
            是否同域名
        """
        try:
            from urllib.parse import urlparse
            domain1 = urlparse(url1).netloc.lower()
            domain2 = urlparse(url2).netloc.lower()
            return domain1 == domain2
        except Exception:
            return False
    
    def update_config(self, config: Dict[str, Any]):
        """
        更新配置
        
        Args:
            config: 新配置
        """
        if hasattr(self, 'config'):
            self.config.update(config)
        
        # 移除多余的空白字符
        url = url.strip()
        
        # 处理相对URL
        if url.startswith('//'):
            url = 'https:' + url
        elif url.startswith('/'):
            # 需要基础URL来处理相对路径
            pass
        
        return url
    
    def extract_domain(self, url: str) -> str:
        """
        提取域名
        
        Args:
            url: URL
            
        Returns:
            域名
        """
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            return parsed.netloc
        except Exception:
            return ""
    
    def is_valid_url(self, url: str) -> bool:
        """
        检查URL是否有效
        
        Args:
            url: URL
            
        Returns:
            是否有效
        """
        if not url or not isinstance(url, str):
            return False
        
        url = url.strip()
        if not url:
            return False
        
        # 基本的URL格式检查
        return (url.startswith('http://') or 
                url.startswith('https://') or 
                url.startswith('//') or
                url.startswith('/'))
    
    def normalize_filename(self, filename: str) -> str:
        """
        规范化文件名
        
        Args:
            filename: 原始文件名
            
        Returns:
            规范化后的文件名
        """
        if not filename:
            return ""
        
        # 移除不安全的字符
        import re
        filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
        
        # 限制长度
        if len(filename) > 255:
            name, ext = filename.rsplit('.', 1) if '.' in filename else (filename, '')
            max_name_len = 255 - len(ext) - 1 if ext else 255
            filename = name[:max_name_len] + ('.' + ext if ext else '')
        
        return filename
    
    def get_file_extension(self, url_or_filename: str) -> str:
        """
        获取文件扩展名
        
        Args:
            url_or_filename: URL或文件名
            
        Returns:
            文件扩展名（小写，不含点）
        """
        if not url_or_filename:
            return ""
        
        # 移除URL参数
        filename = url_or_filename.split('?')[0].split('#')[0]
        
        # 提取扩展名
        if '.' in filename:
            ext = filename.split('.')[-1].lower()
            # 验证是否为有效的图片扩展名
            valid_exts = ['jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp', 'svg', 'ico']
            return ext if ext in valid_exts else ""
        
        return ""