"""
并发处理模块
提供高性能的多线程和异步处理能力
"""

# 导入所有并发处理组件
import logging
logger = logging.getLogger(__name__)

# 逐个导入模块，处理可能的导入错误
_available_modules = {}

# 线程池管理器
try:
    from .thread_pool_manager import ThreadPoolManager, ThreadPoolConfig, get_global_pool_manager
    _available_modules['thread_pool'] = True
except ImportError as e:
    logger.warning(f"线程池管理器导入失败: {e}")
    _available_modules['thread_pool'] = False

# 异步执行器
try:
    from .async_executor import AsyncExecutor, AsyncTask, get_global_async_executor
    _available_modules['async_executor'] = True
except ImportError as e:
    logger.warning(f"异步执行器导入失败: {e}")
    _available_modules['async_executor'] = False

# 资源管理器
try:
    from .resource_manager import ResourceManager, ResourceLimiter, get_global_resource_manager
    _available_modules['resource_manager'] = True
except ImportError as e:
    logger.warning(f"资源管理器导入失败: {e}")
    _available_modules['resource_manager'] = False

# 并发下载器
try:
    from .concurrent_downloader import ConcurrentDownloader, download_files
    _available_modules['concurrent_downloader'] = True
except ImportError as e:
    logger.warning(f"并发下载器导入失败: {e}")
    _available_modules['concurrent_downloader'] = False

# 性能监控器
try:
    from .performance_monitor import PerformanceMonitor, get_global_performance_monitor
    _available_modules['performance_monitor'] = True
except ImportError as e:
    logger.warning(f"性能监控器导入失败: {e}")
    _available_modules['performance_monitor'] = False

# 内存优化器
try:
    from .memory_optimizer import MemoryOptimizer, get_global_memory_optimizer
    _available_modules['memory_optimizer'] = True
except ImportError as e:
    logger.warning(f"内存优化器导入失败: {e}")
    _available_modules['memory_optimizer'] = False

# 构建导出列表
__all__ = []

if _available_modules.get('thread_pool'):
    __all__.extend(['ThreadPoolManager', 'ThreadPoolConfig', 'get_global_pool_manager'])

if _available_modules.get('async_executor'):
    __all__.extend(['AsyncExecutor', 'AsyncTask', 'get_global_async_executor'])

if _available_modules.get('resource_manager'):
    __all__.extend(['ResourceManager', 'ResourceLimiter', 'get_global_resource_manager'])

if _available_modules.get('concurrent_downloader'):
    __all__.extend(['ConcurrentDownloader', 'download_files'])

if _available_modules.get('performance_monitor'):
    __all__.extend(['PerformanceMonitor', 'get_global_performance_monitor'])

if _available_modules.get('memory_optimizer'):
    __all__.extend(['MemoryOptimizer', 'get_global_memory_optimizer'])

# 记录可用模块
available_count = sum(_available_modules.values())
total_count = len(_available_modules)
logger.info(f"并发模块加载完成: {available_count}/{total_count} 个模块可用")