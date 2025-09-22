"""
系统监控器
提供系统级性能监控和健康检查功能
"""

import time
import threading
import psutil
import platform
import socket
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)

class SystemStatus(Enum):
    """系统状态"""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"

@dataclass
class SystemMetric:
    """系统指标"""
    name: str
    value: float
    unit: str
    status: SystemStatus
    threshold_warning: float
    threshold_critical: float
    timestamp: float
    details: Dict[str, Any] = field(default_factory=dict)

@dataclass
class SystemHealth:
    """系统健康状态"""
    overall_status: SystemStatus
    timestamp: float
    metrics: Dict[str, SystemMetric]
    alerts: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)

class SystemMonitor:
    """系统监控器"""
    
    def __init__(self):
        self.is_monitoring = False
        self.monitor_thread: Optional[threading.Thread] = None
        self.monitor_interval = 10.0  # 监控间隔（秒）
        
        self.health_history: List[SystemHealth] = []
        self.alert_callbacks: List[Callable[[SystemHealth], None]] = []
        
        self._lock = threading.RLock()
        
        # 设置默认阈值
        self.thresholds = {
            'cpu_percent': {'warning': 80.0, 'critical': 95.0},
            'memory_percent': {'warning': 80.0, 'critical': 95.0},
            'disk_percent': {'warning': 85.0, 'critical': 95.0},
            'network_connections': {'warning': 1000, 'critical': 2000},
            'process_count': {'warning': 500, 'critical': 1000},
            'load_average': {'warning': 2.0, 'critical': 4.0},
            'temperature': {'warning': 70.0, 'critical': 85.0}
        }
        
        logger.info("系统监控器初始化完成")
    
    def start_monitoring(self, interval: float = 10.0):
        """启动系统监控"""
        if self.is_monitoring:
            logger.warning("系统监控已在运行")
            return
        
        self.monitor_interval = interval
        self.is_monitoring = True
        
        self.monitor_thread = threading.Thread(
            target=self._monitor_loop,
            name="SystemMonitor",
            daemon=True
        )
        self.monitor_thread.start()
        
        logger.info(f"系统监控已启动，监控间隔: {interval}秒")
    
    def stop_monitoring(self):
        """停止系统监控"""
        if not self.is_monitoring:
            return
        
        self.is_monitoring = False
        
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=10.0)
        
        logger.info("系统监控已停止")
    
    def _monitor_loop(self):
        """监控循环"""
        while self.is_monitoring:
            try:
                health = self.check_system_health()
                
                with self._lock:
                    self.health_history.append(health)
                    # 保持最近1000条记录
                    if len(self.health_history) > 1000:
                        self.health_history = self.health_history[-1000:]
                
                # 触发告警回调
                if health.overall_status in [SystemStatus.WARNING, SystemStatus.CRITICAL]:
                    for callback in self.alert_callbacks:
                        try:
                            callback(health)
                        except Exception as e:
                            logger.error(f"系统监控告警回调失败: {e}")
                
                time.sleep(self.monitor_interval)
                
            except Exception as e:
                logger.error(f"系统监控循环错误: {e}")
                time.sleep(self.monitor_interval)
    
    def check_system_health(self) -> SystemHealth:
        """检查系统健康状态"""
        timestamp = time.time()
        metrics = {}
        alerts = []
        recommendations = []
        
        try:
            # CPU使用率
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_status = self._get_status(cpu_percent, 'cpu_percent')
            metrics['cpu_percent'] = SystemMetric(
                name="CPU使用率",
                value=cpu_percent,
                unit="%",
                status=cpu_status,
                threshold_warning=self.thresholds['cpu_percent']['warning'],
                threshold_critical=self.thresholds['cpu_percent']['critical'],
                timestamp=timestamp,
                details={
                    'cpu_count': psutil.cpu_count(),
                    'cpu_count_logical': psutil.cpu_count(logical=True),
                    'cpu_freq': psutil.cpu_freq()._asdict() if psutil.cpu_freq() else {}
                }
            )
            
            if cpu_status != SystemStatus.HEALTHY:
                alerts.append(f"CPU使用率 {cpu_percent:.1f}% 超过阈值")
                if cpu_percent > 90:
                    recommendations.append("考虑优化CPU密集型任务或增加CPU资源")
            
            # 内存使用情况
            memory = psutil.virtual_memory()
            memory_status = self._get_status(memory.percent, 'memory_percent')
            metrics['memory_percent'] = SystemMetric(
                name="内存使用率",
                value=memory.percent,
                unit="%",
                status=memory_status,
                threshold_warning=self.thresholds['memory_percent']['warning'],
                threshold_critical=self.thresholds['memory_percent']['critical'],
                timestamp=timestamp,
                details={
                    'total': memory.total,
                    'available': memory.available,
                    'used': memory.used,
                    'free': memory.free
                }
            )
            
            if memory_status != SystemStatus.HEALTHY:
                alerts.append(f"内存使用率 {memory.percent:.1f}% 超过阈值")
                if memory.percent > 90:
                    recommendations.append("考虑释放内存或增加内存资源")
            
            # 磁盘使用情况
            disk = psutil.disk_usage('/')
            disk_percent = (disk.used / disk.total) * 100
            disk_status = self._get_status(disk_percent, 'disk_percent')
            metrics['disk_percent'] = SystemMetric(
                name="磁盘使用率",
                value=disk_percent,
                unit="%",
                status=disk_status,
                threshold_warning=self.thresholds['disk_percent']['warning'],
                threshold_critical=self.thresholds['disk_percent']['critical'],
                timestamp=timestamp,
                details={
                    'total': disk.total,
                    'used': disk.used,
                    'free': disk.free
                }
            )
            
            if disk_status != SystemStatus.HEALTHY:
                alerts.append(f"磁盘使用率 {disk_percent:.1f}% 超过阈值")
                if disk_percent > 90:
                    recommendations.append("清理磁盘空间或扩展存储容量")
            
            # 网络连接数
            try:
                connections = len(psutil.net_connections())
                conn_status = self._get_status(connections, 'network_connections')
                metrics['network_connections'] = SystemMetric(
                    name="网络连接数",
                    value=connections,
                    unit="个",
                    status=conn_status,
                    threshold_warning=self.thresholds['network_connections']['warning'],
                    threshold_critical=self.thresholds['network_connections']['critical'],
                    timestamp=timestamp
                )
                
                if conn_status != SystemStatus.HEALTHY:
                    alerts.append(f"网络连接数 {connections} 超过阈值")
                    recommendations.append("检查网络连接是否存在泄漏")
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                pass  # 某些系统可能无法获取网络连接信息
            
            # 进程数量
            process_count = len(psutil.pids())
            process_status = self._get_status(process_count, 'process_count')
            metrics['process_count'] = SystemMetric(
                name="进程数量",
                value=process_count,
                unit="个",
                status=process_status,
                threshold_warning=self.thresholds['process_count']['warning'],
                threshold_critical=self.thresholds['process_count']['critical'],
                timestamp=timestamp
            )
            
            if process_status != SystemStatus.HEALTHY:
                alerts.append(f"进程数量 {process_count} 超过阈值")
                recommendations.append("检查是否存在进程泄漏")
            
            # 系统负载（仅Unix系统）
            if hasattr(psutil, 'getloadavg'):
                try:
                    load_avg = psutil.getloadavg()[0]  # 1分钟平均负载
                    load_status = self._get_status(load_avg, 'load_average')
                    metrics['load_average'] = SystemMetric(
                        name="系统负载",
                        value=load_avg,
                        unit="",
                        status=load_status,
                        threshold_warning=self.thresholds['load_average']['warning'],
                        threshold_critical=self.thresholds['load_average']['critical'],
                        timestamp=timestamp,
                        details={
                            'load_1min': psutil.getloadavg()[0],
                            'load_5min': psutil.getloadavg()[1],
                            'load_15min': psutil.getloadavg()[2]
                        }
                    )
                    
                    if load_status != SystemStatus.HEALTHY:
                        alerts.append(f"系统负载 {load_avg:.2f} 超过阈值")
                        recommendations.append("系统负载过高，考虑优化或增加资源")
                except Exception:
                    pass
            
            # 温度监控（如果可用）
            try:
                temps = psutil.sensors_temperatures()
                if temps:
                    max_temp = 0
                    for name, entries in temps.items():
                        for entry in entries:
                            if entry.current and entry.current > max_temp:
                                max_temp = entry.current
                    
                    if max_temp > 0:
                        temp_status = self._get_status(max_temp, 'temperature')
                        metrics['temperature'] = SystemMetric(
                            name="系统温度",
                            value=max_temp,
                            unit="°C",
                            status=temp_status,
                            threshold_warning=self.thresholds['temperature']['warning'],
                            threshold_critical=self.thresholds['temperature']['critical'],
                            timestamp=timestamp,
                            details={'sensors': temps}
                        )
                        
                        if temp_status != SystemStatus.HEALTHY:
                            alerts.append(f"系统温度 {max_temp:.1f}°C 超过阈值")
                            recommendations.append("检查散热系统，确保通风良好")
            except Exception:
                pass  # 温度传感器可能不可用
            
        except Exception as e:
            logger.error(f"系统健康检查失败: {e}")
            alerts.append(f"系统健康检查失败: {str(e)}")
        
        # 确定整体状态
        overall_status = SystemStatus.HEALTHY
        for metric in metrics.values():
            if metric.status == SystemStatus.CRITICAL:
                overall_status = SystemStatus.CRITICAL
                break
            elif metric.status == SystemStatus.WARNING and overall_status == SystemStatus.HEALTHY:
                overall_status = SystemStatus.WARNING
        
        # 添加通用建议
        if overall_status != SystemStatus.HEALTHY:
            recommendations.extend([
                "定期监控系统资源使用情况",
                "考虑设置自动化告警机制",
                "制定资源扩展计划"
            ])
        
        health = SystemHealth(
            overall_status=overall_status,
            timestamp=timestamp,
            metrics=metrics,
            alerts=alerts,
            recommendations=recommendations
        )
        
        return health
    
    def _get_status(self, value: float, metric_name: str) -> SystemStatus:
        """根据阈值确定状态"""
        if metric_name not in self.thresholds:
            return SystemStatus.UNKNOWN
        
        thresholds = self.thresholds[metric_name]
        
        if value >= thresholds['critical']:
            return SystemStatus.CRITICAL
        elif value >= thresholds['warning']:
            return SystemStatus.WARNING
        else:
            return SystemStatus.HEALTHY
    
    def get_system_info(self) -> Dict[str, Any]:
        """获取系统信息"""
        try:
            boot_time = psutil.boot_time()
            uptime = time.time() - boot_time
            
            return {
                'platform': {
                    'system': platform.system(),
                    'release': platform.release(),
                    'version': platform.version(),
                    'machine': platform.machine(),
                    'processor': platform.processor(),
                    'architecture': platform.architecture(),
                    'hostname': socket.gethostname()
                },
                'boot_time': boot_time,
                'uptime_seconds': uptime,
                'uptime_hours': uptime / 3600,
                'python_version': platform.python_version(),
                'cpu_info': {
                    'physical_cores': psutil.cpu_count(logical=False),
                    'logical_cores': psutil.cpu_count(logical=True),
                    'max_frequency': psutil.cpu_freq().max if psutil.cpu_freq() else None,
                    'min_frequency': psutil.cpu_freq().min if psutil.cpu_freq() else None
                },
                'memory_info': {
                    'total': psutil.virtual_memory().total,
                    'available': psutil.virtual_memory().available
                },
                'disk_info': {
                    'total': psutil.disk_usage('/').total,
                    'free': psutil.disk_usage('/').free
                }
            }
        except Exception as e:
            logger.error(f"获取系统信息失败: {e}")
            return {'error': str(e)}
    
    def get_latest_health(self) -> Optional[SystemHealth]:
        """获取最新的健康状态"""
        with self._lock:
            return self.health_history[-1] if self.health_history else None
    
    def get_health_history(self, duration_minutes: int = 60) -> List[SystemHealth]:
        """获取健康状态历史"""
        end_time = time.time()
        start_time = end_time - (duration_minutes * 60)
        
        with self._lock:
            return [
                health for health in self.health_history
                if start_time <= health.timestamp <= end_time
            ]
    
    def get_health_statistics(self, duration_minutes: int = 60) -> Dict[str, Any]:
        """获取健康状态统计"""
        history = self.get_health_history(duration_minutes)
        
        if not history:
            return {}
        
        status_counts = {
            SystemStatus.HEALTHY.value: 0,
            SystemStatus.WARNING.value: 0,
            SystemStatus.CRITICAL.value: 0,
            SystemStatus.UNKNOWN.value: 0
        }
        
        for health in history:
            status_counts[health.overall_status.value] += 1
        
        total_checks = len(history)
        
        return {
            'total_checks': total_checks,
            'status_counts': status_counts,
            'status_percentages': {
                status: (count / total_checks) * 100
                for status, count in status_counts.items()
            },
            'latest_status': history[-1].overall_status.value,
            'duration_minutes': duration_minutes
        }
    
    def set_threshold(self, metric_name: str, warning: float, critical: float):
        """设置阈值"""
        self.thresholds[metric_name] = {
            'warning': warning,
            'critical': critical
        }
        logger.info(f"设置阈值: {metric_name} 警告={warning}, 严重={critical}")
    
    def add_alert_callback(self, callback: Callable[[SystemHealth], None]):
        """添加告警回调"""
        self.alert_callbacks.append(callback)
        logger.info("添加了系统监控告警回调")
    
    def export_health_report(self, filepath: str):
        """导出健康报告"""
        import json
        
        latest_health = self.get_latest_health()
        statistics = self.get_health_statistics(60)  # 最近1小时
        system_info = self.get_system_info()
        
        report = {
            'timestamp': time.time(),
            'system_info': system_info,
            'latest_health': {
                'overall_status': latest_health.overall_status.value,
                'timestamp': latest_health.timestamp,
                'metrics': {
                    name: {
                        'name': metric.name,
                        'value': metric.value,
                        'unit': metric.unit,
                        'status': metric.status.value,
                        'threshold_warning': metric.threshold_warning,
                        'threshold_critical': metric.threshold_critical
                    }
                    for name, metric in latest_health.metrics.items()
                },
                'alerts': latest_health.alerts,
                'recommendations': latest_health.recommendations
            } if latest_health else None,
            'statistics': statistics,
            'thresholds': self.thresholds
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False, default=str)
        
        logger.info(f"系统健康报告已导出到: {filepath}")

# 全局系统监控器实例
_global_system_monitor: Optional[SystemMonitor] = None

def get_global_system_monitor() -> SystemMonitor:
    """获取全局系统监控器实例"""
    global _global_system_monitor
    if _global_system_monitor is None:
        _global_system_monitor = SystemMonitor()
    return _global_system_monitor