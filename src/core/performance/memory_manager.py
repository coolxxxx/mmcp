"""
内存管理器
提供内存监控、优化和泄漏检测功能
"""

import gc
import sys
import time
import threading
import tracemalloc
import weakref
from typing import Dict, List, Any, Optional, Set, Tuple
from dataclasses import dataclass, field
from collections import defaultdict
import logging
import psutil

logger = logging.getLogger(__name__)

@dataclass
class MemorySnapshot:
    """内存快照"""
    timestamp: float
    total_memory: int
    available_memory: int
    used_memory: int
    memory_percent: float
    process_memory: int
    gc_stats: List[Dict[str, int]]
    object_counts: Dict[str, int] = field(default_factory=dict)

@dataclass
class MemoryLeak:
    """内存泄漏信息"""
    object_type: str
    count_increase: int
    size_increase: int
    first_seen: float
    last_seen: float
    traceback: Optional[str] = None

class MemoryPool:
    """内存池"""
    
    def __init__(self, name: str, max_size: int = 1024 * 1024 * 100):  # 100MB默认
        self.name = name
        self.max_size = max_size
        self.current_size = 0
        self.objects: List[Any] = []
        self._lock = threading.RLock()
        
        logger.info(f"内存池 '{name}' 初始化，最大大小: {max_size / 1024 / 1024:.1f}MB")
    
    def allocate(self, size: int) -> bool:
        """分配内存"""
        with self._lock:
            if self.current_size + size > self.max_size:
                return False
            
            self.current_size += size
            return True
    
    def deallocate(self, size: int):
        """释放内存"""
        with self._lock:
            self.current_size = max(0, self.current_size - size)
    
    def get_usage(self) -> Dict[str, Any]:
        """获取使用情况"""
        with self._lock:
            return {
                'name': self.name,
                'current_size': self.current_size,
                'max_size': self.max_size,
                'usage_percent': (self.current_size / self.max_size) * 100,
                'object_count': len(self.objects)
            }
    
    def clear(self):
        """清空内存池"""
        with self._lock:
            self.objects.clear()
            self.current_size = 0
            gc.collect()
        
        logger.info(f"内存池 '{self.name}' 已清空")

class MemoryTracker:
    """内存跟踪器"""
    
    def __init__(self):
        self.snapshots: List[MemorySnapshot] = []
        self.object_refs: Dict[str, Set[weakref.ref]] = defaultdict(set)
        self.tracking_enabled = False
        self._lock = threading.RLock()
        
        # 启用tracemalloc
        if not tracemalloc.is_tracing():
            tracemalloc.start()
        
        logger.info("内存跟踪器初始化完成")
    
    def start_tracking(self):
        """开始跟踪"""
        self.tracking_enabled = True
        logger.info("内存跟踪已启动")
    
    def stop_tracking(self):
        """停止跟踪"""
        self.tracking_enabled = False
        logger.info("内存跟踪已停止")
    
    def take_snapshot(self) -> MemorySnapshot:
        """拍摄内存快照"""
        # 系统内存信息
        memory = psutil.virtual_memory()
        process = psutil.Process()
        
        # 垃圾回收统计
        gc_stats = gc.get_stats()
        
        # 对象计数
        object_counts = {}
        if self.tracking_enabled:
            object_counts = self._count_objects()
        
        snapshot = MemorySnapshot(
            timestamp=time.time(),
            total_memory=memory.total,
            available_memory=memory.available,
            used_memory=memory.used,
            memory_percent=memory.percent,
            process_memory=process.memory_info().rss,
            gc_stats=gc_stats,
            object_counts=object_counts
        )
        
        with self._lock:
            self.snapshots.append(snapshot)
            # 保持最近100个快照
            if len(self.snapshots) > 100:
                self.snapshots = self.snapshots[-100:]
        
        return snapshot
    
    def _count_objects(self) -> Dict[str, int]:
        """统计对象数量"""
        object_counts = defaultdict(int)
        
        try:
            # 统计所有对象
            for obj in gc.get_objects():
                obj_type = type(obj).__name__
                object_counts[obj_type] += 1
        except Exception as e:
            logger.error(f"统计对象数量失败: {e}")
        
        return dict(object_counts)
    
    def detect_leaks(self, threshold: int = 100) -> List[MemoryLeak]:
        """检测内存泄漏"""
        if len(self.snapshots) < 2:
            return []
        
        leaks = []
        
        with self._lock:
            first_snapshot = self.snapshots[0]
            last_snapshot = self.snapshots[-1]
            
            # 比较对象计数
            for obj_type, last_count in last_snapshot.object_counts.items():
                first_count = first_snapshot.object_counts.get(obj_type, 0)
                count_increase = last_count - first_count
                
                if count_increase > threshold:
                    leak = MemoryLeak(
                        object_type=obj_type,
                        count_increase=count_increase,
                        size_increase=0,  # 暂时无法准确计算大小增长
                        first_seen=first_snapshot.timestamp,
                        last_seen=last_snapshot.timestamp
                    )
                    leaks.append(leak)
        
        if leaks:
            logger.warning(f"检测到 {len(leaks)} 个潜在内存泄漏")
        
        return leaks
    
    def get_memory_trend(self, duration_minutes: int = 60) -> Dict[str, Any]:
        """获取内存趋势"""
        end_time = time.time()
        start_time = end_time - (duration_minutes * 60)
        
        with self._lock:
            filtered_snapshots = [
                snapshot for snapshot in self.snapshots
                if start_time <= snapshot.timestamp <= end_time
            ]
        
        if not filtered_snapshots:
            return {}
        
        memory_values = [s.process_memory for s in filtered_snapshots]
        
        return {
            'count': len(memory_values),
            'start_memory': memory_values[0],
            'end_memory': memory_values[-1],
            'min_memory': min(memory_values),
            'max_memory': max(memory_values),
            'mean_memory': sum(memory_values) / len(memory_values),
            'memory_growth': memory_values[-1] - memory_values[0],
            'growth_rate': (memory_values[-1] - memory_values[0]) / len(memory_values) if len(memory_values) > 1 else 0
        }

