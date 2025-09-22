"""
资源管理器
提供系统资源监控、限制和优化功能
"""

import time
import threading
import psutil
import os
import gc
from typing import Dict, List, Any, Optional, Callable, Union
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)

class ResourceType(Enum):
    """资源类型"""
    CPU = "cpu"
    MEMORY = "memory"
    DISK = "disk"
    NETWORK = "network"
    FILE_HANDLES = "file_handles"
    THREADS = "threads"

@dataclass
class ResourceUsage:
    """资源使用情况"""
    resource_type: ResourceType
    current_usage: float
    max_usage: float
    usage_percent: float
    timestamp: float
    unit: str = ""
    details: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ResourceLimit:
    """资源限制"""
    resource_type: ResourceType
    soft_limit: float
    hard_limit: float
    unit: str = ""
    enabled: bool = True

@dataclass
class ResourceAlert:
    """资源告警"""
    resource_type: ResourceType
    alert_type: str  # "soft_limit", "hard_limit", "critical"
    current_value: float
    threshold_value: float
    message: str
    timestamp: float

class ResourceManager:
    """资源管理器"""
    
    def __init__(self):
        self.resource_limits: Dict[ResourceType, ResourceLimit] = {}
        self.resource_usage_history: Dict[ResourceType, List[ResourceUsage]] = {}
        self.alert_callbacks: List[Callable[[ResourceAlert], None]] = []
        
        self.is_monitoring = False
        self.monitor_thread: Optional[threading.Thread] = None
        self.monitor_interval = 5.0  # 监控间隔（秒）
        
        self._lock = threading.RLock()
        
        # 设置默认资源限制
        self._set_default_limits()
        
        logger.info("资源管理器初始化完成")
    
    def _set_default_limits(self):
        """设置默认资源限制"""
        # CPU限制（百分比）
        self.set_resource_limit(ResourceType.CPU, soft_limit=80.0, hard_limit=95.0, unit="%")
        
        # 内存限制（百分比）
        self.set_resource_limit(ResourceType.MEMORY, soft_limit=80.0, hard_limit=95.0, unit="%")
        
        # 磁盘限制（百分比）
        self.set_resource_limit(ResourceType.DISK, soft_limit=85.0, hard_limit=95.0, unit="%")
        
        # 线程数限制
        self.set_resource_limit(ResourceType.THREADS, soft_limit=100, hard_limit=200, unit="count")
        
        # 文件句柄限制
        self.set_resource_limit(ResourceType.FILE_HANDLES, soft_limit=500, hard_limit=1000, unit="count")
    
    def start_monitoring(self, interval: float = 5.0):
        """启动资源监控"""
        if self.is_monitoring:
            logger.warning("资源监控已在运行")
            return
        
        self.monitor_interval = interval
        self.is_monitoring = True
        
        self.monitor_thread = threading.Thread(
            target=self._monitor_loop,
            name="ResourceMonitor",
            daemon=True
        )
        self.monitor_thread.start()
        
        logger.info(f"资源监控已启动，监控间隔: {interval}秒")
    
    def stop_monitoring(self):
        """停止资源监控"""
        if not self.is_monitoring:
            return
        
        self.is_monitoring = False
        
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=10.0)
        
        logger.info("资源监控已停止")
    
    def _monitor_loop(self):
        """监控循环"""
        while self.is_monitoring:
            try:
                self._collect_resource_usage()
                self._check_resource_limits()
                time.sleep(self.monitor_interval)
            except Exception as e:
                logger.error(f"资源监控循环错误: {e}")
                time.sleep(self.monitor_interval)
    
    def _collect_resource_usage(self):
        """收集资源使用情况"""
        timestamp = time.time()
        
        try:
            # CPU使用率
            cpu_percent = psutil.cpu_percent(interval=None)
            cpu_usage = ResourceUsage(
                resource_type=ResourceType.CPU,
                current_usage=cpu_percent,
                max_usage=100.0,
                usage_percent=cpu_percent,
                timestamp=timestamp,
                unit="%",
                details={
                    "cpu_count": psutil.cpu_count(),
                    "cpu_freq": psutil.cpu_freq()._asdict() if psutil.cpu_freq() else {}
                }
            )
            self._record_usage(cpu_usage)
            
            # 内存使用情况
            memory = psutil.virtual_memory()
            memory_usage = ResourceUsage(
                resource_type=ResourceType.MEMORY,
                current_usage=memory.used,
                max_usage=memory.total,
                usage_percent=memory.percent,
                timestamp=timestamp,
                unit="bytes",
                details={
                    "available": memory.available,
                    "free": memory.free,
                    "cached": getattr(memory, 'cached', 0),
                    "buffers": getattr(memory, 'buffers', 0)
                }
            )
            self._record_usage(memory_usage)
            
            # 磁盘使用情况
            disk = psutil.disk_usage('/')
            disk_usage = ResourceUsage(
                resource_type=ResourceType.DISK,
                current_usage=disk.used,
                max_usage=disk.total,
                usage_percent=(disk.used / disk.total) * 100,
                timestamp=timestamp,
                unit="bytes",
                details={
                    "free": disk.free,
                    "total": disk.total
                }
            )
            self._record_usage(disk_usage)
            
            # 网络使用情况
            net_io = psutil.net_io_counters()
            if net_io:
                network_usage = ResourceUsage(
                    resource_type=ResourceType.NETWORK,
                    current_usage=net_io.bytes_sent + net_io.bytes_recv,
                    max_usage=float('inf'),  # 网络没有固定上限
                    usage_percent=0.0,  # 无法计算百分比
                    timestamp=timestamp,
                    unit="bytes",
                    details={
                        "bytes_sent": net_io.bytes_sent,
                        "bytes_recv": net_io.bytes_recv,
                        "packets_sent": net_io.packets_sent,
                        "packets_recv": net_io.packets_recv
                    }
                )
                self._record_usage(network_usage)
            
            # 进程资源使用
            process = psutil.Process()
            
            # 线程数
            thread_count = process.num_threads()
            thread_usage = ResourceUsage(
                resource_type=ResourceType.THREADS,
                current_usage=thread_count,
                max_usage=1000,  # 假设最大线程数
                usage_percent=(thread_count / 1000) * 100,
                timestamp=timestamp,
                unit="count"
            )
            self._record_usage(thread_usage)
            
            # 文件句柄数
            try:
                file_handles = process.num_fds() if hasattr(process, 'num_fds') else len(process.open_files())
                file_handle_usage = ResourceUsage(
                    resource_type=ResourceType.FILE_HANDLES,
                    current_usage=file_handles,
                    max_usage=1024,  # 假设最大文件句柄数
                    usage_percent=(file_handles / 1024) * 100,
                    timestamp=timestamp,
                    unit="count"
                )
                self._record_usage(file_handle_usage)
            except (psutil.AccessDenied, AttributeError):
                pass  # 某些系统可能无法获取文件句柄信息
            
        except Exception as e:
            logger.error(f"收集资源使用情况失败: {e}")
    
    def _record_usage(self, usage: ResourceUsage):
        """记录资源使用情况"""
        with self._lock:
            if usage.resource_type not in self.resource_usage_history:
                self.resource_usage_history[usage.resource_type] = []
            
            history = self.resource_usage_history[usage.resource_type]
            history.append(usage)
            
            # 保持最近1000条记录
            if len(history) > 1000:
                self.resource_usage_history[usage.resource_type] = history[-1000:]
    
    def _check_resource_limits(self):
        """检查资源限制"""
        with self._lock:
            for resource_type, usage_history in self.resource_usage_history.items():
                if not usage_history or resource_type not in self.resource_limits:
                    continue
                
                latest_usage = usage_history[-1]
                limit = self.resource_limits[resource_type]
                
                if not limit.enabled:
                    continue
                
                # 检查软限制
                if latest_usage.usage_percent > limit.soft_limit:
                    alert = ResourceAlert(
                        resource_type=resource_type,
                        alert_type="soft_limit",
                        current_value=latest_usage.usage_percent,
                        threshold_value=limit.soft_limit,
                        message=f"{resource_type.value}使用率超过软限制: {latest_usage.usage_percent:.1f}% > {limit.soft_limit}%",
                        timestamp=latest_usage.timestamp
                    )
                    self._trigger_alert(alert)
                
                # 检查硬限制
                if latest_usage.usage_percent > limit.hard_limit:
                    alert = ResourceAlert(
                        resource_type=resource_type,
                        alert_type="hard_limit",
                        current_value=latest_usage.usage_percent,
                        threshold_value=limit.hard_limit,
                        message=f"{resource_type.value}使用率超过硬限制: {latest_usage.usage_percent:.1f}% > {limit.hard_limit}%",
                        timestamp=latest_usage.timestamp
                    )
                    self._trigger_alert(alert)
                    
                    # 硬限制触发时尝试资源清理
                    self._emergency_resource_cleanup(resource_type)
    
    def _trigger_alert(self, alert: ResourceAlert):
        """触发告警"""
        logger.warning(f"资源告警: {alert.message}")
        
        # 调用告警回调
        for callback in self.alert_callbacks:
            try:
                callback(alert)
            except Exception as e:
                logger.error(f"告警回调执行失败: {e}")
    
    def _emergency_resource_cleanup(self, resource_type: ResourceType):
        """紧急资源清理"""
        logger.warning(f"执行紧急资源清理: {resource_type.value}")
        
        try:
            if resource_type == ResourceType.MEMORY:
                # 强制垃圾回收
                collected = gc.collect()
                logger.info(f"垃圾回收释放了 {collected} 个对象")
                
                # 清理缓存（如果有的话）
                # 这里可以添加应用特定的缓存清理逻辑
                
            elif resource_type == ResourceType.CPU:
                # CPU使用率过高时的处理
                # 可以考虑降低线程优先级或暂停非关键任务
                pass
                
            elif resource_type == ResourceType.DISK:
                # 磁盘空间不足时的处理
                # 可以清理临时文件或日志文件
                pass
                
        except Exception as e:
            logger.error(f"紧急资源清理失败: {e}")
    
    def set_resource_limit(self, resource_type: ResourceType, soft_limit: float, 
                          hard_limit: float, unit: str = "", enabled: bool = True):
        """设置资源限制"""
        limit = ResourceLimit(
            resource_type=resource_type,
            soft_limit=soft_limit,
            hard_limit=hard_limit,
            unit=unit,
            enabled=enabled
        )
        
        with self._lock:
            self.resource_limits[resource_type] = limit
        
        logger.info(f"设置资源限制: {resource_type.value} 软限制={soft_limit}{unit}, 硬限制={hard_limit}{unit}")
    
    def get_resource_usage(self, resource_type: ResourceType) -> Optional[ResourceUsage]:
        """获取最新的资源使用情况"""
        with self._lock:
            if resource_type not in self.resource_usage_history:
                return None
            
            history = self.resource_usage_history[resource_type]
            return history[-1] if history else None
    
    def get_resource_statistics(self, resource_type: ResourceType, 
                               duration_minutes: int = 60) -> Dict[str, Any]:
        """获取资源使用统计"""
        with self._lock:
            if resource_type not in self.resource_usage_history:
                return {}
            
            history = self.resource_usage_history[resource_type]
            if not history:
                return {}
            
            # 过滤指定时间范围内的数据
            end_time = time.time()
            start_time = end_time - (duration_minutes * 60)
            
            filtered_usage = [
                usage for usage in history
                if start_time <= usage.timestamp <= end_time
            ]
            
            if not filtered_usage:
                return {}
            
            usage_values = [usage.usage_percent for usage in filtered_usage]
            
            return {
                'count': len(usage_values),
                'current': usage_values[-1],
                'min': min(usage_values),
                'max': max(usage_values),
                'mean': sum(usage_values) / len(usage_values),
                'latest_details': filtered_usage[-1].details
            }
    
    def get_all_resource_status(self) -> Dict[str, Any]:
        """获取所有资源状态"""
        status = {}
        
        for resource_type in ResourceType:
            usage = self.get_resource_usage(resource_type)
            limit = self.resource_limits.get(resource_type)
            
            status[resource_type.value] = {
                'usage': usage.__dict__ if usage else None,
                'limit': limit.__dict__ if limit else None,
                'statistics': self.get_resource_statistics(resource_type, 10)  # 最近10分钟
            }
        
        return status
    
    def add_alert_callback(self, callback: Callable[[ResourceAlert], None]):
        """添加告警回调"""
        self.alert_callbacks.append(callback)
        logger.info("添加了资源告警回调")
    
    def optimize_resources(self):
        """优化资源使用"""
        logger.info("开始资源优化")
        
        try:
            # 执行垃圾回收
            before_gc = psutil.Process().memory_info().rss
            collected = gc.collect()
            after_gc = psutil.Process().memory_info().rss
            
            memory_freed = before_gc - after_gc
            logger.info(f"垃圾回收: 释放对象={collected}, 释放内存={memory_freed/1024/1024:.2f}MB")
            
            # 其他优化措施可以在这里添加
            
        except Exception as e:
            logger.error(f"资源优化失败: {e}")
    
    def export_resource_report(self, filepath: str):
        """导出资源报告"""
        import json
        
        report = {
            'timestamp': time.time(),
            'resource_status': self.get_all_resource_status(),
            'resource_limits': {
                rt.value: limit.__dict__ 
                for rt, limit in self.resource_limits.items()
            }
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False, default=str)
        
        logger.info(f"资源报告已导出到: {filepath}")

# 全局资源管理器实例
_global_resource_manager: Optional[ResourceManager] = None

def get_global_resource_manager() -> ResourceManager:
    """获取全局资源管理器实例"""
    global _global_resource_manager
    if _global_resource_manager is None:
        _global_resource_manager = ResourceManager()
    return _global_resource_manager