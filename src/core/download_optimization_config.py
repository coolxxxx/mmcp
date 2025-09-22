"""
下载优化配置
针对进度更新和速度优化的配置管理
"""

from dataclasses import dataclass
from typing import Dict, Any, Optional
import json
import os


@dataclass
class DownloadOptimizationConfig:
    """下载优化配置类"""
    
    # 基础性能配置
    max_threads: int = 15  # 增加默认线程数
    timeout: int = 20  # 减少超时时间
    retry_times: int = 2  # 减少重试次数
    chunk_size: int = 16384  # 增加块大小
    
    # 速率限制优化
    base_rate: int = 20  # 提高基础速率
    max_rate: int = 50  # 提高突发容量
    
    # 分片下载配置
    enable_chunked_download: bool = True
    chunk_download_threshold: int = 5 * 1024 * 1024  # 5MB
    connection_pool_size: int = 20
    
    # 自适应配置
    adaptive_threading: bool = True
    adaptive_interval: int = 10  # 减少自适应间隔
    
    # 状态更新配置
    status_update_interval: float = 0.1  # 状态更新间隔
    progress_update_interval: float = 0.5  # 进度更新间隔
    
    # 重试配置优化
    min_retry_delay: float = 0.5  # 减少重试延迟
    max_retry_delay: int = 5  # 减少最大延迟
    
    # 会话配置
    verify_ssl: bool = True
    user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    proxy: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'max_threads': self.max_threads,
            'timeout': self.timeout,
            'retry_times': self.retry_times,
            'chunk_size': self.chunk_size,
            'base_rate': self.base_rate,
            'max_rate': self.max_rate,
            'enable_chunked_download': self.enable_chunked_download,
            'chunk_download_threshold': self.chunk_download_threshold,
            'connection_pool_size': self.connection_pool_size,
            'adaptive_threading': self.adaptive_threading,
            'adaptive_interval': self.adaptive_interval,
            'status_update_interval': self.status_update_interval,
            'progress_update_interval': self.progress_update_interval,
            'min_retry_delay': self.min_retry_delay,
            'max_retry_delay': self.max_retry_delay,
            'session': {
                'verify_ssl': self.verify_ssl,
                'user_agent': self.user_agent,
                'proxy': self.proxy
            }
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DownloadOptimizationConfig':
        """从字典创建配置"""
        session_data = data.get('session', {})
        
        return cls(
            max_threads=data.get('max_threads', 15),
            timeout=data.get('timeout', 20),
            retry_times=data.get('retry_times', 2),
            chunk_size=data.get('chunk_size', 16384),
            base_rate=data.get('base_rate', 20),
            max_rate=data.get('max_rate', 50),
            enable_chunked_download=data.get('enable_chunked_download', True),
            chunk_download_threshold=data.get('chunk_download_threshold', 5 * 1024 * 1024),
            connection_pool_size=data.get('connection_pool_size', 20),
            adaptive_threading=data.get('adaptive_threading', True),
            adaptive_interval=data.get('adaptive_interval', 10),
            status_update_interval=data.get('status_update_interval', 0.1),
            progress_update_interval=data.get('progress_update_interval', 0.5),
            min_retry_delay=data.get('min_retry_delay', 0.5),
            max_retry_delay=data.get('max_retry_delay', 5),
            verify_ssl=session_data.get('verify_ssl', True),
            user_agent=session_data.get('user_agent', 
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"),
            proxy=session_data.get('proxy')
        )
    
    def save_to_file(self, filepath: str) -> None:
        """保存配置到文件"""
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
    
    @classmethod
    def load_from_file(cls, filepath: str) -> 'DownloadOptimizationConfig':
        """从文件加载配置"""
        if not os.path.exists(filepath):
            return cls()  # 返回默认配置
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return cls.from_dict(data)
        except Exception as e:
            print(f"加载配置文件失败: {e}")
            return cls()  # 返回默认配置


def get_optimized_config() -> DownloadOptimizationConfig:
    """获取优化后的配置"""
    config_path = os.path.join(os.path.dirname(__file__), '..', '..', 'config', 'download_optimization.json')
    return DownloadOptimizationConfig.load_from_file(config_path)


def create_default_config_file():
    """创建默认配置文件"""
    config = DownloadOptimizationConfig()
    config_path = os.path.join(os.path.dirname(__file__), '..', '..', 'config', 'download_optimization.json')
    config.save_to_file(config_path)
    print(f"默认优化配置已创建: {config_path}")


if __name__ == "__main__":
    create_default_config_file()