class MemoryOptimizer:
    """内存优化器"""
    
    def __init__(self):
        self.memory_pools: Dict[str, MemoryPool] = {}
        self.optimization_history: List[Dict[str, Any]] = []
        self._lock = threading.RLock()
        
        logger.info("内存优化器初始化完成")
    
    def create_memory_pool(self, name: str, max_size: int) -> MemoryPool:
        """创建内存池"""
        with self._lock:
            pool = MemoryPool(name, max_size)
            self.memory_pools[name] = pool
            return pool
    
    def get_memory_pool(self, name: str) -> Optional[MemoryPool]:
        """获取内存池"""
        return self.memory_pools.get(name)
    
    def optimize_memory(self) -> Dict[str, Any]:
        """优化内存使用"""
        start_time = time.time()
        
        # 获取优化前的内存使用
        process = psutil.Process()
        before_memory = process.memory_info().rss
        
        optimization_result = {
            'timestamp': start_time,
            'before_memory': before_memory,
            'actions': [],
            'after_memory': 0,
            'memory_freed': 0,
            'success': True
        }
        
        try:
            # 1. 强制垃圾回收
            collected_objects = []
            for generation in range(3):
                collected = gc.collect(generation)
                collected_objects.append(collected)
                optimization_result['actions'].append(f"GC generation {generation}: {collected} objects")
            
            # 2. 清理内存池
            for name, pool in self.memory_pools.items():
                if pool.current_size > pool.max_size * 0.8:  # 使用率超过80%时清理
                    pool.clear()
                    optimization_result['actions'].append(f"Cleared memory pool '{name}'")
            
            # 3. 清理缓存（如果有的话）
            # 这里可以添加应用特定的缓存清理逻辑
            
            # 4. 系统级内存优化
            try:
                # 在某些系统上可以尝试内存压缩
                if hasattr(gc, 'set_threshold'):
                    # 调整垃圾回收阈值
                    gc.set_threshold(700, 10, 10)
                    optimization_result['actions'].append("Adjusted GC thresholds")
            except Exception as e:
                logger.warning(f"系统级内存优化失败: {e}")
            
            # 获取优化后的内存使用
            after_memory = process.memory_info().rss
            memory_freed = before_memory - after_memory
            
            optimization_result.update({
                'after_memory': after_memory,
                'memory_freed': memory_freed,
                'memory_freed_mb': memory_freed / 1024 / 1024,
                'optimization_time': time.time() - start_time
            })
            
            logger.info(f"内存优化完成，释放内存: {memory_freed / 1024 / 1024:.2f}MB")
            
        except Exception as e:
            optimization_result['success'] = False
            optimization_result['error'] = str(e)
            logger.error(f"内存优化失败: {e}")
        
        # 记录优化历史
        with self._lock:
            self.optimization_history.append(optimization_result)
            # 保持最近50次优化记录
            if len(self.optimization_history) > 50:
                self.optimization_history = self.optimization_history[-50:]
        
        return optimization_result
    
    def get_memory_pools_status(self) -> Dict[str, Any]:
        """获取所有内存池状态"""
        with self._lock:
            return {
                name: pool.get_usage()
                for name, pool in self.memory_pools.items()
            }
    
    def get_optimization_history(self) -> List[Dict[str, Any]]:
        """获取优化历史"""
        with self._lock:
            return self.optimization_history.copy()

