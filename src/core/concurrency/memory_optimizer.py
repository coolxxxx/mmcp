"""
内存优化器
提供内存使用优化和垃圾回收管理
"""

import gc
import sys
import threading
import time
import weakref
from typing import Dict, List, Any, Optional, Callable, Set
from dataclasses import dataclass
import logging
import psutil
from collections import defaultdict


@dataclass
class MemoryStats:
    """内存统计信息"""
    total_memory: int
    available_memory: int
    used_memory: int
    memory_percent: float
    process_memory: int
    process_memory_percent: float
    gc_collections: Dict[int, int]
    gc_collected: Dict[int, int]
    gc_uncollectable: Dict[int, int]
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'total_memory': self.total_memory,
            'available_memory': self.available_memory,
            'used_memory': self.used_memory,
            'memory_percent': self.memory_percent,
            'process_memory': self.process_memory,
            'process_memory_percent': self.process_memory_percent,
            'gc_collections': self.gc_collections,
            'gc_collected': self.gc_collected,
            'gc_uncollectable': self.gc_uncollectable
        }


class ObjectTracker:
    """对象跟踪器"""
    
    def __init__(self):
        """初始化对象跟踪器"""
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # 弱引用集合，跟踪对象
        self.tracked_objects: Dict[str, Set[weakref.ref]] = defaultdict(set)
        
        # 对象创建计数
        self.creation_counts: Dict[str, int] = defaultdict(int)
        
        # 对象销毁计数
        self.destruction_counts: Dict[str, int] = defaultdict(int)
        
        # 锁
        self.lock = threading.RLock()
    
    def track_object(self, obj: Any, category: str = "default"):
        """
        跟踪对象
        
        Args:
            obj: 要跟踪的对象
            category: 对象类别
        """
        with self.lock:
            def cleanup_callback(ref):
                with self.lock:
                    self.tracked_objects[category].discard(ref)
                    self.destruction_counts[category] += 1
            
            ref = weakref.ref(obj, cleanup_callback)
            self.tracked_objects[category].add(ref)
            self.creation_counts[category] += 1
    
    def get_object_count(self, category: str = None) -> Dict[str, int]:
        """
        获取对象计数
        
        Args:
            category: 对象类别，None表示所有类别
            
        Returns:
            对象计数字典
        """
        with self.lock:
            if category:
                return {
                    category: len(self.tracked_objects[category])
                }
            else:
                return {
                    cat: len(refs) for cat, refs in self.tracked_objects.items()
                }
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self.lock:
            return {
                'tracked_categories': list(self.tracked_objects.keys()),
                'active_objects': {cat: len(refs) for cat, refs in self.tracked_objects.items()},
                'creation_counts': dict(self.creation_counts),
                'destruction_counts': dict(self.destruction_counts),
                'total_active': sum(len(refs) for refs in self.tracked_objects.values()),
                'total_created': sum(self.creation_counts.values()),
                'total_destroyed': sum(self.destruction_counts.values())
            }
    
    def clear_category(self, category: str):
        """清空指定类别的跟踪"""
        with self.lock:
            if category in self.tracked_objects:
                self.tracked_objects[category].clear()
                self.creation_counts[category] = 0
                self.destruction_counts[category] = 0


