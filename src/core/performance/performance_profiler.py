"""
性能分析器
提供代码性能分析、热点检测和优化建议功能
"""

import cProfile
import pstats
import time
import threading
import functools
import io
import sys
from typing import Dict, List, Any, Optional, Callable, Union
from dataclasses import dataclass, field
from contextlib import contextmanager
import logging

logger = logging.getLogger(__name__)

@dataclass
class ProfileResult:
    """性能分析结果"""
    function_name: str
    filename: str
    line_number: int
    call_count: int
    total_time: float
    cumulative_time: float
    per_call_time: float
    per_call_cumulative: float

@dataclass
class HotSpot:
    """性能热点"""
    function_name: str
    total_time: float
    call_count: int
    average_time: float
    percentage: float
    optimization_suggestion: str = ""

@dataclass
class PerformanceReport:
    """性能报告"""
    timestamp: float
    total_execution_time: float
    total_function_calls: int
    top_functions: List[ProfileResult]
    hot_spots: List[HotSpot]
    memory_usage: Dict[str, Any] = field(default_factory=dict)
    recommendations: List[str] = field(default_factory=list)

class FunctionProfiler:
    """函数性能分析器"""
    
    def __init__(self):
        self.profiles: Dict[str, List[ProfileResult]] = {}
        self.execution_times: Dict[str, List[float]] = {}
        self._lock = threading.RLock()
        
        logger.info("函数性能分析器初始化完成")
    
    def profile_function(self, func_name: str = None):
        """函数性能分析装饰器"""
        def decorator(func: Callable) -> Callable:
            name = func_name or f"{func.__module__}.{func.__name__}"
            
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                start_time = time.perf_counter()
                
                try:
                    result = func(*args, **kwargs)
                    return result
                finally:
                    end_time = time.perf_counter()
                    execution_time = end_time - start_time
                    
                    self._record_execution(name, execution_time)
            
            return wrapper
        return decorator
    
    def _record_execution(self, func_name: str, execution_time: float):
        """记录函数执行时间"""
        with self._lock:
            if func_name not in self.execution_times:
                self.execution_times[func_name] = []
            
            self.execution_times[func_name].append(execution_time)
            
            # 保持最近1000次执行记录
            if len(self.execution_times[func_name]) > 1000:
                self.execution_times[func_name] = self.execution_times[func_name][-1000:]
    
    def get_function_stats(self, func_name: str) -> Dict[str, Any]:
        """获取函数统计信息"""
        with self._lock:
            if func_name not in self.execution_times:
                return {}
            
            times = self.execution_times[func_name]
            if not times:
                return {}
            
            return {
                'function_name': func_name,
                'call_count': len(times),
                'total_time': sum(times),
                'average_time': sum(times) / len(times),
                'min_time': min(times),
                'max_time': max(times),
                'recent_average': sum(times[-10:]) / min(10, len(times))  # 最近10次平均
            }
    
    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """获取所有函数统计信息"""
        with self._lock:
            return {
                func_name: self.get_function_stats(func_name)
                for func_name in self.execution_times.keys()
            }
    
    def identify_slow_functions(self, threshold: float = 1.0) -> List[Dict[str, Any]]:
        """识别慢函数"""
        slow_functions = []
        
        for func_name, stats in self.get_all_stats().items():
            if stats and stats.get('average_time', 0) > threshold:
                slow_functions.append(stats)
        
        # 按平均执行时间排序
        slow_functions.sort(key=lambda x: x.get('average_time', 0), reverse=True)
        
        return slow_functions

