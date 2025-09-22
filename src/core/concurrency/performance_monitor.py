"""
性能监控器
提供实时性能监控和分析功能
"""

import time
import threading
import psutil
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from collections import deque
import logging
import json
from pathlib import Path


@dataclass
class PerformanceMetric:
    """性能指标"""
    name: str
    value: float
    timestamp: float
    unit: str = ""
    category: str = "general"
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'name': self.name,
            'value': self.value,
            'timestamp': self.timestamp,
            'unit': self.unit,
            'category': self.category
        }


@dataclass
class PerformanceSnapshot:
    """性能快照"""
    timestamp: float
    metrics: List[PerformanceMetric] = field(default_factory=list)
    
    def add_metric(self, name: str, value: float, unit: str = "", category: str = "general"):
        """添加指标"""
        metric = PerformanceMetric(
            name=name,
            value=value,
            timestamp=self.timestamp,
            unit=unit,
            category=category
        )
        self.metrics.append(metric)
    
    def get_metric(self, name: str) -> Optional[PerformanceMetric]:
        """获取指标"""
        for metric in self.metrics:
            if metric.name == name:
                return metric
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'timestamp': self.timestamp,
            'metrics': [metric.to_dict() for metric in self.metrics]
        }


class PerformanceCollector:
    """性能数据收集器"""
    
    def __init__(self):
        """初始化性能收集器"""
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # 自定义指标收集器
        self.custom_collectors: Dict[str, Callable[[], Dict[str, float]]] = {}
        
        # 进程信息
        self.process = psutil.Process()
        
    def collect_system_metrics(self) -> Dict[str, float]:
        """收集系统指标"""
        try:
            return {
                'cpu_percent': psutil.cpu_percent(interval=0.1),
                'memory_percent': psutil.virtual_memory().percent,
                'memory_available': psutil.virtual_memory().available,
                'disk_usage_percent': psutil.disk_usage('/').percent,
                'disk_free': psutil.disk_usage('/').free,
                'network_sent': psutil.net_io_counters().bytes_sent,
                'network_recv': psutil.net_io_counters().bytes_recv,
                'load_average_1m': psutil.getloadavg()[0] if hasattr(psutil, 'getloadavg') else 0,
                'active_connections': len(psutil.net_connections()),
                'process_count': len(psutil.pids())
            }
        except Exception as e:
            self.logger.error(f"收集系统指标失败: {str(e)}")
            return {}
    
    def collect_process_metrics(self) -> Dict[str, float]:
        """收集进程指标"""
        try:
            with self.process.oneshot():
                memory_info = self.process.memory_info()
                cpu_times = self.process.cpu_times()
                
                return {
                    'process_cpu_percent': self.process.cpu_percent(),
                    'process_memory_rss': memory_info.rss,
                    'process_memory_vms': memory_info.vms,
                    'process_memory_percent': self.process.memory_percent(),
                    'process_cpu_user_time': cpu_times.user,
                    'process_cpu_system_time': cpu_times.system,
                    'process_threads': self.process.num_threads(),
                    'process_fds': self.process.num_fds() if hasattr(self.process, 'num_fds') else 0,
                    'process_connections': len(self.process.connections())
                }
        except Exception as e:
            self.logger.error(f"收集进程指标失败: {str(e)}")
            return {}
    
    def add_custom_collector(self, name: str, collector: Callable[[], Dict[str, float]]):
        """
        添加自定义指标收集器
        
        Args:
            name: 收集器名称
            collector: 收集器函数，返回指标字典
        """
        self.custom_collectors[name] = collector
        self.logger.info(f"添加自定义指标收集器: {name}")
    
    def collect_all_metrics(self) -> PerformanceSnapshot:
        """收集所有指标"""
        snapshot = PerformanceSnapshot(timestamp=time.time())
        
        # 系统指标
        system_metrics = self.collect_system_metrics()
        for name, value in system_metrics.items():
            snapshot.add_metric(name, value, category="system")
        
        # 进程指标
        process_metrics = self.collect_process_metrics()
        for name, value in process_metrics.items():
            snapshot.add_metric(name, value, category="process")
        
        # 自定义指标
        for collector_name, collector in self.custom_collectors.items():
            try:
                custom_metrics = collector()
                for name, value in custom_metrics.items():
                    snapshot.add_metric(f"{collector_name}_{name}", value, category="custom")
            except Exception as e:
                self.logger.error(f"自定义指标收集器 {collector_name} 执行失败: {str(e)}")
        
        return snapshot


