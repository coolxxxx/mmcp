"""
性能优化器
提供自动化性能优化和调优功能
"""

import time
import threading
import gc
import sys
from typing import Dict, List, Any, Optional, Callable, Union
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)

class OptimizationType(Enum):
    """优化类型"""
    MEMORY = "memory"
    CPU = "cpu"
    IO = "io"
    NETWORK = "network"
    CACHE = "cache"
    ALGORITHM = "algorithm"

@dataclass
class OptimizationRule:
    """优化规则"""
    name: str
    optimization_type: OptimizationType
    condition: Callable[[], bool]
    action: Callable[[], Dict[str, Any]]
    priority: int = 1  # 优先级，数字越大优先级越高
    enabled: bool = True
    description: str = ""

@dataclass
class OptimizationResult:
    """优化结果"""
    rule_name: str
    optimization_type: OptimizationType
    success: bool
    timestamp: float
    execution_time: float
    before_metrics: Dict[str, Any]
    after_metrics: Dict[str, Any]
    improvement: Dict[str, Any] = field(default_factory=dict)
    error_message: str = ""

class PerformanceOptimizer:
    """性能优化器"""
    
    def __init__(self):
        self.optimization_rules: List[OptimizationRule] = []
        self.optimization_history: List[OptimizationResult] = []
        
        self.is_auto_optimizing = False
        self.auto_optimize_thread: Optional[threading.Thread] = None
        self.auto_optimize_interval = 300.0  # 自动优化间隔（秒）
        
        self._lock = threading.RLock()
        
        # 注册默认优化规则
        self._register_default_rules()
        
        logger.info("性能优化器初始化完成")
    
    def _register_default_rules(self):
        """注册默认优化规则"""
        
        # 内存优化规则
        memory_rule = OptimizationRule(
            name="memory_cleanup",
            optimization_type=OptimizationType.MEMORY,
            condition=self._memory_usage_high,
            action=self._optimize_memory,
            priority=5,
            description="当内存使用率超过80%时执行内存清理"
        )
        self.add_optimization_rule(memory_rule)
        
        # 垃圾回收优化规则
        gc_rule = OptimizationRule(
            name="garbage_collection",
            optimization_type=OptimizationType.MEMORY,
            condition=self._gc_needed,
            action=self._optimize_gc,
            priority=3,
            description="定期执行垃圾回收优化"
        )
        self.add_optimization_rule(gc_rule)
        
        # 缓存清理规则
        cache_rule = OptimizationRule(
            name="cache_cleanup",
            optimization_type=OptimizationType.CACHE,
            condition=self._cache_size_large,
            action=self._optimize_cache,
            priority=2,
            description="当缓存占用过多内存时清理缓存"
        )
        self.add_optimization_rule(cache_rule)
        
        # 线程池优化规则
        thread_rule = OptimizationRule(
            name="thread_pool_optimization",
            optimization_type=OptimizationType.CPU,
            condition=self._thread_pool_inefficient,
            action=self._optimize_thread_pool,
            priority=4,
            description="优化线程池配置以提高CPU利用率"
        )
        self.add_optimization_rule(thread_rule)
    
    def _memory_usage_high(self) -> bool:
        """检查内存使用率是否过高"""
        try:
            import psutil
            memory = psutil.virtual_memory()
            return memory.percent > 80.0
        except Exception:
            return False
    
    def _gc_needed(self) -> bool:
        """检查是否需要垃圾回收"""
        # 简单的启发式：如果上次GC后已经过了一定时间
        return True  # 总是返回True，让优化器决定是否执行
    
    def _cache_size_large(self) -> bool:
        """检查缓存大小是否过大"""
        # 这里需要根据具体应用的缓存实现来判断
        return False  # 默认不执行缓存清理
    
    def _thread_pool_inefficient(self) -> bool:
        """检查线程池是否效率低下"""
        # 这里需要根据具体的线程池使用情况来判断
        return False  # 默认不执行线程池优化
    
    def _optimize_memory(self) -> Dict[str, Any]:
        """内存优化"""
        try:
            import psutil
            
            # 获取优化前的内存使用
            process = psutil.Process()
            before_memory = process.memory_info().rss
            
            # 执行内存优化
            collected = gc.collect()
            
            # 获取优化后的内存使用
            after_memory = process.memory_info().rss
            memory_freed = before_memory - after_memory
            
            return {
                'success': True,
                'objects_collected': collected,
                'memory_freed_bytes': memory_freed,
                'memory_freed_mb': memory_freed / 1024 / 1024,
                'before_memory_mb': before_memory / 1024 / 1024,
                'after_memory_mb': after_memory / 1024 / 1024
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def _optimize_gc(self) -> Dict[str, Any]:
        """垃圾回收优化"""
        try:
            # 获取GC统计信息
            before_stats = gc.get_stats()
            
            # 执行分代垃圾回收
            collected = []
            for generation in range(3):
                count = gc.collect(generation)
                collected.append(count)
            
            # 获取优化后的统计信息
            after_stats = gc.get_stats()
            
            # 调整GC阈值（可选）
            current_thresholds = gc.get_threshold()
            
            return {
                'success': True,
                'collected_by_generation': collected,
                'total_collected': sum(collected),
                'before_stats': before_stats,
                'after_stats': after_stats,
                'current_thresholds': current_thresholds
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def _optimize_cache(self) -> Dict[str, Any]:
        """缓存优化"""
        try:
            # 这里需要根据具体的缓存实现来优化
            # 示例：清理过期缓存项
            
            return {
                'success': True,
                'cache_cleared': True,
                'message': '缓存优化完成'
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def _optimize_thread_pool(self) -> Dict[str, Any]:
        """线程池优化"""
        try:
            # 这里需要根据具体的线程池实现来优化
            # 示例：调整线程池大小
            
            return {
                'success': True,
                'thread_pool_optimized': True,
                'message': '线程池优化完成'
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def add_optimization_rule(self, rule: OptimizationRule):
        """添加优化规则"""
        with self._lock:
            self.optimization_rules.append(rule)
            # 按优先级排序
            self.optimization_rules.sort(key=lambda r: r.priority, reverse=True)
        
        logger.info(f"添加优化规则: {rule.name} (优先级: {rule.priority})")
    
    def remove_optimization_rule(self, rule_name: str) -> bool:
        """移除优化规则"""
        with self._lock:
            for i, rule in enumerate(self.optimization_rules):
                if rule.name == rule_name:
                    del self.optimization_rules[i]
                    logger.info(f"移除优化规则: {rule_name}")
                    return True
        
        logger.warning(f"未找到优化规则: {rule_name}")
        return False
    
    def enable_rule(self, rule_name: str) -> bool:
        """启用优化规则"""
        with self._lock:
            for rule in self.optimization_rules:
                if rule.name == rule_name:
                    rule.enabled = True
                    logger.info(f"启用优化规则: {rule_name}")
                    return True
        
        logger.warning(f"未找到优化规则: {rule_name}")
        return False
    
    def disable_rule(self, rule_name: str) -> bool:
        """禁用优化规则"""
        with self._lock:
            for rule in self.optimization_rules:
                if rule.name == rule_name:
                    rule.enabled = False
                    logger.info(f"禁用优化规则: {rule_name}")
                    return True
        
        logger.warning(f"未找到优化规则: {rule_name}")
        return False
    
    def run_optimization(self, rule_names: Optional[List[str]] = None) -> List[OptimizationResult]:
        """运行优化"""
        results = []
        
        with self._lock:
            rules_to_run = self.optimization_rules
            
            # 如果指定了规则名称，只运行指定的规则
            if rule_names:
                rules_to_run = [
                    rule for rule in self.optimization_rules
                    if rule.name in rule_names
                ]
        
        for rule in rules_to_run:
            if not rule.enabled:
                continue
            
            try:
                # 检查条件
                if not rule.condition():
                    continue
                
                logger.info(f"执行优化规则: {rule.name}")
                
                # 获取优化前的指标
                before_metrics = self._get_current_metrics()
                
                # 执行优化
                start_time = time.perf_counter()
                action_result = rule.action()
                end_time = time.perf_counter()
                
                # 获取优化后的指标
                after_metrics = self._get_current_metrics()
                
                # 计算改进
                improvement = self._calculate_improvement(before_metrics, after_metrics)
                
                # 创建结果
                result = OptimizationResult(
                    rule_name=rule.name,
                    optimization_type=rule.optimization_type,
                    success=action_result.get('success', True),
                    timestamp=time.time(),
                    execution_time=end_time - start_time,
                    before_metrics=before_metrics,
                    after_metrics=after_metrics,
                    improvement=improvement,
                    error_message=action_result.get('error', '')
                )
                
                results.append(result)
                
                # 记录到历史
                with self._lock:
                    self.optimization_history.append(result)
                    # 保持最近100条记录
                    if len(self.optimization_history) > 100:
                        self.optimization_history = self.optimization_history[-100:]
                
                logger.info(f"优化规则 {rule.name} 执行完成，耗时: {result.execution_time:.3f}秒")
                
            except Exception as e:
                logger.error(f"执行优化规则 {rule.name} 失败: {e}")
                
                error_result = OptimizationResult(
                    rule_name=rule.name,
                    optimization_type=rule.optimization_type,
                    success=False,
                    timestamp=time.time(),
                    execution_time=0,
                    before_metrics={},
                    after_metrics={},
                    error_message=str(e)
                )
                results.append(error_result)
        
        return results
    
    def _get_current_metrics(self) -> Dict[str, Any]:
        """获取当前性能指标"""
        try:
            import psutil
            
            # 系统指标
            memory = psutil.virtual_memory()
            cpu_percent = psutil.cpu_percent(interval=None)
            
            # 进程指标
            process = psutil.Process()
            process_memory = process.memory_info()
            
            # GC统计
            gc_stats = gc.get_stats()
            
            return {
                'system_memory_percent': memory.percent,
                'system_memory_available': memory.available,
                'cpu_percent': cpu_percent,
                'process_memory_rss': process_memory.rss,
                'process_memory_vms': process_memory.vms,
                'gc_stats': gc_stats,
                'timestamp': time.time()
            }
        except Exception as e:
            logger.error(f"获取性能指标失败: {e}")
            return {'error': str(e)}
    
    def _calculate_improvement(self, before: Dict[str, Any], after: Dict[str, Any]) -> Dict[str, Any]:
        """计算性能改进"""
        improvement = {}
        
        try:
            # 内存改进
            if 'process_memory_rss' in before and 'process_memory_rss' in after:
                memory_before = before['process_memory_rss']
                memory_after = after['process_memory_rss']
                memory_saved = memory_before - memory_after
                memory_saved_percent = (memory_saved / memory_before) * 100 if memory_before > 0 else 0
                
                improvement['memory_saved_bytes'] = memory_saved
                improvement['memory_saved_mb'] = memory_saved / 1024 / 1024
                improvement['memory_saved_percent'] = memory_saved_percent
            
            # CPU改进
            if 'cpu_percent' in before and 'cpu_percent' in after:
                cpu_before = before['cpu_percent']
                cpu_after = after['cpu_percent']
                cpu_improvement = cpu_before - cpu_after
                
                improvement['cpu_improvement_percent'] = cpu_improvement
            
            # 系统内存改进
            if 'system_memory_percent' in before and 'system_memory_percent' in after:
                sys_mem_before = before['system_memory_percent']
                sys_mem_after = after['system_memory_percent']
                sys_mem_improvement = sys_mem_before - sys_mem_after
                
                improvement['system_memory_improvement_percent'] = sys_mem_improvement
            
        except Exception as e:
            logger.error(f"计算性能改进失败: {e}")
            improvement['calculation_error'] = str(e)
        
        return improvement
    
    def start_auto_optimization(self, interval: float = 300.0):
        """启动自动优化"""
        if self.is_auto_optimizing:
            logger.warning("自动优化已在运行")
            return
        
        self.auto_optimize_interval = interval
        self.is_auto_optimizing = True
        
        self.auto_optimize_thread = threading.Thread(
            target=self._auto_optimize_loop,
            name="AutoOptimizer",
            daemon=True
        )
        self.auto_optimize_thread.start()
        
        logger.info(f"自动优化已启动，优化间隔: {interval}秒")
    
    def stop_auto_optimization(self):
        """停止自动优化"""
        if not self.is_auto_optimizing:
            return
        
        self.is_auto_optimizing = False
        
        if self.auto_optimize_thread and self.auto_optimize_thread.is_alive():
            self.auto_optimize_thread.join(timeout=10.0)
        
        logger.info("自动优化已停止")
    
    def _auto_optimize_loop(self):
        """自动优化循环"""
        while self.is_auto_optimizing:
            try:
                logger.debug("执行自动优化检查")
                results = self.run_optimization()
                
                if results:
                    successful_optimizations = [r for r in results if r.success]
                    logger.info(f"自动优化完成，成功执行 {len(successful_optimizations)} 个优化规则")
                
                time.sleep(self.auto_optimize_interval)
                
            except Exception as e:
                logger.error(f"自动优化循环错误: {e}")
                time.sleep(self.auto_optimize_interval)
    
    def get_optimization_rules(self) -> List[Dict[str, Any]]:
        """获取所有优化规则信息"""
        with self._lock:
            return [
                {
                    'name': rule.name,
                    'optimization_type': rule.optimization_type.value,
                    'priority': rule.priority,
                    'enabled': rule.enabled,
                    'description': rule.description
                }
                for rule in self.optimization_rules
            ]
    
    def get_optimization_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """获取优化历史"""
        with self._lock:
            history = self.optimization_history[-limit:] if limit > 0 else self.optimization_history
            
            return [
                {
                    'rule_name': result.rule_name,
                    'optimization_type': result.optimization_type.value,
                    'success': result.success,
                    'timestamp': result.timestamp,
                    'execution_time': result.execution_time,
                    'improvement': result.improvement,
                    'error_message': result.error_message
                }
                for result in history
            ]
    
    def get_optimization_statistics(self) -> Dict[str, Any]:
        """获取优化统计信息"""
        with self._lock:
            if not self.optimization_history:
                return {}
            
            total_optimizations = len(self.optimization_history)
            successful_optimizations = sum(1 for r in self.optimization_history if r.success)
            failed_optimizations = total_optimizations - successful_optimizations
            
            # 按类型统计
            type_stats = {}
            for result in self.optimization_history:
                opt_type = result.optimization_type.value
                if opt_type not in type_stats:
                    type_stats[opt_type] = {'total': 0, 'successful': 0}
                
                type_stats[opt_type]['total'] += 1
                if result.success:
                    type_stats[opt_type]['successful'] += 1
            
            # 计算总体改进
            total_memory_saved = sum(
                r.improvement.get('memory_saved_bytes', 0)
                for r in self.optimization_history if r.success
            )
            
            return {
                'total_optimizations': total_optimizations,
                'successful_optimizations': successful_optimizations,
                'failed_optimizations': failed_optimizations,
                'success_rate': (successful_optimizations / total_optimizations) * 100,
                'optimization_by_type': type_stats,
                'total_memory_saved_bytes': total_memory_saved,
                'total_memory_saved_mb': total_memory_saved / 1024 / 1024,
                'is_auto_optimizing': self.is_auto_optimizing,
                'auto_optimize_interval': self.auto_optimize_interval
            }
    
    def export_optimization_report(self, filepath: str):
        """导出优化报告"""
        import json
        
        report = {
            'timestamp': time.time(),
            'optimization_rules': self.get_optimization_rules(),
            'optimization_history': self.get_optimization_history(),
            'optimization_statistics': self.get_optimization_statistics(),
            'current_metrics': self._get_current_metrics()
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False, default=str)
        
        logger.info(f"优化报告已导出到: {filepath}")

# 全局性能优化器实例
_global_performance_optimizer: Optional[PerformanceOptimizer] = None

def get_global_performance_optimizer() -> PerformanceOptimizer:
    """获取全局性能优化器实例"""
    global _global_performance_optimizer
    if _global_performance_optimizer is None:
        _global_performance_optimizer = PerformanceOptimizer()
    return _global_performance_optimizer