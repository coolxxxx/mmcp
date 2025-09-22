"""
异常处理装饰器
提供便捷的异常处理装饰器
"""

import functools
import time
import logging
from typing import Any, Callable, Optional, Type, Union, List, Dict
import asyncio
import threading

from .base_exceptions import BaseApplicationException, ValidationError
from .error_handler import ErrorHandler, ErrorContext, RetryPolicy, get_global_error_handler
from .error_reporter import get_global_error_reporter, ReportLevel


def handle_exceptions(
    exceptions: Union[Type[Exception], List[Type[Exception]]] = None,
    default_return: Any = None,
    reraise: bool = False,
    log_errors: bool = True,
    report_errors: bool = True,
    context_factory: Callable = None
):
    """
    异常处理装饰器
    
    Args:
        exceptions: 要处理的异常类型
        default_return: 异常时的默认返回值
        reraise: 是否重新抛出异常
        log_errors: 是否记录错误日志
        report_errors: 是否报告错误
        context_factory: 错误上下文工厂函数
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                # 检查是否是要处理的异常类型
                if exceptions:
                    exception_types = exceptions if isinstance(exceptions, list) else [exceptions]
                    if not any(isinstance(e, exc_type) for exc_type in exception_types):
                        raise
                
                # 创建错误上下文
                context = None
                if context_factory:
                    try:
                        context = context_factory(*args, **kwargs)
                    except Exception:
                        pass
                
                if context is None:
                    context = ErrorContext(
                        operation=func.__name__,
                        parameters={'args': str(args)[:200], 'kwargs': str(kwargs)[:200]}
                    )
                
                # 记录日志
                if log_errors:
                    logger = logging.getLogger(func.__module__)
                    logger.error(f"函数 {func.__name__} 执行失败: {str(e)}")
                
                # 报告错误
                if report_errors:
                    get_global_error_reporter().report_exception(e, context)
                
                # 处理异常
                result = get_global_error_handler().handle_exception(e, context)
                
                if reraise:
                    raise
                
                return result if result is not None else default_return
        
        # 异步函数版本
        if asyncio.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    # 检查是否是要处理的异常类型
                    if exceptions:
                        exception_types = exceptions if isinstance(exceptions, list) else [exceptions]
                        if not any(isinstance(e, exc_type) for exc_type in exception_types):
                            raise
                    
                    # 创建错误上下文
                    context = None
                    if context_factory:
                        try:
                            context = context_factory(*args, **kwargs)
                        except Exception:
                            pass
                    
                    if context is None:
                        context = ErrorContext(
                            operation=func.__name__,
                            parameters={'args': str(args)[:200], 'kwargs': str(kwargs)[:200]}
                        )
                    
                    # 记录日志
                    if log_errors:
                        logger = logging.getLogger(func.__module__)
                        logger.error(f"异步函数 {func.__name__} 执行失败: {str(e)}")
                    
                    # 报告错误
                    if report_errors:
                        get_global_error_reporter().report_exception(e, context)
                    
                    # 处理异常
                    result = get_global_error_handler().handle_exception(e, context)
                    
                    if reraise:
                        raise
                    
                    return result if result is not None else default_return
            
            return async_wrapper
        
        return wrapper
    
    return decorator


def retry_on_failure(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_backoff: bool = True,
    jitter: bool = True,
    retry_on_exceptions: List[Type[Exception]] = None,
    give_up_on_exceptions: List[Type[Exception]] = None
):
    """
    重试装饰器
    
    Args:
        max_attempts: 最大重试次数
        base_delay: 基础延迟时间
        max_delay: 最大延迟时间
        exponential_backoff: 是否使用指数退避
        jitter: 是否添加随机抖动
        retry_on_exceptions: 需要重试的异常类型
        give_up_on_exceptions: 不重试的异常类型
    """
    def decorator(func: Callable) -> Callable:
        retry_policy = RetryPolicy(
            max_attempts=max_attempts,
            base_delay=base_delay,
            max_delay=max_delay,
            exponential_backoff=exponential_backoff,
            jitter=jitter,
            retry_on_exceptions=retry_on_exceptions or []
        )
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            context = ErrorContext(
                operation=func.__name__,
                parameters={'args': str(args)[:200], 'kwargs': str(kwargs)[:200]}
            )
            
            attempt = 0
            last_exception = None
            
            while attempt < max_attempts:
                attempt += 1
                
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    
                    # 检查是否应该放弃重试
                    if give_up_on_exceptions:
                        if any(isinstance(e, exc_type) for exc_type in give_up_on_exceptions):
                            raise
                    
                    # 检查是否应该重试
                    if not retry_policy.should_retry(e, attempt):
                        break
                    
                    # 计算延迟时间
                    delay = retry_policy.get_delay(attempt)
                    
                    logger = logging.getLogger(func.__module__)
                    logger.warning(
                        f"函数 {func.__name__} 执行失败，{delay:.2f}秒后重试 "
                        f"(第{attempt}次，最多{max_attempts}次): {str(e)}"
                    )
                    
                    time.sleep(delay)
            
            # 所有重试都失败了
            if last_exception:
                get_global_error_handler().handle_exception(last_exception, context)
                raise last_exception
        
        # 异步函数版本
        if asyncio.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                context = ErrorContext(
                    operation=func.__name__,
                    parameters={'args': str(args)[:200], 'kwargs': str(kwargs)[:200]}
                )
                
                attempt = 0
                last_exception = None
                
                while attempt < max_attempts:
                    attempt += 1
                    
                    try:
                        return await func(*args, **kwargs)
                    except Exception as e:
                        last_exception = e
                        
                        # 检查是否应该放弃重试
                        if give_up_on_exceptions:
                            if any(isinstance(e, exc_type) for exc_type in give_up_on_exceptions):
                                raise
                        
                        # 检查是否应该重试
                        if not retry_policy.should_retry(e, attempt):
                            break
                        
                        # 计算延迟时间
                        delay = retry_policy.get_delay(attempt)
                        
                        logger = logging.getLogger(func.__module__)
                        logger.warning(
                            f"异步函数 {func.__name__} 执行失败，{delay:.2f}秒后重试 "
                            f"(第{attempt}次，最多{max_attempts}次): {str(e)}"
                        )
                        
                        await asyncio.sleep(delay)
                
                # 所有重试都失败了
                if last_exception:
                    get_global_error_handler().handle_exception(last_exception, context)
                    raise last_exception
            
            return async_wrapper
        
        return wrapper
    
    return decorator


def log_exceptions(
    logger: logging.Logger = None,
    level: int = logging.ERROR,
    message_template: str = "函数 {func_name} 执行失败: {error}",
    include_traceback: bool = True
):
    """
    异常日志装饰器
    
    Args:
        logger: 日志记录器
        level: 日志级别
        message_template: 消息模板
        include_traceback: 是否包含堆栈信息
    """
    def decorator(func: Callable) -> Callable:
        func_logger = logger or logging.getLogger(func.__module__)
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                message = message_template.format(
                    func_name=func.__name__,
                    error=str(e),
                    args=args,
                    kwargs=kwargs
                )
                
                func_logger.log(level, message, exc_info=include_traceback)
                raise
        
        # 异步函数版本
        if asyncio.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    message = message_template.format(
                        func_name=func.__name__,
                        error=str(e),
                        args=args,
                        kwargs=kwargs
                    )
                    
                    func_logger.log(level, message, exc_info=include_traceback)
                    raise
            
            return async_wrapper
        
        return wrapper
    
    return decorator


def validate_input(
    validators: Dict[str, Callable[[Any], bool]] = None,
    error_messages: Dict[str, str] = None,
    raise_on_invalid: bool = True
):
    """
    输入验证装饰器
    
    Args:
        validators: 验证器字典，键为参数名，值为验证函数
        error_messages: 错误消息字典
        raise_on_invalid: 验证失败时是否抛出异常
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if not validators:
                return func(*args, **kwargs)
            
            # 获取函数参数名
            import inspect
            sig = inspect.signature(func)
            bound_args = sig.bind(*args, **kwargs)
            bound_args.apply_defaults()
            
            # 验证参数
            for param_name, validator in validators.items():
                if param_name in bound_args.arguments:
                    value = bound_args.arguments[param_name]
                    
                    try:
                        if not validator(value):
                            error_msg = error_messages.get(param_name, f"参数 {param_name} 验证失败")
                            
                            if raise_on_invalid:
                                raise ValidationError(
                                    error_msg,
                                    field=param_name,
                                    value=value
                                )
                            else:
                                logger = logging.getLogger(func.__module__)
                                logger.warning(f"函数 {func.__name__} 参数验证失败: {error_msg}")
                                return None
                    
                    except Exception as e:
                        if isinstance(e, ValidationError):
                            raise
                        
                        error_msg = f"参数 {param_name} 验证器执行失败: {str(e)}"
                        if raise_on_invalid:
                            raise ValidationError(error_msg, field=param_name, value=value, cause=e)
                        else:
                            logger = logging.getLogger(func.__module__)
                            logger.error(error_msg)
                            return None
            
            return func(*args, **kwargs)
        
        return wrapper
    
    return decorator