class PerformanceMonitor:
    """性能监控器"""
    
    def __init__(self, collection_interval: int = 5, max_history: int = 1000):
        """
        初始化性能监控器
        
        Args:
            collection_interval: 收集间隔（秒）
            max_history: 最大历史记录数
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self.collection_interval = collection_interval
        self.max_history = max_history
        
        # 性能收集器
        self.collector = PerformanceCollector()
        
        # 历史数据
        self.history: deque = deque(maxlen=max_history)
        
        # 监控线程
        self.monitor_thread: Optional[threading.Thread] = None
        self.is_monitoring = False
        
        # 阈值和警报
        self.thresholds: Dict[str, Dict[str, float]] = {}
        self.alert_callbacks: List[Callable[[str, PerformanceMetric], None]] = []
        
        # 统计信息
        self.stats = {
            'total_snapshots': 0,
            'alerts_triggered': 0,
            'monitoring_start_time': None,
            'last_collection_time': None
        }
        
        self.logger.info(f"性能监控器初始化完成，收集间隔: {collection_interval}秒")
    
    def set_threshold(self, metric_name: str, warning: float, critical: float):
        """
        设置指标阈值
        
        Args:
            metric_name: 指标名称
            warning: 警告阈值
            critical: 严重阈值
        """
        self.thresholds[metric_name] = {
            'warning': warning,
            'critical': critical
        }
        self.logger.info(f"设置阈值 {metric_name}: 警告={warning}, 严重={critical}")
    
    def add_alert_callback(self, callback: Callable[[str, PerformanceMetric], None]):
        """添加警报回调"""
        self.alert_callbacks.append(callback)
    
    def start_monitoring(self):
        """启动性能监控"""
        if self.is_monitoring:
            return
        
        self.is_monitoring = True
        self.stats['monitoring_start_time'] = time.time()
        
        def monitor_loop():
            while self.is_monitoring:
                try:
                    # 收集性能数据
                    snapshot = self.collector.collect_all_metrics()
                    self.history.append(snapshot)
                    
                    # 更新统计
                    self.stats['total_snapshots'] += 1
                    self.stats['last_collection_time'] = snapshot.timestamp
                    
                    # 检查阈值
                    self._check_thresholds(snapshot)
                    
                    # 等待下次收集
                    time.sleep(self.collection_interval)
                    
                except Exception as e:
                    self.logger.error(f"性能监控出错: {str(e)}")
                    time.sleep(self.collection_interval)
        
        self.monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        self.monitor_thread.start()
        
        self.logger.info("性能监控已启动")
    
    def stop_monitoring(self):
        """停止性能监控"""
        self.is_monitoring = False
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=5)
        self.logger.info("性能监控已停止")
    
    def _check_thresholds(self, snapshot: PerformanceSnapshot):
        """检查阈值"""
        for metric in snapshot.metrics:
            if metric.name in self.thresholds:
                thresholds = self.thresholds[metric.name]
                
                alert_level = None
                if metric.value >= thresholds['critical']:
                    alert_level = 'critical'
                elif metric.value >= thresholds['warning']:
                    alert_level = 'warning'
                
                if alert_level:
                    self.stats['alerts_triggered'] += 1
                    
                    # 触发警报回调
                    for callback in self.alert_callbacks:
                        try:
                            callback(alert_level, metric)
                        except Exception as e:
                            self.logger.error(f"警报回调执行失败: {str(e)}")
    
    def get_current_snapshot(self) -> Optional[PerformanceSnapshot]:
        """获取当前性能快照"""
        if self.history:
            return self.history[-1]
        return None
    
    def get_history(self, limit: int = 100) -> List[PerformanceSnapshot]:
        """
        获取历史数据
        
        Args:
            limit: 返回记录数限制
            
        Returns:
            历史快照列表
        """
        if limit <= 0:
            return list(self.history)
        return list(self.history)[-limit:]
    
    def get_metric_history(self, metric_name: str, limit: int = 100) -> List[PerformanceMetric]:
        """
        获取特定指标的历史数据
        
        Args:
            metric_name: 指标名称
            limit: 返回记录数限制
            
        Returns:
            指标历史列表
        """
        metrics = []
        
        for snapshot in list(self.history)[-limit:]:
            metric = snapshot.get_metric(metric_name)
            if metric:
                metrics.append(metric)
        
        return metrics
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        stats = self.stats.copy()
        stats.update({
            'is_monitoring': self.is_monitoring,
            'history_size': len(self.history),
            'collection_interval': self.collection_interval,
            'thresholds_count': len(self.thresholds),
            'uptime': time.time() - self.stats['monitoring_start_time'] 
                     if self.stats['monitoring_start_time'] else 0
        })
        return stats
    
    def analyze_performance(self, duration_minutes: int = 10) -> Dict[str, Any]:
        """
        分析性能数据
        
        Args:
            duration_minutes: 分析时间段（分钟）
            
        Returns:
            分析结果
        """
        if not self.history:
            return {'error': '没有可用的性能数据'}
        
        # 获取指定时间段的数据
        cutoff_time = time.time() - (duration_minutes * 60)
        recent_snapshots = [
            snapshot for snapshot in self.history
            if snapshot.timestamp >= cutoff_time
        ]
        
        if not recent_snapshots:
            return {'error': f'没有最近 {duration_minutes} 分钟的数据'}
        
        analysis = {
            'time_range': {
                'start': recent_snapshots[0].timestamp,
                'end': recent_snapshots[-1].timestamp,
                'duration_minutes': duration_minutes,
                'sample_count': len(recent_snapshots)
            },
            'metrics': {}
        }
        
        # 分析每个指标
        metric_names = set()
        for snapshot in recent_snapshots:
            for metric in snapshot.metrics:
                metric_names.add(metric.name)
        
        for metric_name in metric_names:
            values = []
            for snapshot in recent_snapshots:
                metric = snapshot.get_metric(metric_name)
                if metric:
                    values.append(metric.value)
            
            if values:
                analysis['metrics'][metric_name] = {
                    'current': values[-1],
                    'average': sum(values) / len(values),
                    'min': min(values),
                    'max': max(values),
                    'trend': 'increasing' if values[-1] > values[0] else 'decreasing' if values[-1] < values[0] else 'stable',
                    'samples': len(values)
                }
        
        return analysis
    
    def export_data(self, file_path: str, format: str = 'json'):
        """
        导出性能数据
        
        Args:
            file_path: 导出文件路径
            format: 导出格式 (json, csv)
        """
        try:
            if format.lower() == 'json':
                data = {
                    'export_time': time.time(),
                    'stats': self.get_stats(),
                    'snapshots': [snapshot.to_dict() for snapshot in self.history]
                }
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
            
            elif format.lower() == 'csv':
                import csv
                
                with open(file_path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    
                    # 写入表头
                    if self.history:
                        first_snapshot = self.history[0]
                        headers = ['timestamp'] + [metric.name for metric in first_snapshot.metrics]
                        writer.writerow(headers)
                        
                        # 写入数据
                        for snapshot in self.history:
                            row = [snapshot.timestamp]
                            for header in headers[1:]:
                                metric = snapshot.get_metric(header)
                                row.append(metric.value if metric else '')
                            writer.writerow(row)
            
            self.logger.info(f"性能数据已导出到: {file_path}")
            
        except Exception as e:
            self.logger.error(f"导出性能数据失败: {str(e)}")
            raise
    
    def clear_history(self):
        """清空历史数据"""
        self.history.clear()
        self.stats['total_snapshots'] = 0
        self.logger.info("性能历史数据已清空")


# 全局性能监控器实例
_global_performance_monitor: Optional[PerformanceMonitor] = None


def get_global_performance_monitor() -> PerformanceMonitor:
    """获取全局性能监控器实例"""
    global _global_performance_monitor
    if _global_performance_monitor is None:
        _global_performance_monitor = PerformanceMonitor()
        _global_performance_monitor.start_monitoring()
    return _global_performance_monitor


def shutdown_global_performance_monitor():
    """关闭全局性能监控器"""
    global _global_performance_monitor
    if _global_performance_monitor:
        _global_performance_monitor.stop_monitoring()
        _global_performance_monitor = None