"""
服务器友好的下载配置
针对502错误和服务器拒绝问题的保守优化策略
"""

from dataclasses import dataclass
from typing import Dict, Any, Optional
import json
import os


@dataclass
class ServerFriendlyConfig:
    """服务器友好的下载配置类"""
    
    # 保守的性能配置 - 避免服务器过载
    max_threads: int = 6       # 适中的线程数，避免服务器压力
    timeout: int = 45          # 增加超时时间，给服务器充足响应时间
    retry_times: int = 4       # 增加重试次数应对502错误
    chunk_size: int = 8192     # 适中的块大小，减少内存压力
    
    # 温和的速率限制 - 防止触发反爬机制
    base_rate: int = 3         # 降低基础速率，减少服务器压力
    max_rate: int = 8          # 降低突发容量，避免触发502
    
    # 分片下载配置 - 保守策略
    enable_chunked_download: bool = False  # 暂时禁用分片下载，减少复杂性
    chunk_download_threshold: int = 10 * 1024 * 1024  # 10MB阈值
    connection_pool_size: int = 8          # 减少连接池大小
    
    # 自适应配置 - 保守调整
    adaptive_threading: bool = True
    adaptive_interval: int = 60            # 增加自适应间隔，减少频繁调整
    max_threads_limit: int = 10            # 设置线程数上限
    min_threads_limit: int = 2             # 设置线程数下限
    
    # 状态更新配置
    status_update_interval: float = 0.2    # 稍微增加更新间隔
    progress_update_interval: float = 1.0  # 增加进度更新间隔
    
    # 重试配置 - 针对502错误优化
    min_retry_delay: float = 3.0           # 增加重试延迟
    max_retry_delay: int = 60              # 大幅增加最大延迟
    server_error_delay: int = 15           # 服务器错误专用延迟
    exponential_backoff: bool = True       # 启用指数退避
    
    # 502错误专用配置
    server_error_retry_times: int = 6      # 服务器错误专用重试次数
    server_error_cooldown: int = 30        # 服务器错误后的冷却时间
    
    # 会话配置 - 更友好的请求头
    verify_ssl: bool = True
    user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    proxy: Optional[str] = None
    
    # 请求间隔配置
    request_interval: float = 0.5          # 请求间最小间隔
    burst_interval: float = 2.0            # 突发请求后的间隔
    
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
            'max_threads_limit': self.max_threads_limit,
            'min_threads_limit': self.min_threads_limit,
            'status_update_interval': self.status_update_interval,
            'progress_update_interval': self.progress_update_interval,
            'min_retry_delay': self.min_retry_delay,
            'max_retry_delay': self.max_retry_delay,
            'server_error_delay': self.server_error_delay,
            'exponential_backoff': self.exponential_backoff,
            'server_error_retry_times': self.server_error_retry_times,
            'server_error_cooldown': self.server_error_cooldown,
            'request_interval': self.request_interval,
            'burst_interval': self.burst_interval,
            'session': {
                'verify_ssl': self.verify_ssl,
                'user_agent': self.user_agent,
                'proxy': self.proxy
            }
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ServerFriendlyConfig':
        """从字典创建配置"""
        session_data = data.get('session', {})
        
        return cls(
            max_threads=data.get('max_threads', 6),
            timeout=data.get('timeout', 45),
            retry_times=data.get('retry_times', 4),
            chunk_size=data.get('chunk_size', 8192),
            base_rate=data.get('base_rate', 3),
            max_rate=data.get('max_rate', 8),
            enable_chunked_download=data.get('enable_chunked_download', False),
            chunk_download_threshold=data.get('chunk_download_threshold', 10 * 1024 * 1024),
            connection_pool_size=data.get('connection_pool_size', 8),
            adaptive_threading=data.get('adaptive_threading', True),
            adaptive_interval=data.get('adaptive_interval', 60),
            max_threads_limit=data.get('max_threads_limit', 10),
            min_threads_limit=data.get('min_threads_limit', 2),
            status_update_interval=data.get('status_update_interval', 0.2),
            progress_update_interval=data.get('progress_update_interval', 1.0),
            min_retry_delay=data.get('min_retry_delay', 3.0),
            max_retry_delay=data.get('max_retry_delay', 60),
            server_error_delay=data.get('server_error_delay', 15),
            exponential_backoff=data.get('exponential_backoff', True),
            server_error_retry_times=data.get('server_error_retry_times', 6),
            server_error_cooldown=data.get('server_error_cooldown', 30),
            request_interval=data.get('request_interval', 0.5),
            burst_interval=data.get('burst_interval', 2.0),
            verify_ssl=session_data.get('verify_ssl', True),
            user_agent=session_data.get('user_agent', 
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"),
            proxy=session_data.get('proxy')
        )
    
    def save_to_file(self, filepath: str) -> None:
        """保存配置到文件"""
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
    
    @classmethod
    def load_from_file(cls, filepath: str) -> 'ServerFriendlyConfig':
        """从文件加载配置"""
        if not os.path.exists(filepath):
            return cls()
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return cls.from_dict(data)
        except Exception as e:
            print(f"加载配置文件失败: {e}")
            return cls()


def get_server_friendly_config() -> ServerFriendlyConfig:
    """获取服务器友好的配置"""
    config_path = os.path.join(os.path.dirname(__file__), '..', '..', 'config', 'server_friendly.json')
    return ServerFriendlyConfig.load_from_file(config_path)


def create_server_friendly_config_file():
    """创建服务器友好的配置文件"""
    config = ServerFriendlyConfig()
    config_path = os.path.join(os.path.dirname(__file__), '..', '..', 'config', 'server_friendly.json')
    config.save_to_file(config_path)
    print(f"服务器友好配置已创建: {config_path}")
    
    # 输出配置说明
    print("\n服务器友好配置特点:")
    print(f"- 线程数: {config.max_threads} (保守)")
    print(f"- 请求速率: {config.base_rate}-{config.max_rate} req/s (温和)")
    print(f"- 超时时间: {config.timeout}s (充足)")
    print(f"- 重试次数: {config.retry_times} (增强)")
    print(f"- 服务器错误延迟: {config.server_error_delay}s")
    print(f"- 请求间隔: {config.request_interval}s")
    print("- 分片下载: 禁用 (减少复杂性)")
    print("- 指数退避: 启用")


if __name__ == "__main__":
    create_server_friendly_config_file()