class MemoryOptimizer:
    """内存优化器"""
    
    def __init__(self, gc_threshold: float = 80.0, optimization_interval: int = 30):
        """
        初始化内存优化器
        
        Args:
            gc_threshold: 触发垃圾回收的内存使用阈值（百分比）
            optimization_interval: 优化检查间隔（秒）
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self.gc_threshold = gc_threshold
        self.optimization_interval = optimization_interval
        
        # 对象跟踪器
        self.object_tracker = ObjectTracker()
        
        # 优化线程
        self.optimizer_thread: Optional[threading.Thread] = None
        self.is_optimizing = False
        
        # 缓存管理
        self.caches: Dict[str, Dict[Any, Any]] = {}
        self.cache_limits: Dict[str, int] = {}
        
        # 统计信息
        self.stats = {
            'gc_runs': 0,
            'memory_freed': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'optimization_runs': 0,
            'last_optimization_time': None
        }
        
        # 回调函数
        self.memory_warning_callbacks: List[Callable[[float], None]] = []
        self.gc_callbacks: List[Callable[[Dict[str, Any]], None]] = []
        
        # 进程信息
        self.process = psutil.Process()
        
        self.logger.info(f"内存优化器初始化完成，GC阈值: {gc_threshold}%")
    
    def start_optimization(self):
        """启动内存优化"""
        if self.is_optimizing:
            return
        
        self.is_optimizing = True
        
        def optimization_loop():
            while self.is_optimizing:
                try:
                    self._run_optimization()
                    time.sleep(self.optimization_interval)
                except Exception as e:
                    self.logger.error(f"内存优化出错: {str(e)}")
                    time.sleep(self.optimization_interval)
        
        self.optimizer_thread = threading.Thread(target=optimization_loop, daemon=True)
        self.optimizer_thread.start()
        
        self.logger.info("内存优化已启动")
    
    def stop_optimization(self):
        """停止内存优化"""
        self.is_optimizing = False
        if self.optimizer_thread and self.optimizer_thread.is_alive():
            self.optimizer_thread.join(timeout=5)
        self.logger.info("内存优化已停止")
    
    def _run_optimization(self):
        """运行优化"""
        memory_stats = self.get_memory_stats()
        
        # 检查是否需要优化
        if memory_stats.memory_percent >= self.gc_threshold:
            self.logger.info(f"内存使用率 {memory_stats.memory_percent:.1f}% 超过阈值，开始优化")
            
            # 触发内存警告回调
            for callback in self.memory_warning_callbacks:
                try:
                    callback(memory_stats.memory_percent)
                except Exception as e:
                    self.logger.warning(f"内存警告回调执行失败: {str(e)}")
            
            # 执行垃圾回收
            self.force_garbage_collection()
            
            # 清理缓存
            self.cleanup_caches()
        
        self.stats['optimization_runs'] += 1
        self.stats['last_optimization_time'] = time.time()
    
    def get_memory_stats(self) -> MemoryStats:
        """获取内存统计信息"""
        try:
            # 系统内存信息
            memory = psutil.virtual_memory()
            
            # 进程内存信息
            process_memory = self.process.memory_info()
            
            # 垃圾回收统计
            gc_stats = gc.get_stats()
            gc_collections = {i: stat['collections'] for i, stat in enumerate(gc_stats)}
            gc_collected = {i: stat['collected'] for i, stat in enumerate(gc_stats)}
            gc_uncollectable = {i: stat['uncollectable'] for i, stat in enumerate(gc_stats)}
            
            return MemoryStats(
                total_memory=memory.total,
                available_memory=memory.available,
                used_memory=memory.used,
                memory_percent=memory.percent,
                process_memory=process_memory.rss,
                process_memory_percent=self.process.memory_percent(),
                gc_collections=gc_collections,
                gc_collected=gc_collected,
                gc_uncollectable=gc_uncollectable
            )
            
        except Exception as e:
            self.logger.error(f"获取内存统计失败: {str(e)}")
            raise
    
    def force_garbage_collection(self) -> Dict[str, Any]:
        """
        强制执行垃圾回收
        
        Returns:
            垃圾回收结果
        """
        before_memory = self.process.memory_info().rss
        
        # 执行垃圾回收
        collected = {}
        for generation in range(3):
            collected[generation] = gc.collect(generation)
        
        after_memory = self.process.memory_info().rss
        memory_freed = before_memory - after_memory
        
        # 更新统计
        self.stats['gc_runs'] += 1
        self.stats['memory_freed'] += max(0, memory_freed)
        
        gc_result = {
            'collected_objects': collected,
            'memory_before': before_memory,
            'memory_after': after_memory,
            'memory_freed': memory_freed,
            'gc_count': gc.get_count(),
            'gc_threshold': gc.get_threshold()
        }
        
        # 触发GC回调
        for callback in self.gc_callbacks:
            try:
                callback(gc_result)
            except Exception as e:
                self.logger.warning(f"GC回调执行失败: {str(e)}")
        
        self.logger.info(f"垃圾回收完成，释放内存: {memory_freed} bytes")
        return gc_result
    
    def create_cache(self, name: str, max_size: int = 1000):
        """
        创建缓存
        
        Args:
            name: 缓存名称
            max_size: 最大缓存大小
        """
        self.caches[name] = {}
        self.cache_limits[name] = max_size
        self.logger.info(f"创建缓存: {name}, 最大大小: {max_size}")
    
    def get_from_cache(self, cache_name: str, key: Any) -> Any:
        """
        从缓存获取值
        
        Args:
            cache_name: 缓存名称
            key: 键
            
        Returns:
            缓存值，不存在返回None
        """
        if cache_name not in self.caches:
            self.stats['cache_misses'] += 1
            return None
        
        cache = self.caches[cache_name]
        if key in cache:
            self.stats['cache_hits'] += 1
            return cache[key]
        else:
            self.stats['cache_misses'] += 1
            return None
    
    def put_to_cache(self, cache_name: str, key: Any, value: Any):
        """
        向缓存添加值
        
        Args:
            cache_name: 缓存名称
            key: 键
            value: 值
        """
        if cache_name not in self.caches:
            self.create_cache(cache_name)
        
        cache = self.caches[cache_name]
        limit = self.cache_limits[cache_name]
        
        # 检查缓存大小限制
        if len(cache) >= limit:
            # 删除最旧的条目（简单的FIFO策略）
            oldest_key = next(iter(cache))
            del cache[oldest_key]
        
        cache[key] = value
    
    def clear_cache(self, cache_name: str):
        """
        清空指定缓存
        
        Args:
            cache_name: 缓存名称
        """
        if cache_name in self.caches:
            self.caches[cache_name].clear()
            self.logger.info(f"清空缓存: {cache_name}")
    
    def cleanup_caches(self):
        """清理所有缓存"""
        total_cleared = 0
        for cache_name, cache in self.caches.items():
            size = len(cache)
            cache.clear()
            total_cleared += size
        
        self.logger.info(f"清理缓存完成，清理了 {total_cleared} 个条目")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        cache_stats = {}
        for name, cache in self.caches.items():
            cache_stats[name] = {
                'size': len(cache),
                'limit': self.cache_limits.get(name, 0),
                'usage_percent': (len(cache) / max(1, self.cache_limits.get(name, 1))) * 100
            }
        
        return {
            'caches': cache_stats,
            'total_caches': len(self.caches),
            'cache_hits': self.stats['cache_hits'],
            'cache_misses': self.stats['cache_misses'],
            'hit_rate': (
                self.stats['cache_hits'] / 
                max(1, self.stats['cache_hits'] + self.stats['cache_misses'])
            ) * 100
        }
    
    def track_object(self, obj: Any, category: str = "default"):
        """
        跟踪对象
        
        Args:
            obj: 要跟踪的对象
            category: 对象类别
        """
        self.object_tracker.track_object(obj, category)
    
    def get_object_stats(self) -> Dict[str, Any]:
        """获取对象统计信息"""
        return self.object_tracker.get_stats()
    
    def add_memory_warning_callback(self, callback: Callable[[float], None]):
        """添加内存警告回调"""
        self.memory_warning_callbacks.append(callback)
    
    def add_gc_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """添加垃圾回收回调"""
        self.gc_callbacks.append(callback)
    
    def optimize_for_memory_usage(self) -> Dict[str, Any]:
        """
        针对内存使用进行优化
        
        Returns:
            优化结果
        """
        before_stats = self.get_memory_stats()
        
        # 强制垃圾回收
        gc_result = self.force_garbage_collection()
        
        # 清理缓存
        self.cleanup_caches()
        
        # 优化Python内部结构
        sys.intern('')  # 清理字符串缓存
        
        after_stats = self.get_memory_stats()
        
        optimization_result = {
            'before_memory': before_stats.process_memory,
            'after_memory': after_stats.process_memory,
            'memory_saved': before_stats.process_memory - after_stats.process_memory,
            'gc_result': gc_result,
            'optimization_time': time.time()
        }
        
        self.logger.info(f"内存优化完成，节省内存: {optimization_result['memory_saved']} bytes")
        return optimization_result
    
    def get_optimization_recommendations(self) -> List[str]:
        """
        获取优化建议
        
        Returns:
            优化建议列表
        """
        recommendations = []
        memory_stats = self.get_memory_stats()
        cache_stats = self.get_cache_stats()
        object_stats = self.get_object_stats()
        
        # 内存使用建议
        if memory_stats.memory_percent > 90:
            recommendations.append("系统内存使用率过高，建议增加内存或减少程序负载")
        elif memory_stats.memory_percent > 80:
            recommendations.append("系统内存使用率较高，建议监控内存使用情况")
        
        # 进程内存建议
        if memory_stats.process_memory_percent > 50:
            recommendations.append("进程内存使用率较高，建议优化内存使用")
        
        # 缓存建议
        if cache_stats['hit_rate'] < 50:
            recommendations.append("缓存命中率较低，建议调整缓存策略")
        
        # 对象建议
        if object_stats['total_active'] > 10000:
            recommendations.append("活跃对象数量较多，建议检查对象生命周期管理")
        
        # 垃圾回收建议
        if sum(memory_stats.gc_uncollectable.values()) > 0:
            recommendations.append("存在无法回收的对象，建议检查循环引用")
        
        return recommendations
    
    def get_stats(self) -> Dict[str, Any]:
        """获取完整统计信息"""
        return {
            'memory_stats': self.get_memory_stats().to_dict(),
            'cache_stats': self.get_cache_stats(),
            'object_stats': self.get_object_stats(),
            'optimization_stats': {
                'gc_runs': self.stats['gc_runs'],
                'memory_freed': self.stats['memory_freed'],
                'optimization_runs': self.stats['optimization_runs'],
                'last_optimization_time': self.stats['last_optimization_time'],
                'is_optimizing': self.is_optimizing,
                'gc_threshold': self.gc_threshold
            },
            'recommendations': self.get_optimization_recommendations()
        }


# 全局内存优化器实例
_global_memory_optimizer: Optional[MemoryOptimizer] = None


def get_global_memory_optimizer() -> MemoryOptimizer:
    """获取全局内存优化器实例"""
    global _global_memory_optimizer
    if _global_memory_optimizer is None:
        _global_memory_optimizer = MemoryOptimizer()
        _global_memory_optimizer.start_optimization()
    return _global_memory_optimizer


def shutdown_global_memory_optimizer():
    """关闭全局内存优化器"""
    global _global_memory_optimizer
    if _global_memory_optimizer:
        _global_memory_optimizer.stop_optimization()
        _global_memory_optimizer = None