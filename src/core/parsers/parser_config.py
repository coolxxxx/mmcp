"""
解析器配置管理
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import json
from pathlib import Path


@dataclass
class NetworkConfig:
    """网络配置"""
    request_timeout: int = 30
    max_retries: int = 3
    retry_delay: float = 1.0
    user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    headers: Dict[str, str] = field(default_factory=dict)
    proxies: Dict[str, str] = field(default_factory=dict)
    verify_ssl: bool = True
    max_redirects: int = 10
    
    def get_headers(self) -> Dict[str, str]:
        """获取完整的请求头"""
        default_headers = {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1"
        }
        default_headers.update(self.headers)
        return default_headers


@dataclass
class ImageConfig:
    """图片配置"""
    supported_formats: List[str] = field(default_factory=lambda: ['jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp'])
    min_image_size: int = 1024  # 最小文件大小（字节）
    max_image_size: int = 10 * 1024 * 1024  # 最大文件大小（字节）
    min_width: int = 100  # 最小宽度（像素）
    min_height: int = 100  # 最小高度（像素）
    max_width: int = 10000  # 最大宽度（像素）
    max_height: int = 10000  # 最大高度（像素）
    check_image_headers: bool = True  # 是否检查图片头信息
    download_timeout: int = 60  # 下载超时时间
    
    def is_supported_format(self, format_or_ext: str) -> bool:
        """检查是否为支持的格式"""
        if not format_or_ext:
            return False
        ext = format_or_ext.lower().lstrip('.')
        return ext in self.supported_formats
    
    def is_valid_size(self, file_size: int) -> bool:
        """检查文件大小是否有效"""
        return self.min_image_size <= file_size <= self.max_image_size
    
    def is_valid_dimensions(self, width: int, height: int) -> bool:
        """检查图片尺寸是否有效"""
        return (self.min_width <= width <= self.max_width and 
                self.min_height <= height <= self.max_height)


@dataclass
class SubPageConfig:
    """子页面配置"""
    max_depth: int = 3  # 最大递归深度
    follow_external_links: bool = False  # 是否跟踪外部链接
    allowed_domains: List[str] = field(default_factory=list)  # 允许的域名
    blocked_domains: List[str] = field(default_factory=list)  # 阻止的域名
    link_patterns: List[str] = field(default_factory=list)  # 链接匹配模式
    exclude_patterns: List[str] = field(default_factory=list)  # 排除模式
    max_links_per_page: int = 100  # 每页最大链接数
    
    def is_domain_allowed(self, domain: str) -> bool:
        """检查域名是否被允许"""
        if not domain:
            return False
        
        # 检查阻止列表
        if self.blocked_domains and domain in self.blocked_domains:
            return False
        
        # 检查允许列表
        if self.allowed_domains:
            return domain in self.allowed_domains
        
        return True


@dataclass
class FilterConfig:
    """过滤器配置"""
    enable_size_filter: bool = True
    enable_format_filter: bool = True
    enable_duplicate_filter: bool = True
    enable_dimension_filter: bool = True
    enable_content_filter: bool = False
    
    # 自定义过滤规则
    custom_filters: List[Dict[str, Any]] = field(default_factory=list)
    
    # 排序配置
    sort_by: str = "size"  # size, name, url, format
    sort_order: str = "desc"  # asc, desc
    
    def is_filter_enabled(self, filter_name: str) -> bool:
        """检查过滤器是否启用"""
        return getattr(self, f"enable_{filter_name}_filter", False)


@dataclass
class ParserConfig:
    """解析器主配置"""
    # 子配置
    network: NetworkConfig = field(default_factory=NetworkConfig)
    image: ImageConfig = field(default_factory=ImageConfig)
    subpage: SubPageConfig = field(default_factory=SubPageConfig)
    filter: FilterConfig = field(default_factory=FilterConfig)
    
    # 通用配置
    enable_logging: bool = True
    log_level: str = "INFO"
    max_workers: int = 4  # 最大工作线程数
    enable_cache: bool = True
    cache_ttl: int = 3600  # 缓存TTL（秒）
    
    # 性能配置
    batch_size: int = 10  # 批处理大小
    memory_limit_mb: int = 512  # 内存限制（MB）
    
    # 错误处理配置
    continue_on_error: bool = True  # 遇到错误是否继续
    max_errors: int = 10  # 最大错误数
    
    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> 'ParserConfig':
        """从字典创建配置"""
        config = cls()
        
        # 更新网络配置
        if 'network' in config_dict:
            network_dict = config_dict['network']
            for key, value in network_dict.items():
                if hasattr(config.network, key):
                    setattr(config.network, key, value)
        
        # 更新图片配置
        if 'image' in config_dict:
            image_dict = config_dict['image']
            for key, value in image_dict.items():
                if hasattr(config.image, key):
                    setattr(config.image, key, value)
        
        # 更新子页面配置
        if 'subpage' in config_dict:
            subpage_dict = config_dict['subpage']
            for key, value in subpage_dict.items():
                if hasattr(config.subpage, key):
                    setattr(config.subpage, key, value)
        
        # 更新过滤器配置
        if 'filter' in config_dict:
            filter_dict = config_dict['filter']
            for key, value in filter_dict.items():
                if hasattr(config.filter, key):
                    setattr(config.filter, key, value)
        
        # 更新主配置
        for key, value in config_dict.items():
            if key not in ['network', 'image', 'subpage', 'filter'] and hasattr(config, key):
                setattr(config, key, value)
        
        return config
    
    @classmethod
    def from_file(cls, config_path: str) -> 'ParserConfig':
        """从文件加载配置"""
        config_file = Path(config_path)
        if not config_file.exists():
            raise FileNotFoundError(f"配置文件不存在: {config_path}")
        
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config_dict = json.load(f)
            return cls.from_dict(config_dict)
        except json.JSONDecodeError as e:
            raise ValueError(f"配置文件格式错误: {e}")
        except Exception as e:
            raise RuntimeError(f"加载配置文件失败: {e}")
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'network': {
                'request_timeout': self.network.request_timeout,
                'max_retries': self.network.max_retries,
                'retry_delay': self.network.retry_delay,
                'user_agent': self.network.user_agent,
                'headers': self.network.headers,
                'proxies': self.network.proxies,
                'verify_ssl': self.network.verify_ssl,
                'max_redirects': self.network.max_redirects
            },
            'image': {
                'supported_formats': self.image.supported_formats,
                'min_image_size': self.image.min_image_size,
                'max_image_size': self.image.max_image_size,
                'min_width': self.image.min_width,
                'min_height': self.image.min_height,
                'max_width': self.image.max_width,
                'max_height': self.image.max_height,
                'check_image_headers': self.image.check_image_headers,
                'download_timeout': self.image.download_timeout
            },
            'subpage': {
                'max_depth': self.subpage.max_depth,
                'follow_external_links': self.subpage.follow_external_links,
                'allowed_domains': self.subpage.allowed_domains,
                'blocked_domains': self.subpage.blocked_domains,
                'link_patterns': self.subpage.link_patterns,
                'exclude_patterns': self.subpage.exclude_patterns,
                'max_links_per_page': self.subpage.max_links_per_page
            },
            'filter': {
                'enable_size_filter': self.filter.enable_size_filter,
                'enable_format_filter': self.filter.enable_format_filter,
                'enable_duplicate_filter': self.filter.enable_duplicate_filter,
                'enable_dimension_filter': self.filter.enable_dimension_filter,
                'enable_content_filter': self.filter.enable_content_filter,
                'custom_filters': self.filter.custom_filters,
                'sort_by': self.filter.sort_by,
                'sort_order': self.filter.sort_order
            },
            'enable_logging': self.enable_logging,
            'log_level': self.log_level,
            'max_workers': self.max_workers,
            'enable_cache': self.enable_cache,
            'cache_ttl': self.cache_ttl,
            'batch_size': self.batch_size,
            'memory_limit_mb': self.memory_limit_mb,
            'continue_on_error': self.continue_on_error,
            'max_errors': self.max_errors
        }
    
    def save_to_file(self, config_path: str):
        """保存配置到文件"""
        config_file = Path(config_path)
        config_file.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
        except Exception as e:
            raise RuntimeError(f"保存配置文件失败: {e}")
    
    def validate(self) -> List[str]:
        """验证配置"""
        errors = []
        
        # 验证网络配置
        if self.network.request_timeout <= 0:
            errors.append("网络请求超时时间必须大于0")
        
        if self.network.max_retries < 0:
            errors.append("最大重试次数不能为负数")
        
        # 验证图片配置
        if self.image.min_image_size < 0:
            errors.append("最小图片大小不能为负数")
        
        if self.image.max_image_size <= self.image.min_image_size:
            errors.append("最大图片大小必须大于最小图片大小")
        
        if self.image.min_width <= 0 or self.image.min_height <= 0:
            errors.append("图片最小尺寸必须大于0")
        
        # 验证子页面配置
        if self.subpage.max_depth < 0:
            errors.append("最大递归深度不能为负数")
        
        if self.subpage.max_links_per_page <= 0:
            errors.append("每页最大链接数必须大于0")
        
        # 验证通用配置
        if self.max_workers <= 0:
            errors.append("最大工作线程数必须大于0")
        
        if self.batch_size <= 0:
            errors.append("批处理大小必须大于0")
        
        return errors