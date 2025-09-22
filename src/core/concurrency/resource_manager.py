"""
资源管理器
提供系统资源监控和限制功能
"""

import threading
import time
import psutil
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass
from enum import Enum
import logging


class ResourceType(Enum):
    """资源类型"""
    CPU = "cpu"
    MEMORY = "memory"
    DISK = "disk"
    NETWORK = "network"
    CONNECTIONS = "connections"


@dataclass
class ResourceLimit:
    """资源限制"""
    resource_type: ResourceType
    max_value: float
    warning_threshold: float = 0.8
    critical_threshold: float = 0.9
    enabled: bool = True


class ResourceLimiter:
    """资源限制器"""
    
    def __init__(self, limits: List[ResourceLimit]):
        """
        初始化资源限制器
        
        Args:
            limits: 资源限制列表
        """
        self.limits = {limit.resource_type: limit for limit in limits}
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # 当前资源使用情况
        self.current_usage: Dict[ResourceType, float] = {}
        
        # 回调函数
        self.warning_callbacks: List[Callable[[ResourceType, float], None]] = []
        self.critical_callbacks: List[Callable[[ResourceType, float], None]] = []
        
        # 锁
        self.lock = threading.RLock()
    
    def add_warning_callback(self, callback: Callable[[ResourceType, float], None]):
        """添加警告回调"""
        self.warning_callbacks.append(callback)
    
    def add_critical_callback(self, callback: Callable[[ResourceType, float], None]):
        """添加严重警告回调"""
        self.critical_callbacks.append(callback)
    
    def update_usage(self, resource_type: ResourceType, usage: float):
        """
        更新资源使用情况
        
        Args:
            resource_type: 资源类型
            usage: 使用量
        """
        with self.lock:
            self.current_usage[resource_type] = usage
            
            if resource_type not in self.limits:
                return
            
            limit = self.limits[resource_type]
            if not limit.enabled:
                return
            
            usage_ratio = usage / limit.max_value
            
            # 检查是否超过阈值
            if usage_ratio >= limit.critical_threshold:
                self._trigger_critical_callbacks(resource_type, usage_ratio)
            elif usage_ratio >= limit.warning_threshold:
                self._trigger_warning_callbacks(resource_type, usage_ratio)
    
    def _trigger_warning_callbacks(self, resource_type: ResourceType, usage_ratio: float):
        """触发警告回调"""
        for callback in self.warning_callbacks:
            try:
                callback(resource_type, usage_ratio)
            except Exception as e:
                self.logger.error(f"警告回调执行失败: {str(e)}")
    
    def _trigger_critical_callbacks(self, resource_type: ResourceType, usage_ratio: float):
        """触发严重警告回调"""
        for callback in self.critical_callbacks:
            try:
                callback(resource_type, usage_ratio)
            except Exception as e:
                self.logger.error(f"严重警告回调执行失败: {str(e)}")
    
    def check_resource_available(self, resource_type: ResourceType, required: float) -> bool:
        """
        检查资源是否可用
        
        Args:
            resource_type: 资源类型
            required: 需要的资源量
            
        Returns:
            是否可用
        """
        with self.lock:
            if resource_type not in self.limits:
                return True
            
            limit = self.limits[resource_type]
            if not limit.enabled:
                return True
            
            current = self.current_usage.get(resource_type, 0)
            return (current + required) <= limit.max_value
    
    def get_available_resource(self, resource_type: ResourceType) -> float:
        """
        获取可用资源量
        
        Args:
            resource_type: 资源类型
            
        Returns:
            可用资源量
        """
        with self.lock:
            if resource_type not in self.limits:
                return float('inf')
            
            limit = self.limits[resource_type]
            current = self.current_usage.get(resource_type, 0)
            return max(0, limit.max_value - current)