def timeout_handler(
    timeout_seconds: float,
    timeout_message: str = "操作超时",
    raise_on_timeout: bool = True
):
    """
    超时处理装饰器
    
    Args:
        timeout_seconds: 超时时间（秒）
        timeout_message: 超时消息
        raise_on_timeout: 超时时是否抛出异常
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            result = [None]
            exception = [None]
            
            def target():
                try:
                    result[0] = func(*args, **kwargs)
                except Exception as e:
                    exception[0] = e
            
            thread = threading.Thread(target=target)
            thread.daemon = True
            thread.start()
            thread.join(timeout_seconds)
            
            if thread.is_alive():
                # 超时了
                if raise_on_timeout:
                    from .base_exceptions import TimeoutError as AppTimeoutError
                    raise AppTimeoutError(
                        timeout_message,
                        timeout_duration=timeout_seconds,
                        operation=func.__name__
                    )
                else:
                    logger = logging.getLogger(func.__module__)
                    logger.warning(f"函数 {func.__name__} 执行超时 ({timeout_seconds}秒)")
                    return None
            
            if exception[0]:
                raise exception[0]
            
            return result[0]
        
        # 异步函数版本
        if asyncio.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                try:
                    return await asyncio.wait_for(func(*args, **kwargs), timeout=timeout_seconds)
                except asyncio.TimeoutError:
                    if raise_on_timeout:
                        from .base_exceptions import TimeoutError as AppTimeoutError
                        raise AppTimeoutError(
                            timeout_message,
                            timeout_duration=timeout_seconds,
                            operation=func.__name__
                        )
                    else:
                        logger = logging.getLogger(func.__module__)
                        logger.warning(f"异步函数 {func.__name__} 执行超时 ({timeout_seconds}秒)")
                        return None
            
            return async_wrapper
        
        return wrapper
    
    return decorator


# 便捷的装饰器组合
def robust_operation(
    max_retries: int = 3,
    timeout_seconds: float = None,
    log_errors: bool = True,
    report_errors: bool = True
):
    """
    健壮操作装饰器组合
    
    Args:
        max_retries: 最大重试次数
        timeout_seconds: 超时时间
        log_errors: 是否记录错误
        report_errors: 是否报告错误
    """
    def decorator(func: Callable) -> Callable:
        # 应用装饰器链
        decorated_func = func
        
        # 超时处理
        if timeout_seconds:
            decorated_func = timeout_handler(timeout_seconds)(decorated_func)
        
        # 重试机制
        if max_retries > 1:
            decorated_func = retry_on_failure(max_attempts=max_retries)(decorated_func)
        
        # 异常处理
        decorated_func = handle_exceptions(
            log_errors=log_errors,
            report_errors=report_errors
        )(decorated_func)
        
        return decorated_func
    
    return decorator