class CodeProfiler:
    """代码性能分析器"""
    
    def __init__(self):
        self.profiler: Optional[cProfile.Profile] = None
        self.is_profiling = False
        self.profile_results: List[PerformanceReport] = []
        self._lock = threading.RLock()
        
        logger.info("代码性能分析器初始化完成")
    
    def start_profiling(self):
        """开始性能分析"""
        if self.is_profiling:
            logger.warning("性能分析已在运行")
            return
        
        with self._lock:
            self.profiler = cProfile.Profile()
            self.profiler.enable()
            self.is_profiling = True
        
        logger.info("代码性能分析已启动")
    
    def stop_profiling(self) -> PerformanceReport:
        """停止性能分析并生成报告"""
        if not self.is_profiling or not self.profiler:
            logger.warning("性能分析未在运行")
            return None
        
        with self._lock:
            self.profiler.disable()
            self.is_profiling = False
            
            # 生成分析报告
            report = self._generate_report()
            self.profile_results.append(report)
            
            # 保持最近20个报告
            if len(self.profile_results) > 20:
                self.profile_results = self.profile_results[-20:]
        
        logger.info("代码性能分析已停止，报告已生成")
        return report
    
    def _generate_report(self) -> PerformanceReport:
        """生成性能报告"""
        if not self.profiler:
            return None
        
        # 创建统计对象
        stats_stream = io.StringIO()
        stats = pstats.Stats(self.profiler, stream=stats_stream)
        stats.sort_stats('cumulative')
        
        # 获取顶级函数
        top_functions = []
        hot_spots = []
        
        try:
            # 获取统计数据
            stats_data = stats.get_stats_profile()
            total_calls = stats_data.total_calls
            total_time = stats_data.total_tt
            
            # 分析顶级函数
            for (filename, line_number, function_name), (call_count, reccall_count, total_time_func, cumulative_time) in stats_data.stats.items():
                if call_count > 0:
                    profile_result = ProfileResult(
                        function_name=function_name,
                        filename=filename,
                        line_number=line_number,
                        call_count=call_count,
                        total_time=total_time_func,
                        cumulative_time=cumulative_time,
                        per_call_time=total_time_func / call_count,
                        per_call_cumulative=cumulative_time / call_count
                    )
                    top_functions.append(profile_result)
            
            # 按累积时间排序
            top_functions.sort(key=lambda x: x.cumulative_time, reverse=True)
            top_functions = top_functions[:20]  # 取前20个
            
            # 识别热点
            for func in top_functions[:10]:  # 取前10个作为热点
                percentage = (func.cumulative_time / total_time) * 100 if total_time > 0 else 0
                
                hot_spot = HotSpot(
                    function_name=func.function_name,
                    total_time=func.total_time,
                    call_count=func.call_count,
                    average_time=func.per_call_time,
                    percentage=percentage,
                    optimization_suggestion=self._get_optimization_suggestion(func)
                )
                hot_spots.append(hot_spot)
            
            # 生成优化建议
            recommendations = self._generate_recommendations(hot_spots)
            
            report = PerformanceReport(
                timestamp=time.time(),
                total_execution_time=total_time,
                total_function_calls=total_calls,
                top_functions=top_functions,
                hot_spots=hot_spots,
                recommendations=recommendations
            )
            
        except Exception as e:
            logger.error(f"生成性能报告失败: {e}")
            report = PerformanceReport(
                timestamp=time.time(),
                total_execution_time=0,
                total_function_calls=0,
                top_functions=[],
                hot_spots=[],
                recommendations=[f"报告生成失败: {str(e)}"]
            )
        
        return report
    
    def _get_optimization_suggestion(self, func: ProfileResult) -> str:
        """获取优化建议"""
        suggestions = []
        
        # 基于调用次数的建议
        if func.call_count > 10000:
            suggestions.append("考虑减少函数调用次数或使用缓存")
        
        # 基于执行时间的建议
        if func.per_call_time > 0.1:
            suggestions.append("函数执行时间较长，考虑算法优化")
        
        # 基于文件类型的建议
        if 'io' in func.filename.lower() or 'file' in func.function_name.lower():
            suggestions.append("I/O操作较多，考虑批量处理或异步操作")
        
        if 'network' in func.filename.lower() or 'request' in func.function_name.lower():
            suggestions.append("网络操作较多，考虑连接池或并发处理")
        
        return "; ".join(suggestions) if suggestions else "暂无特定建议"
    
    def _generate_recommendations(self, hot_spots: List[HotSpot]) -> List[str]:
        """生成优化建议"""
        recommendations = []
        
        if not hot_spots:
            return ["未发现明显性能瓶颈"]
        
        # 分析热点函数
        top_hot_spot = hot_spots[0]
        if top_hot_spot.percentage > 50:
            recommendations.append(f"函数 '{top_hot_spot.function_name}' 占用了 {top_hot_spot.percentage:.1f}% 的执行时间，建议优先优化")
        
        # 分析调用频率
        high_frequency_funcs = [hs for hs in hot_spots if hs.call_count > 1000]
        if high_frequency_funcs:
            recommendations.append(f"发现 {len(high_frequency_funcs)} 个高频调用函数，考虑缓存或算法优化")
        
        # 分析平均执行时间
        slow_funcs = [hs for hs in hot_spots if hs.average_time > 0.01]
        if slow_funcs:
            recommendations.append(f"发现 {len(slow_funcs)} 个执行较慢的函数，建议进行性能优化")
        
        # 通用建议
        recommendations.extend([
            "考虑使用性能分析工具进一步分析瓶颈",
            "检查是否存在不必要的重复计算",
            "考虑使用更高效的数据结构和算法",
            "对于I/O密集型操作，考虑使用异步编程"
        ])
        
        return recommendations
    
    @contextmanager
    def profile_context(self):
        """性能分析上下文管理器"""
        self.start_profiling()
        try:
            yield
        finally:
            report = self.stop_profiling()
            return report
    
    def get_latest_report(self) -> Optional[PerformanceReport]:
        """获取最新的性能报告"""
        with self._lock:
            return self.profile_results[-1] if self.profile_results else None
    
    def get_all_reports(self) -> List[PerformanceReport]:
        """获取所有性能报告"""
        with self._lock:
            return self.profile_results.copy()
    
    def export_report(self, report: PerformanceReport, filepath: str, format: str = 'json'):
        """导出性能报告"""
        if format.lower() == 'json':
            import json
            
            # 转换为可序列化的格式
            report_dict = {
                'timestamp': report.timestamp,
                'total_execution_time': report.total_execution_time,
                'total_function_calls': report.total_function_calls,
                'top_functions': [
                    {
                        'function_name': func.function_name,
                        'filename': func.filename,
                        'line_number': func.line_number,
                        'call_count': func.call_count,
                        'total_time': func.total_time,
                        'cumulative_time': func.cumulative_time,
                        'per_call_time': func.per_call_time,
                        'per_call_cumulative': func.per_call_cumulative
                    }
                    for func in report.top_functions
                ],
                'hot_spots': [
                    {
                        'function_name': hs.function_name,
                        'total_time': hs.total_time,
                        'call_count': hs.call_count,
                        'average_time': hs.average_time,
                        'percentage': hs.percentage,
                        'optimization_suggestion': hs.optimization_suggestion
                    }
                    for hs in report.hot_spots
                ],
                'recommendations': report.recommendations
            }
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(report_dict, f, indent=2, ensure_ascii=False)
        
        elif format.lower() == 'txt':
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(f"性能分析报告\n")
                f.write(f"生成时间: {time.ctime(report.timestamp)}\n")
                f.write(f"总执行时间: {report.total_execution_time:.4f}秒\n")
                f.write(f"总函数调用: {report.total_function_calls}\n\n")
                
                f.write("热点函数:\n")
                for i, hs in enumerate(report.hot_spots, 1):
                    f.write(f"{i}. {hs.function_name}\n")
                    f.write(f"   执行时间: {hs.total_time:.4f}秒 ({hs.percentage:.1f}%)\n")
                    f.write(f"   调用次数: {hs.call_count}\n")
                    f.write(f"   平均时间: {hs.average_time:.6f}秒\n")
                    f.write(f"   优化建议: {hs.optimization_suggestion}\n\n")
                
                f.write("优化建议:\n")
                for i, rec in enumerate(report.recommendations, 1):
                    f.write(f"{i}. {rec}\n")
        
        logger.info(f"性能报告已导出到: {filepath}")

