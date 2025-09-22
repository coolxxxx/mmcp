"""
错误处理器
提供统一的错误处理、重试和恢复机制
"""

import logging
import time
import threading
from typing import Dict, Any, Optional, Callable, List, Type, Union
from dataclasses import dataclass, field
from enum import Enum
import traceback
import functools

from .base_exceptions import BaseApplicationException


class ErrorSeverity(Enum):
    """错误严重程度"""
    LOW = "low"           # 低级错误，可以忽略
    MEDIUM = "medium"     # 中级错误，需要记录
    HIGH = "high"         # 高级错误，需要处理
    CRITICAL = "critical" # 严重错误，需要立即处理


@dataclass
class RetryPolicy:
    """重试策略"""
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_backoff: bool = True
    jitter: bool = True
    retry_on_exceptions: List[Type[Exception]] = field(default_factory=list)
    
    def should_retry(self, exception: Exception, attempt: int) -> bool:
        """
        判断是否应该重试
        
        Args:
            exception: 异常对象
            attempt: 当前尝试次数
            
        Returns:
            是否应该重试
        """
        if attempt >= self.max_attempts:
            return False
        
        if not self.retry_on_exceptions:
            return True
        
        return any(isinstance(exception, exc_type) for exc_type in self.retry_on_exceptions)
    
    def get_delay(self, attempt: int) -> float:
        """
        获取重试延迟时间
        
        Args:
            attempt: 当前尝试次数
            
        Returns:
            延迟时间（秒）
        """
        if self.exponential_backoff:
            delay = self.base_delay * (2 ** (attempt - 1))
        else:
            delay = self.base_delay
        
        delay = min(delay, self.max_delay)
        
        if self.jitter:
            import random
            delay *= (0.5 + random.random() * 0.5)
        
        return delay


@dataclass
class ErrorContext:
    """错误上下文"""
    operation: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    request_id: Optional[str] = None
    timestamp: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'operation': self.operation,
            'parameters': self.parameters,
            'user_id': self.user_id,
            'session_id': self.session_id,
            'request_id': self.request_id,
            'timestamp': self.timestamp
        }