class ResourceManager:
    """资源管理器"""
    
    def __init__(self, update_interval: int = 5):
        """
        初始化资源管理器
        
        Args:
            update_interval: 更新间隔（秒）
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self.update_interval = update_interval
        
        # 资源限制器
        self.limiter: Optional[ResourceLimiter] = None
        
        # 监控线程
        self.monitor_thread: Optional[threading.Thread] = None
        self.is_monitoring = False
        
        # 资源使用历史
        self.usage_history: Dict[ResourceType, List[float]] = {
            ResourceType.CPU: [],
            ResourceType.MEMORY: [],
            ResourceType.DISK: [],
            ResourceType.NETWORK: []
        }
        
        # 系统信息
        self.system_info = {
            'cpu_count': psutil.cpu_count(),
            'memory_total': psutil.virtual_memory().total,
            'disk_total': sum(psutil.disk_usage(p.mountpoint).total 
                            for p in psutil.disk_partitions()),
        }
        
        self.logger.info(f"资源管理器初始化完成，系统信息: {self.system_info}")
    
    def set_limits(self, limits: List[ResourceLimit]):
        """
        设置资源限制
        
        Args:
            limits: 资源限制列表
        """
        self.limiter = ResourceLimiter(limits)
        self.logger.info(f"设置了 {len(limits)} 个资源限制")
    
    def start_monitoring(self):
        """启动资源监控"""
        if self.is_monitoring:
            return
        
        self.is_monitoring = True
        
        def monitor_loop():
            while self.is_monitoring:
                try:
                    self._update_resource_usage()
                    time.sleep(self.update_interval)
                except Exception as e:
                    self.logger.error(f"资源监控出错: {str(e)}")
                    time.sleep(self.update_interval)
        
        self.monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        self.monitor_thread.start()
        
        self.logger.info(f"资源监控已启动，更新间隔: {self.update_interval}秒")
    
    def stop_monitoring(self):
        """停止资源监控"""
        self.is_monitoring = False
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=5)
        self.logger.info("资源监控已停止")
    
    def _update_resource_usage(self):
        """更新资源使用情况"""
        try:
            # CPU使用率
            cpu_percent = psutil.cpu_percent(interval=1)
            self._record_usage(ResourceType.CPU, cpu_percent)
            
            # 内存使用率
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            self._record_usage(ResourceType.MEMORY, memory_percent)
            
            # 磁盘使用率
            disk_usage = psutil.disk_usage('/')
            disk_percent = (disk_usage.used / disk_usage.total) * 100
            self._record_usage(ResourceType.DISK, disk_percent)
            
            # 网络连接数
            connections = len(psutil.net_connections())
            self._record_usage(ResourceType.CONNECTIONS, connections)
            
            # 更新限制器
            if self.limiter:
                self.limiter.update_usage(ResourceType.CPU, cpu_percent)
                self.limiter.update_usage(ResourceType.MEMORY, memory_percent)
                self.limiter.update_usage(ResourceType.DISK, disk_percent)
                self.limiter.update_usage(ResourceType.CONNECTIONS, connections)
            
        except Exception as e:
            self.logger.error(f"更新资源使用情况失败: {str(e)}")
    
    def _record_usage(self, resource_type: ResourceType, usage: float):
        """
        记录资源使用情况
        
        Args:
            resource_type: 资源类型
            usage: 使用量
        """
        history = self.usage_history[resource_type]
        history.append(usage)
        
        # 保持最近100个记录
        if len(history) > 100:
            history.pop(0)
    
    def get_current_usage(self) -> Dict[str, Any]:
        """
        获取当前资源使用情况
        
        Returns:
            资源使用情况字典
        """
        try:
            return {
                'cpu_percent': psutil.cpu_percent(),
                'memory_percent': psutil.virtual_memory().percent,
                'memory_available': psutil.virtual_memory().available,
                'disk_percent': (psutil.disk_usage('/').used / psutil.disk_usage('/').total) * 100,
                'disk_free': psutil.disk_usage('/').free,
                'connections': len(psutil.net_connections()),
                'processes': len(psutil.pids()),
                'load_average': psutil.getloadavg() if hasattr(psutil, 'getloadavg') else None
            }
        except Exception as e:
            self.logger.error(f"获取资源使用情况失败: {str(e)}")
            return {}
    
    def get_usage_history(self, resource_type: ResourceType, limit: int = 50) -> List[float]:
        """
        获取资源使用历史
        
        Args:
            resource_type: 资源类型
            limit: 返回记录数限制
            
        Returns:
            使用历史列表
        """
        history = self.usage_history.get(resource_type, [])
        return history[-limit:] if limit > 0 else history
    
    def get_resource_stats(self) -> Dict[str, Any]:
        """
        获取资源统计信息
        
        Returns:
            统计信息字典
        """
        stats = {}
        
        for resource_type in ResourceType:
            history = self.usage_history.get(resource_type, [])
            if history:
                stats[resource_type.value] = {
                    'current': history[-1] if history else 0,
                    'average': sum(history) / len(history),
                    'min': min(history),
                    'max': max(history),
                    'samples': len(history)
                }
        
        return stats
    
    def check_system_health(self) -> Dict[str, Any]:
        """
        检查系统健康状况
        
        Returns:
            健康状况报告
        """
        current_usage = self.get_current_usage()
        
        health_report = {
            'overall_status': 'healthy',
            'warnings': [],
            'critical_issues': [],
            'recommendations': []
        }
        
        # CPU检查
        cpu_percent = current_usage.get('cpu_percent', 0)
        if cpu_percent > 90:
            health_report['critical_issues'].append(f"CPU使用率过高: {cpu_percent:.1f}%")
            health_report['overall_status'] = 'critical'
        elif cpu_percent > 80:
            health_report['warnings'].append(f"CPU使用率较高: {cpu_percent:.1f}%")
            if health_report['overall_status'] == 'healthy':
                health_report['overall_status'] = 'warning'
        
        # 内存检查
        memory_percent = current_usage.get('memory_percent', 0)
        if memory_percent > 95:
            health_report['critical_issues'].append(f"内存使用率过高: {memory_percent:.1f}%")
            health_report['overall_status'] = 'critical'
        elif memory_percent > 85:
            health_report['warnings'].append(f"内存使用率较高: {memory_percent:.1f}%")
            if health_report['overall_status'] == 'healthy':
                health_report['overall_status'] = 'warning'
        
        # 磁盘检查
        disk_percent = current_usage.get('disk_percent', 0)
        if disk_percent > 95:
            health_report['critical_issues'].append(f"磁盘使用率过高: {disk_percent:.1f}%")
            health_report['overall_status'] = 'critical'
        elif disk_percent > 85:
            health_report['warnings'].append(f"磁盘使用率较高: {disk_percent:.1f}%")
            if health_report['overall_status'] == 'healthy':
                health_report['overall_status'] = 'warning'
        
        # 生成建议
        if health_report['critical_issues']:
            health_report['recommendations'].append("立即减少系统负载")
            health_report['recommendations'].append("考虑增加系统资源")
        elif health_report['warnings']:
            health_report['recommendations'].append("监控系统资源使用情况")
            health_report['recommendations'].append("考虑优化应用程序性能")
        
        return health_report
    
    def optimize_for_task(self, task_type: str) -> Dict[str, Any]:
        """
        为特定任务类型优化资源配置
        
        Args:
            task_type: 任务类型 (download, parse, process)
            
        Returns:
            优化建议
        """
        current_usage = self.get_current_usage()
        recommendations = {
            'max_workers': 4,
            'memory_limit': None,
            'cpu_limit': None,
            'io_limit': None
        }
        
        cpu_percent = current_usage.get('cpu_percent', 0)
        memory_percent = current_usage.get('memory_percent', 0)
        
        if task_type == 'download':
            # 下载任务主要是I/O密集型
            if cpu_percent < 50 and memory_percent < 70:
                recommendations['max_workers'] = min(20, self.system_info['cpu_count'] * 4)
            elif cpu_percent < 70 and memory_percent < 80:
                recommendations['max_workers'] = min(10, self.system_info['cpu_count'] * 2)
            else:
                recommendations['max_workers'] = max(2, self.system_info['cpu_count'])
        
        elif task_type == 'parse':
            # 解析任务主要是CPU密集型
            if cpu_percent < 60 and memory_percent < 70:
                recommendations['max_workers'] = self.system_info['cpu_count']
            elif cpu_percent < 80 and memory_percent < 85:
                recommendations['max_workers'] = max(1, self.system_info['cpu_count'] // 2)
            else:
                recommendations['max_workers'] = 1
        
        elif task_type == 'process':
            # 处理任务是混合型
            if cpu_percent < 50 and memory_percent < 60:
                recommendations['max_workers'] = min(8, self.system_info['cpu_count'] * 2)
            elif cpu_percent < 70 and memory_percent < 80:
                recommendations['max_workers'] = self.system_info['cpu_count']
            else:
                recommendations['max_workers'] = max(1, self.system_info['cpu_count'] // 2)
        
        return recommendations


# 全局资源管理器实例
_global_resource_manager: Optional[ResourceManager] = None


def get_global_resource_manager() -> ResourceManager:
    """获取全局资源管理器实例"""
    global _global_resource_manager
    if _global_resource_manager is None:
        _global_resource_manager = ResourceManager()
        _global_resource_manager.start_monitoring()
    return _global_resource_manager


def shutdown_global_resource_manager():
    """关闭全局资源管理器"""
    global _global_resource_manager
    if _global_resource_manager:
        _global_resource_manager.stop_monitoring()
        _global_resource_manager = None