class PerformanceProfiler:
    """综合性能分析器"""
    
    def __init__(self):
        self.function_profiler = FunctionProfiler()
        self.code_profiler = CodeProfiler()
        
        logger.info("综合性能分析器初始化完成")
    
    def profile_function(self, func_name: str = None):
        """函数性能分析装饰器"""
        return self.function_profiler.profile_function(func_name)
    
    def start_code_profiling(self):
        """开始代码性能分析"""
        self.code_profiler.start_profiling()
    
    def stop_code_profiling(self) -> PerformanceReport:
        """停止代码性能分析"""
        return self.code_profiler.stop_profiling()
    
    def get_comprehensive_report(self) -> Dict[str, Any]:
        """获取综合性能报告"""
        return {
            'function_stats': self.function_profiler.get_all_stats(),
            'slow_functions': self.function_profiler.identify_slow_functions(),
            'latest_profile': self.code_profiler.get_latest_report(),
            'timestamp': time.time()
        }

# 全局性能分析器实例
_global_profiler: Optional[PerformanceProfiler] = None

def get_global_profiler() -> PerformanceProfiler:
    """获取全局性能分析器实例"""
    global _global_profiler
    if _global_profiler is None:
        _global_profiler = PerformanceProfiler()
    return _global_profiler

def profile_function(func_name: str = None):
    """性能分析装饰器的便捷函数"""
    return get_global_profiler().profile_function(func_name)