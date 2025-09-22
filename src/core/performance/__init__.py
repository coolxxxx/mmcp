"""
性能监控和资源管理模块
提供全面的性能监控、资源管理和优化功能
"""

# 导入性能监控组件
try:
    from .performance_monitor import (
        PerformanceMonitor,
        MetricType,
        PerformanceMetric,
        PerformanceReport,
        get_global_performance_monitor
    )
    _performance_monitor_available = True
except ImportError as e:
    import logging
    logging.getLogger(__name__).warning(f"性能监控器导入失败: {e}")
    _performance_monitor_available = False

# 导入资源管理组件
try:
    from .resource_manager import (
        ResourceManager,
        ResourceType,
        ResourceUsage,
        ResourceLimit,
        ResourceAlert,
        get_global_resource_manager
    )
    _resource_manager_available = True
except ImportError as e:
    import logging
    logging.getLogger(__name__).warning(f"资源管理器导入失败: {e}")
    _resource_manager_available = False

# 导入内存管理组件
try:
    from .memory_manager import (
        MemoryManager,
        MemoryPool,
        MemoryTracker,
        MemoryOptimizer,
        detect_memory_leaks
    )
    _memory_manager_available = True
except ImportError as e:
    import logging
    logging.getLogger(__name__).warning(f"内存管理器导入失败: {e}")
    _memory_manager_available = False

# 导入性能分析器
try:
    from .performance_profiler import (
        PerformanceProfiler,
        ProfileResult,
        HotSpot,
        PerformanceReport as ProfilerReport,
        get_global_profiler,
        profile_function
    )
    _performance_profiler_available = True
except ImportError as e:
    import logging
    logging.getLogger(__name__).warning(f"性能分析器导入失败: {e}")
    _performance_profiler_available = False

# 导入系统监控器
try:
    from .system_monitor import (
        SystemMonitor,
        SystemMetric,
        SystemHealth,
        SystemStatus,
        get_global_system_monitor
    )
    _system_monitor_available = True
except ImportError as e:
    import logging
    logging.getLogger(__name__).warning(f"系统监控器导入失败: {e}")
    _system_monitor_available = False

# 导入性能优化器
try:
    from .performance_optimizer import (
        PerformanceOptimizer,
        OptimizationRule,
        OptimizationResult,
        OptimizationType,
        get_global_performance_optimizer
    )
    _performance_optimizer_available = True
except ImportError as e:
    import logging
    logging.getLogger(__name__).warning(f"性能优化器导入失败: {e}")
    _performance_optimizer_available = False

# 模块可用性检查
def check_module_availability():
    """检查模块可用性"""
    return {
        'performance_monitor': _performance_monitor_available,
        'resource_manager': _resource_manager_available,
        'memory_manager': _memory_manager_available,
        'performance_profiler': _performance_profiler_available,
        'system_monitor': _system_monitor_available,
        'performance_optimizer': _performance_optimizer_available
    }

# 导出所有可用组件
__all__ = []

if _performance_monitor_available:
    __all__.extend([
        'PerformanceMonitor', 'MetricType', 'PerformanceMetric',
        'PerformanceReport', 'get_global_performance_monitor'
    ])

if _resource_manager_available:
    __all__.extend([
        'ResourceManager', 'ResourceType', 'ResourceUsage',
        'ResourceLimit', 'ResourceAlert', 'get_global_resource_manager'
    ])

if _memory_manager_available:
    __all__.extend([
        'MemoryManager', 'MemoryPool', 'MemoryTracker',
        'MemoryOptimizer', 'detect_memory_leaks'
    ])

if _performance_profiler_available:
    __all__.extend([
        'PerformanceProfiler', 'ProfileResult', 'HotSpot',
        'ProfilerReport', 'get_global_profiler', 'profile_function'
    ])

if _system_monitor_available:
    __all__.extend([
        'SystemMonitor', 'SystemMetric', 'SystemHealth',
        'SystemStatus', 'get_global_system_monitor'
    ])

if _performance_optimizer_available:
    __all__.extend([
        'PerformanceOptimizer', 'OptimizationRule',
        'OptimizationResult', 'OptimizationType',
        'get_global_performance_optimizer'
    ])

__all__.append('check_module_availability')