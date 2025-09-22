"""
性能监控器
提供实时性能监控和指标收集功能
"""

import time
import threading
import statistics
import json
from typing import Dict, List, Any, Optional, Callable, Union
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict, deque
import logging
import psutil
import gc

logger = logging.getLogger(__name__)

class MetricType(Enum):
    """指标类型"""
    COUNTER = "counter"           # 计数器
    GAUGE = "gauge"              # 仪表盘
    HISTOGRAM = "histogram"       # 直方图
    TIMER = "timer"              # 计时器
    RATE = "rate"                # 速率

@dataclass
class PerformanceMetric:
    """性能指标"""
    name: str
    metric_type: MetricType
    value: Union[int, float]
    timestamp: float
    tags: Dict[str, str] = field(default_factory=dict)
    unit: str = ""
    description: str = ""

@dataclass
class PerformanceReport:
    """性能报告"""
    start_time: float
    end_time: float
    duration: float
    metrics: List[PerformanceMetric]
    summary: Dict[str, Any] = field(default_factory=dict)
    alerts: List[str] = field(default_factory=list)

class PerformanceMonitor:
    """性能监控器"""
    
    def __init__(self, max_history: int = 10000):
        self.max_history = max_history
        self.metrics_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=max_history))
        self.counters: Dict[str, int] = defaultdict(int)
        self.gauges: Dict[str, float] = {}
        self.timers: Dict[str, List[float]] = defaultdict(list)
        self.rates: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
        
        self.is_monitoring = False
        self.monitor_thread: Optional[threading.Thread] = None
        self.monitor_interval = 1.0  # 监控间隔（秒）
        
        self.alert_thresholds: Dict[str, Dict[str, float]] = {}
        self.alert_callbacks: List[Callable[[str, PerformanceMetric], None]] = []
        
        self._lock = threading.RLock()
        
        logger.info("性能监控器初始化完成")
    
    def start_monitoring(self, interval: float = 1.0):
        """启动监控"""
        if self.is_monitoring:
            logger.warning("性能监控已在运行")
            return
        
        self.monitor_interval = interval
        self.is_monitoring = True
        
        self.monitor_thread = threading.Thread(
            target=self._monitor_loop,
            name="PerformanceMonitor",
            daemon=True
        )
        self.monitor_thread.start()
        
        logger.info(f"性能监控已启动，监控间隔: {interval}秒")
    
    def stop_monitoring(self):
        """停止监控"""
        if not self.is_monitoring:
            return
        
        self.is_monitoring = False
        
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=5.0)
        
        logger.info("性能监控已停止")
    
    def _monitor_loop(self):
        """监控循环"""
        while self.is_monitoring:
            try:
                self._collect_system_metrics()
                time.sleep(self.monitor_interval)
            except Exception as e:
                logger.error(f"监控循环错误: {e}")
                time.sleep(self.monitor_interval)
    
    def _collect_system_metrics(self):
        """收集系统指标"""
        try:
            # CPU使用率
            cpu_percent = psutil.cpu_percent(interval=None)
            self.record_gauge("system.cpu.usage", cpu_percent, unit="%")
            
            # 内存使用情况
            memory = psutil.virtual_memory()
            self.record_gauge("system.memory.usage", memory.percent, unit="%")
            self.record_gauge("system.memory.available", memory.available / (1024**3), unit="GB")
            self.record_gauge("system.memory.used", memory.used / (1024**3), unit="GB")
            
            # 磁盘使用情况
            disk = psutil.disk_usage('/')
            self.record_gauge("system.disk.usage", (disk.used / disk.total) * 100, unit="%")
            self.record_gauge("system.disk.free", disk.free / (1024**3), unit="GB")
            
            # 网络IO
            net_io = psutil.net_io_counters()
            if net_io:
                self.record_counter("system.network.bytes_sent", net_io.bytes_sent)
                self.record_counter("system.network.bytes_recv", net_io.bytes_recv)
            
            # Python进程信息
            process = psutil.Process()
            self.record_gauge("process.memory.rss", process.memory_info().rss / (1024**2), unit="MB")
            self.record_gauge("process.cpu.percent", process.cpu_percent(), unit="%")
            self.record_gauge("process.threads", process.num_threads())
            
            # 垃圾回收统计
            gc_stats = gc.get_stats()
            if gc_stats:
                for i, stat in enumerate(gc_stats):
                    self.record_counter(f"gc.generation_{i}.collections", stat['collections'])
                    self.record_counter(f"gc.generation_{i}.collected", stat['collected'])
            
        except Exception as e:
            logger.error(f"收集系统指标失败: {e}")
    
    def record_counter(self, name: str, value: int = 1, tags: Optional[Dict[str, str]] = None):
        """记录计数器指标"""
        with self._lock:
            self.counters[name] += value
            metric = PerformanceMetric(
                name=name,
                metric_type=MetricType.COUNTER,
                value=self.counters[name],
                timestamp=time.time(),
                tags=tags or {}
            )
            self.metrics_history[name].append(metric)
            self._check_alerts(metric)
    
    def record_gauge(self, name: str, value: float, tags: Optional[Dict[str, str]] = None, unit: str = ""):
        """记录仪表盘指标"""
        with self._lock:
            self.gauges[name] = value
            metric = PerformanceMetric(
                name=name,
                metric_type=MetricType.GAUGE,
                value=value,
                timestamp=time.time(),
                tags=tags or {},
                unit=unit
            )
            self.metrics_history[name].append(metric)
            self._check_alerts(metric)
    
    def record_timer(self, name: str, duration: float, tags: Optional[Dict[str, str]] = None):
        """记录计时器指标"""
        with self._lock:
            self.timers[name].append(duration)
            # 保持最近1000个记录
            if len(self.timers[name]) > 1000:
                self.timers[name] = self.timers[name][-1000:]
            
            metric = PerformanceMetric(
                name=name,
                metric_type=MetricType.TIMER,
                value=duration,
                timestamp=time.time(),
                tags=tags or {},
                unit="ms"
            )
            self.metrics_history[name].append(metric)
            self._check_alerts(metric)
    
    def record_rate(self, name: str, value: float, tags: Optional[Dict[str, str]] = None):
        """记录速率指标"""
        with self._lock:
            timestamp = time.time()
            self.rates[name].append((timestamp, value))
            
            metric = PerformanceMetric(
                name=name,
                metric_type=MetricType.RATE,
                value=value,
                timestamp=timestamp,
                tags=tags or {},
                unit="/s"
            )
            self.metrics_history[name].append(metric)
            self._check_alerts(metric)
    
    def time_function(self, name: str, tags: Optional[Dict[str, str]] = None):
        """函数计时装饰器"""
        def decorator(func):
            def wrapper(*args, **kwargs):
                start_time = time.time()
                try:
                    result = func(*args, **kwargs)
                    return result
                finally:
                    duration = (time.time() - start_time) * 1000  # 转换为毫秒
                    self.record_timer(name, duration, tags)
            return wrapper
        return decorator
    
    def get_metric_statistics(self, name: str) -> Dict[str, Any]:
        """获取指标统计信息"""
        with self._lock:
            if name not in self.metrics_history:
                return {}
            
            metrics = list(self.metrics_history[name])
            if not metrics:
                return {}
            
            values = [m.value for m in metrics]
            
            stats = {
                'count': len(values),
                'latest': values[-1] if values else 0,
                'min': min(values) if values else 0,
                'max': max(values) if values else 0,
                'mean': statistics.mean(values) if values else 0,
            }
            
            if len(values) > 1:
                stats['median'] = statistics.median(values)
                stats['stdev'] = statistics.stdev(values)
            
            # 计算百分位数
            if len(values) >= 10:
                sorted_values = sorted(values)
                stats['p50'] = statistics.median(sorted_values)
                stats['p90'] = sorted_values[int(len(sorted_values) * 0.9)]
                stats['p95'] = sorted_values[int(len(sorted_values) * 0.95)]
                stats['p99'] = sorted_values[int(len(sorted_values) * 0.99)]
            
            return stats
    
    def get_all_metrics(self) -> Dict[str, Any]:
        """获取所有指标"""
        with self._lock:
            result = {
                'counters': dict(self.counters),
                'gauges': dict(self.gauges),
                'timers': {},
                'rates': {},
                'statistics': {}
            }
            
            # 计算计时器统计
            for name, times in self.timers.items():
                if times:
                    result['timers'][name] = {
                        'count': len(times),
                        'mean': statistics.mean(times),
                        'min': min(times),
                        'max': max(times)
                    }
                    if len(times) > 1:
                        result['timers'][name]['median'] = statistics.median(times)
            
            # 计算速率统计
            for name, rate_data in self.rates.items():
                if rate_data:
                    recent_rates = [r[1] for r in list(rate_data)[-10:]]  # 最近10个数据点
                    if recent_rates:
                        result['rates'][name] = {
                            'current': recent_rates[-1],
                            'mean': statistics.mean(recent_rates),
                            'min': min(recent_rates),
                            'max': max(recent_rates)
                        }
            
            # 获取详细统计
            for name in self.metrics_history.keys():
                result['statistics'][name] = self.get_metric_statistics(name)
            
            return result
    
    def set_alert_threshold(self, metric_name: str, threshold_type: str, value: float):
        """设置告警阈值"""
        if metric_name not in self.alert_thresholds:
            self.alert_thresholds[metric_name] = {}
        self.alert_thresholds[metric_name][threshold_type] = value
        logger.info(f"设置告警阈值: {metric_name}.{threshold_type} = {value}")
    
    def add_alert_callback(self, callback: Callable[[str, PerformanceMetric], None]):
        """添加告警回调"""
        self.alert_callbacks.append(callback)
    
    def _check_alerts(self, metric: PerformanceMetric):
        """检查告警"""
        if metric.name not in self.alert_thresholds:
            return
        
        thresholds = self.alert_thresholds[metric.name]
        
        for threshold_type, threshold_value in thresholds.items():
            triggered = False
            
            if threshold_type == "max" and metric.value > threshold_value:
                triggered = True
            elif threshold_type == "min" and metric.value < threshold_value:
                triggered = True
            
            if triggered:
                alert_message = f"告警: {metric.name} {threshold_type} 阈值触发 (值: {metric.value}, 阈值: {threshold_value})"
                logger.warning(alert_message)
                
                # 调用告警回调
                for callback in self.alert_callbacks:
                    try:
                        callback(alert_message, metric)
                    except Exception as e:
                        logger.error(f"告警回调执行失败: {e}")
    
    def generate_report(self, duration_minutes: int = 60) -> PerformanceReport:
        """生成性能报告"""
        end_time = time.time()
        start_time = end_time - (duration_minutes * 60)
        
        # 收集指定时间范围内的指标
        report_metrics = []
        alerts = []
        
        with self._lock:
            for name, metrics in self.metrics_history.items():
                for metric in metrics:
                    if start_time <= metric.timestamp <= end_time:
                        report_metrics.append(metric)
        
        # 生成摘要
        summary = {
            'total_metrics': len(report_metrics),
            'metric_types': {},
            'top_metrics': {},
            'system_health': self._assess_system_health()
        }
        
        # 按类型统计指标
        for metric in report_metrics:
            metric_type = metric.metric_type.value
            if metric_type not in summary['metric_types']:
                summary['metric_types'][metric_type] = 0
            summary['metric_types'][metric_type] += 1
        
        # 获取关键指标的统计信息
        key_metrics = ['system.cpu.usage', 'system.memory.usage', 'process.memory.rss']
        for metric_name in key_metrics:
            if metric_name in self.metrics_history:
                summary['top_metrics'][metric_name] = self.get_metric_statistics(metric_name)
        
        return PerformanceReport(
            start_time=start_time,
            end_time=end_time,
            duration=duration_minutes * 60,
            metrics=report_metrics,
            summary=summary,
            alerts=alerts
        )
    
    def _assess_system_health(self) -> str:
        """评估系统健康状态"""
        try:
            cpu_usage = self.gauges.get('system.cpu.usage', 0)
            memory_usage = self.gauges.get('system.memory.usage', 0)
            
            if cpu_usage > 90 or memory_usage > 90:
                return "CRITICAL"
            elif cpu_usage > 70 or memory_usage > 70:
                return "WARNING"
            elif cpu_usage > 50 or memory_usage > 50:
                return "MODERATE"
            else:
                return "HEALTHY"
        except Exception:
            return "UNKNOWN"
    
    def export_metrics(self, filepath: str, format: str = "json"):
        """导出指标数据"""
        metrics_data = self.get_all_metrics()
        
        if format.lower() == "json":
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(metrics_data, f, indent=2, ensure_ascii=False, default=str)
        else:
            raise ValueError(f"不支持的导出格式: {format}")
        
        logger.info(f"指标数据已导出到: {filepath}")
    
    def clear_metrics(self):
        """清空指标数据"""
        with self._lock:
            self.metrics_history.clear()
            self.counters.clear()
            self.gauges.clear()
            self.timers.clear()
            self.rates.clear()
        
        logger.info("指标数据已清空")

# 全局性能监控器实例
_global_performance_monitor: Optional[PerformanceMonitor] = None

def get_global_performance_monitor() -> PerformanceMonitor:
    """获取全局性能监控器实例"""
    global _global_performance_monitor
    if _global_performance_monitor is None:
        _global_performance_monitor = PerformanceMonitor()
    return _global_performance_monitor