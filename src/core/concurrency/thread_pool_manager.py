"""
线程池管理器
提供智能的线程池管理和资源调度
"""

import threading
import time
import queue
from typing import Dict, List, Any, Optional, Callable, Union, Tuple
from concurrent.futures import ThreadPoolExecutor, Future, as_completed
from dataclasses import dataclass
from enum import Enum
import logging

try:
    import psutil
except ImportError:
    psutil = None


class PoolType(Enum):
    """线程池类型"""
    IO_BOUND = "io_bound"      # I/O密集型任务
    CPU_BOUND = "cpu_bound"    # CPU密集型任务
    MIXED = "mixed"            # 混合型任务
    DOWNLOAD = "download"      # 下载专用
    PARSE = "parse"           # 解析专用


@dataclass
class ThreadPoolConfig:
    """线程池配置"""
    pool_type: PoolType
    min_workers: int = 2
    max_workers: int = 10
    core_workers: int = 5
    queue_size: int = 100
    keep_alive_time: int = 60  # 秒
    auto_scale: bool = True
    priority_queue: bool = False
    thread_name_prefix: str = "Worker"


class ThreadPoolManager:
    """智能线程池管理器"""
    
    def __init__(self):
        """初始化线程池管理器"""
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # 线程池字典
        self.pools: Dict[str, ThreadPoolExecutor] = {}
        self.pool_configs: Dict[str, ThreadPoolConfig] = {}
        self.pool_stats: Dict[str, Dict[str, Any]] = {}
        
        # 系统资源监控
        self.cpu_count = psutil.cpu_count() if psutil else 4
        self.memory_total = psutil.virtual_memory().total if psutil else 8 * 1024 * 1024 * 1024
        
        # 管理锁
        self.lock = threading.RLock()
        
        # 监控线程
        self.monitor_thread: Optional[threading.Thread] = None
        self.is_monitoring = False
        
        # 默认配置
        self._setup_default_pools()
        
        self.logger.info(f"线程池管理器初始化完成，CPU核心数: {self.cpu_count}")
    
    def _setup_default_pools(self):
        """设置默认线程池"""
        # I/O密集型池（下载、网络请求）
        io_config = ThreadPoolConfig(
            pool_type=PoolType.IO_BOUND,
            min_workers=2,
            max_workers=min(32, (self.cpu_count or 1) * 4),
            core_workers=min(8, (self.cpu_count or 1) * 2),
            queue_size=200,
            auto_scale=True,
            thread_name_prefix="IO-Worker"
        )
        self.create_pool("io_bound", io_config)
        
        # CPU密集型池（解析、处理）
        cpu_config = ThreadPoolConfig(
            pool_type=PoolType.CPU_BOUND,
            min_workers=1,
            max_workers=self.cpu_count or 1,
            core_workers=max(1, (self.cpu_count or 1) // 2),
            queue_size=50,
            auto_scale=True,
            thread_name_prefix="CPU-Worker"
        )
        self.create_pool("cpu_bound", cpu_config)
        
        # 下载专用池
        download_config = ThreadPoolConfig(
            pool_type=PoolType.DOWNLOAD,
            min_workers=3,
            max_workers=min(20, (self.cpu_count or 1) * 3),
            core_workers=min(10, (self.cpu_count or 1) * 2),
            queue_size=500,
            auto_scale=True,
            priority_queue=True,
            thread_name_prefix="Download-Worker"
        )
        self.create_pool("download", download_config)
        
        # 解析专用池
        parse_config = ThreadPoolConfig(
            pool_type=PoolType.PARSE,
            min_workers=2,
            max_workers=min(8, self.cpu_count or 1),
            core_workers=min(4, max(1, (self.cpu_count or 1) // 2)),
            queue_size=100,
            auto_scale=True,
            thread_name_prefix="Parse-Worker"
        )
        self.create_pool("parse", parse_config)
    
    def create_pool(self, name: str, config: ThreadPoolConfig) -> bool:
        """
        创建线程池
        
        Args:
            name: 线程池名称
            config: 线程池配置
            
        Returns:
            是否创建成功
        """
        with self.lock:
            try:
                if name in self.pools:
                    self.logger.warning(f"线程池 {name} 已存在，将替换")
                    self.shutdown_pool(name)
                
                # 创建线程池
                pool = ThreadPoolExecutor(
                    max_workers=config.core_workers,
                    thread_name_prefix=config.thread_name_prefix
                )
                
                self.pools[name] = pool
                self.pool_configs[name] = config
                self.pool_stats[name] = {
                    'created_time': time.time(),
                    'tasks_submitted': 0,
                    'tasks_completed': 0,
                    'tasks_failed': 0,
                    'current_workers': config.core_workers,
                    'peak_workers': config.core_workers,
                    'queue_size': 0,
                    'avg_execution_time': 0.0,
                    'total_execution_time': 0.0
                }
                
                self.logger.info(f"创建线程池 {name}，类型: {config.pool_type.value}，"
                               f"核心线程数: {config.core_workers}")
                return True
                
            except Exception as e:
                self.logger.error(f"创建线程池 {name} 失败: {str(e)}")
                return False
    
    def submit_task(self, pool_name: str, func: Callable[..., Any], *args, 
                   priority: int = 0, timeout: Optional[float] = None, **kwargs) -> Optional[Future[Any]]:
        """
        提交任务到指定线程池
        
        Args:
            pool_name: 线程池名称
            func: 要执行的函数
            *args: 函数参数
            priority: 任务优先级（数字越大优先级越高）
            timeout: 超时时间
            **kwargs: 函数关键字参数
            
        Returns:
            Future对象或None
        """
        with self.lock:
            if pool_name not in self.pools:
                self.logger.error(f"线程池 {pool_name} 不存在")
                return None
            
            pool = self.pools[pool_name]
            stats = self.pool_stats[pool_name]
            
            try:
                # 包装任务以收集统计信息
                wrapped_func = self._wrap_task(func, pool_name)
                
                # 提交任务
                future = pool.submit(wrapped_func, *args, **kwargs)
                
                # 更新统计
                stats['tasks_submitted'] += 1
                stats['queue_size'] = getattr(pool._work_queue, 'qsize', lambda: 0)()
                
                # 设置超时
                if timeout:
                    def timeout_handler():
                        time.sleep(timeout)
                        if not future.done():
                            future.cancel()
                            self.logger.warning(f"任务超时被取消: {func.__name__}")
                    
                    threading.Thread(target=timeout_handler, daemon=True).start()
                
                return future
                
            except Exception as e:
                self.logger.error(f"提交任务到线程池 {pool_name} 失败: {str(e)}")
                stats['tasks_failed'] += 1
                return None
    
    def _wrap_task(self, func: Callable[..., Any], pool_name: str) -> Callable[..., Any]:
        """
        包装任务以收集执行统计信息
        
        Args:
            func: 原始函数
            pool_name: 线程池名称
            
        Returns:
            包装后的函数
        """
        def wrapped(*args, **kwargs):
            start_time = time.time()
            stats = self.pool_stats[pool_name]
            
            try:
                result = func(*args, **kwargs)
                stats['tasks_completed'] += 1
                return result
            except Exception as e:
                stats['tasks_failed'] += 1
                raise e
            finally:
                # 更新执行时间统计
                execution_time = time.time() - start_time
                stats['total_execution_time'] += execution_time
                
                completed = stats['tasks_completed']
                if completed > 0:
                    stats['avg_execution_time'] = stats['total_execution_time'] / completed
        
        return wrapped
    
    def submit_batch(self, pool_name: str, func: Callable[..., Any], args_list: List[tuple], 
                    max_workers: Optional[int] = None, timeout: Optional[float] = None) -> List[Future[Any]]:
        """
        批量提交任务
        
        Args:
            pool_name: 线程池名称
            func: 要执行的函数
            args_list: 参数列表
            max_workers: 最大并发数
            timeout: 超时时间
            
        Returns:
            Future对象列表
        """
        futures = []
        
        # 限制并发数
        if max_workers:
            semaphore = threading.Semaphore(max_workers)
            
            def limited_func(*args, **kwargs):
                with semaphore:
                    return func(*args, **kwargs)
            
            target_func = limited_func
        else:
            target_func = func
        
        # 提交所有任务
        for args in args_list:
            if isinstance(args, tuple):
                future = self.submit_task(pool_name, target_func, *args, timeout=timeout)
            else:
                future = self.submit_task(pool_name, target_func, args, timeout=timeout)
            
            if future:
                futures.append(future)
        
        return futures
    
    def wait_for_completion(self, futures: List[Future[Any]], timeout: Optional[float] = None) -> Dict[str, Any]:
        """
        等待任务完成
        
        Args:
            futures: Future对象列表
            timeout: 超时时间
            
        Returns:
            完成统计信息
        """
        results = {
            'completed': [],
            'failed': [],
            'cancelled': [],
            'timeout': []
        }
        
        try:
            for future in as_completed(futures, timeout=timeout):
                try:
                    result = future.result()
                    results['completed'].append(result)
                except Exception as e:
                    results['failed'].append(str(e))
                    
        except TimeoutError:
            # 处理超时的任务
            for future in futures:
                if not future.done():
                    future.cancel()
                    results['timeout'].append(future)
                elif future.cancelled():
                    results['cancelled'].append(future)
        
        return results
    
    def auto_scale_pool(self, pool_name: str) -> bool:
        """
        自动调整线程池大小
        
        Args:
            pool_name: 线程池名称
            
        Returns:
            是否调整成功
        """
        with self.lock:
            if pool_name not in self.pools:
                return False
            
            config = self.pool_configs[pool_name]
            if not config.auto_scale:
                return False
            
            stats = self.pool_stats[pool_name]
            pool = self.pools[pool_name]
            
            try:
                # 获取当前队列大小和系统负载
                queue_size = getattr(pool._work_queue, 'qsize', lambda: 0)()
                cpu_percent = psutil.cpu_percent(interval=0.1) if psutil else 50.0
                memory_percent = psutil.virtual_memory().percent if psutil else 50.0
                
                current_workers = stats['current_workers']
                
                # 决定是否需要调整
                should_scale_up = (
                    queue_size > current_workers * 2 and
                    current_workers < config.max_workers and
                    cpu_percent < 80 and
                    memory_percent < 85
                )
                
                should_scale_down = (
                    queue_size < current_workers // 2 and
                    current_workers > config.min_workers and
                    cpu_percent < 50
                )
                
                if should_scale_up:
                    new_workers = min(current_workers + 2, config.max_workers)
                    self._resize_pool(pool_name, new_workers)
                    return True
                elif should_scale_down:
                    new_workers = max(current_workers - 1, config.min_workers)
                    self._resize_pool(pool_name, new_workers)
                    return True
                
                return False
                
            except Exception as e:
                self.logger.error(f"自动调整线程池 {pool_name} 失败: {str(e)}")
                return False
    
    def _resize_pool(self, pool_name: str, new_size: int):
        """
        调整线程池大小
        
        Args:
            pool_name: 线程池名称
            new_size: 新的线程数
        """
        try:
            pool = self.pools[pool_name]
            config = self.pool_configs[pool_name]
            stats = self.pool_stats[pool_name]
            
            # 创建新的线程池
            new_pool = ThreadPoolExecutor(
                max_workers=new_size,
                thread_name_prefix=config.thread_name_prefix
            )
            
            # 替换线程池
            old_pool = self.pools[pool_name]
            self.pools[pool_name] = new_pool
            
            # 更新统计
            stats['current_workers'] = new_size
            stats['peak_workers'] = max(stats['peak_workers'], new_size)
            
            # 异步关闭旧线程池
            def shutdown_old_pool():
                try:
                    old_pool.shutdown(wait=True)
                except Exception as e:
                    self.logger.warning(f"关闭旧线程池时出错: {str(e)}")
            
            threading.Thread(target=shutdown_old_pool, daemon=True).start()
            
            self.logger.info(f"线程池 {pool_name} 大小调整为 {new_size}")
            
        except Exception as e:
            self.logger.error(f"调整线程池 {pool_name} 大小失败: {str(e)}")
    
    def get_pool_stats(self, pool_name: Optional[str] = None) -> Dict[str, Any]:
        """
        获取线程池统计信息
        
        Args:
            pool_name: 线程池名称，None表示获取所有
            
        Returns:
            统计信息字典
        """
        with self.lock:
            if pool_name:
                if pool_name in self.pool_stats:
                    stats = self.pool_stats[pool_name].copy()
                    # 添加实时信息
                    if pool_name in self.pools:
                        pool = self.pools[pool_name]
                        stats['queue_size'] = getattr(pool._work_queue, 'qsize', lambda: 0)()
                    return stats
                else:
                    return {}
            else:
                all_stats = {}
                for name in self.pool_stats:
                    all_stats[name] = self.get_pool_stats(name)
                return all_stats
    
    def start_monitoring(self, interval: int = 30):
        """
        启动监控线程
        
        Args:
            interval: 监控间隔（秒）
        """
        if self.is_monitoring:
            return
        
        self.is_monitoring = True
        
        def monitor_loop():
            while self.is_monitoring:
                try:
                    # 自动调整所有支持的线程池
                    for pool_name in self.pools:
                        self.auto_scale_pool(pool_name)
                    
                    # 记录统计信息
                    if self.logger.isEnabledFor(logging.DEBUG):
                        stats = self.get_pool_stats()
                        self.logger.debug(f"线程池统计: {stats}")
                    
                    time.sleep(interval)
                    
                except Exception as e:
                    self.logger.error(f"监控线程出错: {str(e)}")
                    time.sleep(interval)
        
        self.monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        self.monitor_thread.start()
        
        self.logger.info(f"线程池监控已启动，间隔: {interval}秒")
    
    def stop_monitoring(self):
        """停止监控线程"""
        self.is_monitoring = False
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=5)
        self.logger.info("线程池监控已停止")
    
    def shutdown_pool(self, pool_name: str, wait: bool = True):
        """
        关闭指定线程池
        
        Args:
            pool_name: 线程池名称
            wait: 是否等待任务完成
        """
        with self.lock:
            if pool_name in self.pools:
                try:
                    pool = self.pools[pool_name]
                    pool.shutdown(wait=wait)
                    del self.pools[pool_name]
                    del self.pool_configs[pool_name]
                    del self.pool_stats[pool_name]
                    self.logger.info(f"线程池 {pool_name} 已关闭")
                except Exception as e:
                    self.logger.error(f"关闭线程池 {pool_name} 失败: {str(e)}")
    
    def shutdown_all(self, wait: bool = True):
        """
        关闭所有线程池
        
        Args:
            wait: 是否等待任务完成
        """
        self.stop_monitoring()
        
        with self.lock:
            pool_names = list(self.pools.keys())
            for pool_name in pool_names:
                self.shutdown_pool(pool_name, wait=wait)
        
        self.logger.info("所有线程池已关闭")
    
    def __enter__(self):
        """上下文管理器入口"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.shutdown_all()


# 全局线程池管理器实例
_global_pool_manager: Optional[ThreadPoolManager] = None


def get_global_pool_manager() -> ThreadPoolManager:
    """获取全局线程池管理器实例"""
    global _global_pool_manager
    if _global_pool_manager is None:
        _global_pool_manager = ThreadPoolManager()
        _global_pool_manager.start_monitoring()
    return _global_pool_manager


def shutdown_global_pool_manager():
    """关闭全局线程池管理器"""
    global _global_pool_manager
    if _global_pool_manager:
        _global_pool_manager.shutdown_all()
        _global_pool_manager = None