class MemoryManager:
    """内存管理器主类"""
    
    def __init__(self):
        self.tracker = MemoryTracker()
        self.optimizer = MemoryOptimizer()
        
        self.is_monitoring = False
        self.monitor_thread: Optional[threading.Thread] = None
        self.monitor_interval = 30.0  # 监控间隔（秒）
        
        self.auto_optimize = False
        self.auto_optimize_threshold = 80.0  # 内存使用率阈值
        
        logger.info("内存管理器初始化完成")
    
    def start_monitoring(self, interval: float = 30.0, auto_optimize: bool = False):
        """启动内存监控"""
        if self.is_monitoring:
            logger.warning("内存监控已在运行")
            return
        
        self.monitor_interval = interval
        self.auto_optimize = auto_optimize
        self.is_monitoring = True
        
        self.tracker.start_tracking()
        
        self.monitor_thread = threading.Thread(
            target=self._monitor_loop,
            name="MemoryMonitor",
            daemon=True
        )
        self.monitor_thread.start()
        
        logger.info(f"内存监控已启动，监控间隔: {interval}秒，自动优化: {auto_optimize}")
    
    def stop_monitoring(self):
        """停止内存监控"""
        if not self.is_monitoring:
            return
        
        self.is_monitoring = False
        self.tracker.stop_tracking()
        
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=10.0)
        
        logger.info("内存监控已停止")
    
    def _monitor_loop(self):
        """监控循环"""
        while self.is_monitoring:
            try:
                # 拍摄内存快照
                snapshot = self.tracker.take_snapshot()
                
                # 检查是否需要自动优化
                if self.auto_optimize and snapshot.memory_percent > self.auto_optimize_threshold:
                    logger.info(f"内存使用率 {snapshot.memory_percent:.1f}% 超过阈值，执行自动优化")
                    self.optimizer.optimize_memory()
                
                time.sleep(self.monitor_interval)
                
            except Exception as e:
                logger.error(f"内存监控循环错误: {e}")
                time.sleep(self.monitor_interval)
    
    def get_memory_status(self) -> Dict[str, Any]:
        """获取内存状态"""
        latest_snapshot = None
        if self.tracker.snapshots:
            latest_snapshot = self.tracker.snapshots[-1]
        
        return {
            'latest_snapshot': latest_snapshot.__dict__ if latest_snapshot else None,
            'memory_trend': self.tracker.get_memory_trend(60),  # 最近1小时
            'memory_pools': self.optimizer.get_memory_pools_status(),
            'optimization_history': self.optimizer.get_optimization_history()[-5:],  # 最近5次优化
            'potential_leaks': self.tracker.detect_leaks()
        }
    
    def force_optimization(self) -> Dict[str, Any]:
        """强制执行内存优化"""
        return self.optimizer.optimize_memory()
    
    def create_memory_pool(self, name: str, max_size: int) -> MemoryPool:
        """创建内存池"""
        return self.optimizer.create_memory_pool(name, max_size)
    
    def export_memory_report(self, filepath: str):
        """导出内存报告"""
        import json
        
        report = {
            'timestamp': time.time(),
            'memory_status': self.get_memory_status(),
            'system_info': {
                'python_version': sys.version,
                'platform': sys.platform,
                'tracemalloc_enabled': tracemalloc.is_tracing()
            }
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False, default=str)
        
        logger.info(f"内存报告已导出到: {filepath}")

def detect_memory_leaks(threshold: int = 100) -> List[MemoryLeak]:
    """检测内存泄漏的便捷函数"""
    tracker = MemoryTracker()
    tracker.start_tracking()
    
    # 拍摄初始快照
    tracker.take_snapshot()
    
    # 等待一段时间
    time.sleep(5)
    
    # 拍摄第二个快照
    tracker.take_snapshot()
    
    # 检测泄漏
    leaks = tracker.detect_leaks(threshold)
    
    tracker.stop_tracking()
    
    return leaks