class ErrorHandler:
    """统一错误处理器"""
    
    def __init__(self):
        """初始化错误处理器"""
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # 错误处理策略
        self.handlers: Dict[Type[Exception], Callable] = {}
        self.severity_mapping: Dict[Type[Exception], ErrorSeverity] = {}
        self.retry_policies: Dict[Type[Exception], RetryPolicy] = {}
        
        # 全局回调函数
        self.error_callbacks: List[Callable[[Exception, ErrorContext], None]] = []
        self.recovery_callbacks: List[Callable[[Exception, ErrorContext], Any]] = []
        
        # 统计信息
        self.error_stats = {
            'total_errors': 0,
            'errors_by_type': {},
            'errors_by_severity': {severity.value: 0 for severity in ErrorSeverity},
            'retry_attempts': 0,
            'successful_recoveries': 0
        }
        
        # 线程安全锁
        self.lock = threading.RLock()
        
        # 设置默认处理器
        self._setup_default_handlers()
        
        self.logger.info("错误处理器初始化完成")
    
    def _setup_default_handlers(self):
        """设置默认错误处理器"""
        # 默认重试策略
        default_retry = RetryPolicy(
            max_attempts=3,
            base_delay=1.0,
            retry_on_exceptions=[ConnectionError, TimeoutError]
        )
        
        # 网络相关错误的重试策略
        network_retry = RetryPolicy(
            max_attempts=5,
            base_delay=2.0,
            max_delay=30.0,
            retry_on_exceptions=[ConnectionError, TimeoutError, OSError]
        )
        
        # 设置默认重试策略
        self.set_retry_policy(ConnectionError, network_retry)
        self.set_retry_policy(TimeoutError, network_retry)
        self.set_retry_policy(OSError, default_retry)
        
        # 设置默认严重程度
        self.set_severity(ValueError, ErrorSeverity.MEDIUM)
        self.set_severity(TypeError, ErrorSeverity.MEDIUM)
        self.set_severity(ConnectionError, ErrorSeverity.HIGH)
        self.set_severity(TimeoutError, ErrorSeverity.HIGH)
        self.set_severity(MemoryError, ErrorSeverity.CRITICAL)
        self.set_severity(KeyboardInterrupt, ErrorSeverity.CRITICAL)
    
    def register_handler(self, exception_type: Type[Exception], 
                        handler: Callable[[Exception, ErrorContext], Any]):
        """
        注册异常处理器
        
        Args:
            exception_type: 异常类型
            handler: 处理函数
        """
        with self.lock:
            self.handlers[exception_type] = handler
            self.logger.info(f"注册异常处理器: {exception_type.__name__}")
    
    def set_severity(self, exception_type: Type[Exception], severity: ErrorSeverity):
        """
        设置异常严重程度
        
        Args:
            exception_type: 异常类型
            severity: 严重程度
        """
        with self.lock:
            self.severity_mapping[exception_type] = severity
            self.logger.debug(f"设置异常严重程度: {exception_type.__name__} -> {severity.value}")
    
    def set_retry_policy(self, exception_type: Type[Exception], policy: RetryPolicy):
        """
        设置重试策略
        
        Args:
            exception_type: 异常类型
            policy: 重试策略
        """
        with self.lock:
            self.retry_policies[exception_type] = policy
            self.logger.debug(f"设置重试策略: {exception_type.__name__}")
    
    def add_error_callback(self, callback: Callable[[Exception, ErrorContext], None]):
        """添加错误回调函数"""
        self.error_callbacks.append(callback)
    
    def add_recovery_callback(self, callback: Callable[[Exception, ErrorContext], Any]):
        """添加恢复回调函数"""
        self.recovery_callbacks.append(callback)
    
    def handle_exception(self, exception: Exception, context: ErrorContext = None) -> Any:
        """
        处理异常
        
        Args:
            exception: 异常对象
            context: 错误上下文
            
        Returns:
            处理结果
        """
        if context is None:
            context = ErrorContext(operation="unknown")
        
        with self.lock:
            # 更新统计信息
            self.error_stats['total_errors'] += 1
            exc_type_name = type(exception).__name__
            self.error_stats['errors_by_type'][exc_type_name] = (
                self.error_stats['errors_by_type'].get(exc_type_name, 0) + 1
            )
            
            # 获取严重程度
            severity = self._get_severity(exception)
            self.error_stats['errors_by_severity'][severity.value] += 1
        
        # 记录错误
        self._log_error(exception, context, severity)
        
        # 触发错误回调
        self._trigger_error_callbacks(exception, context)
        
        # 查找并执行处理器
        handler = self._find_handler(exception)
        if handler:
            try:
                return handler(exception, context)
            except Exception as handler_error:
                self.logger.error(f"错误处理器执行失败: {str(handler_error)}")
        
        # 尝试恢复
        recovery_result = self._attempt_recovery(exception, context)
        if recovery_result is not None:
            return recovery_result
        
        # 如果是严重错误，重新抛出
        if severity == ErrorSeverity.CRITICAL:
            raise exception
        
        return None
    
    def execute_with_retry(self, func: Callable, *args, context: ErrorContext = None, 
                          retry_policy: RetryPolicy = None, **kwargs) -> Any:
        """
        带重试机制执行函数
        
        Args:
            func: 要执行的函数
            *args: 函数参数
            context: 错误上下文
            retry_policy: 重试策略
            **kwargs: 函数关键字参数
            
        Returns:
            函数执行结果
        """
        if context is None:
            context = ErrorContext(operation=func.__name__)
        
        attempt = 0
        last_exception = None
        
        while attempt < (retry_policy.max_attempts if retry_policy else 3):
            attempt += 1
            
            try:
                return func(*args, **kwargs)
                
            except Exception as e:
                last_exception = e
                
                # 获取重试策略
                if retry_policy is None:
                    retry_policy = self._get_retry_policy(e)
                
                # 判断是否应该重试
                if not retry_policy.should_retry(e, attempt):
                    break
                
                # 更新统计
                with self.lock:
                    self.error_stats['retry_attempts'] += 1
                
                # 计算延迟时间
                delay = retry_policy.get_delay(attempt)
                
                self.logger.warning(
                    f"函数 {func.__name__} 执行失败，{delay:.2f}秒后重试 "
                    f"(第{attempt}次，最多{retry_policy.max_attempts}次): {str(e)}"
                )
                
                time.sleep(delay)
        
        # 所有重试都失败了，处理最后的异常
        if last_exception:
            return self.handle_exception(last_exception, context)
        
        return None
    
    def _get_severity(self, exception: Exception) -> ErrorSeverity:
        """获取异常严重程度"""
        for exc_type, severity in self.severity_mapping.items():
            if isinstance(exception, exc_type):
                return severity
        
        # 默认严重程度
        if isinstance(exception, (SystemExit, KeyboardInterrupt, MemoryError)):
            return ErrorSeverity.CRITICAL
        elif isinstance(exception, (ConnectionError, TimeoutError, OSError)):
            return ErrorSeverity.HIGH
        elif isinstance(exception, (ValueError, TypeError, AttributeError)):
            return ErrorSeverity.MEDIUM
        else:
            return ErrorSeverity.LOW
    
    def _get_retry_policy(self, exception: Exception) -> RetryPolicy:
        """获取重试策略"""
        for exc_type, policy in self.retry_policies.items():
            if isinstance(exception, exc_type):
                return policy
        
        # 默认重试策略
        return RetryPolicy()
    
    def _find_handler(self, exception: Exception) -> Optional[Callable]:
        """查找异常处理器"""
        for exc_type, handler in self.handlers.items():
            if isinstance(exception, exc_type):
                return handler
        return None
    
    def _log_error(self, exception: Exception, context: ErrorContext, severity: ErrorSeverity):
        """记录错误日志"""
        error_info = {
            'exception_type': type(exception).__name__,
            'message': str(exception),
            'severity': severity.value,
            'context': context.to_dict(),
            'traceback': traceback.format_exc()
        }
        
        if severity == ErrorSeverity.CRITICAL:
            self.logger.critical(f"严重错误: {error_info}")
        elif severity == ErrorSeverity.HIGH:
            self.logger.error(f"高级错误: {error_info}")
        elif severity == ErrorSeverity.MEDIUM:
            self.logger.warning(f"中级错误: {error_info}")
        else:
            self.logger.info(f"低级错误: {error_info}")
    
    def _trigger_error_callbacks(self, exception: Exception, context: ErrorContext):
        """触发错误回调函数"""
        for callback in self.error_callbacks:
            try:
                callback(exception, context)
            except Exception as e:
                self.logger.error(f"错误回调执行失败: {str(e)}")
    
    def _attempt_recovery(self, exception: Exception, context: ErrorContext) -> Any:
        """尝试错误恢复"""
        for callback in self.recovery_callbacks:
            try:
                result = callback(exception, context)
                if result is not None:
                    with self.lock:
                        self.error_stats['successful_recoveries'] += 1
                    self.logger.info(f"错误恢复成功: {type(exception).__name__}")
                    return result
            except Exception as e:
                self.logger.error(f"错误恢复回调执行失败: {str(e)}")
        
        return None
    
    def get_stats(self) -> Dict[str, Any]:
        """获取错误统计信息"""
        with self.lock:
            return self.error_stats.copy()
    
    def reset_stats(self):
        """重置统计信息"""
        with self.lock:
            self.error_stats = {
                'total_errors': 0,
                'errors_by_type': {},
                'errors_by_severity': {severity.value: 0 for severity in ErrorSeverity},
                'retry_attempts': 0,
                'successful_recoveries': 0
            }
        self.logger.info("错误统计信息已重置")


# 全局错误处理器实例
_global_error_handler: Optional[ErrorHandler] = None


def get_global_error_handler() -> ErrorHandler:
    """获取全局错误处理器实例"""
    global _global_error_handler
    if _global_error_handler is None:
        _global_error_handler = ErrorHandler()
    return _global_error_handler


def handle_error(exception: Exception, context: ErrorContext = None) -> Any:
    """便捷的错误处理函数"""
    return get_global_error_handler().handle_exception(exception, context)


def execute_with_retry(func: Callable, *args, **kwargs) -> Any:
    """便捷的重试执行函数"""
    return get_global_error_handler().execute_with_retry(func, *args, **kwargs)